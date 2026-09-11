"""Moteur de données XML natif pour XMLForge.

Exécute les opérations (lecture, filtrage, tri, pagination, agrégats, JOIN,
INSERT, UPDATE, DELETE, DDL) directement sur le document XML canonique
XMLForge, SANS SQLite ni SQLAlchemy. Il réutilise uniquement :

- ``xml_engine.document`` : parseur/sérialiseur/validateur du format canonique ;
- ``xml_engine.storage``  : écriture atomique et verrous de fichiers.

Le document manipulé est un simple ``dict`` Python (celui produit par
``parse_document``).

Fonctionnalités :

- SELECT : `*`, colonnes (qualifiées `t.col`/`alias.col`), alias `AS`, DISTINCT,
  WHERE complet, ORDER BY multi-colonnes, LIMIT/OFFSET ;
- agrégats COUNT/SUM/AVG/MIN/MAX, GROUP BY, HAVING ;
- INNER JOIN ... ON ... (boucle imbriquée, résolution des colonnes qualifiées) ;
- INSERT (simple et multi-lignes), UPDATE, DELETE (WHERE obligatoire) ;
- DDL : CREATE TABLE, DROP TABLE, ADD COLUMN, DROP COLUMN ;
- contraintes : PK (simple/composite), UNIQUE, NOT NULL, FK (existence +
  RESTRICT/CASCADE/SET NULL), DEFAULT, AUTO_INCREMENT, validation de types ;
- index mémoire (PK/UNIQUE/index) reconstruit depuis le XML, invalidé après
  mutation — accélère les point-lookups et les vérifications FK.
"""

from __future__ import annotations

import copy
import os
import re
import time
import uuid as uuid_lib
from datetime import datetime

from ..errors import (
    ConflictError,
    ConstraintViolation,
    DataValidationError,
    NotFoundError,
    ValidationFailed,
)
from .document import parse_document, serialize_document, validate_document
from .storage import atomic_write, database_lock

INT_TYPES = {"INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT"}
REAL_TYPES = {"REAL", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC"}
BOOL_TYPES = {"BOOLEAN", "BOOL"}
STRING_TYPES = {"TEXT", "VARCHAR", "CHAR", "CLOB"}
DATE_TYPES = {"DATE", "DATETIME", "TIMESTAMP", "TIME"}
REFERENTIAL_ACTIONS = {"NO ACTION", "RESTRICT", "CASCADE", "SET NULL"}
AGG_FUNCS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}
COMPARISON_OPS = {"=", "!=", "<>", "<", "<=", ">", ">=", "LIKE", "IN", "IS NULL", "IS NOT NULL"}

# Formats documentés des types temporels (validation en écriture uniquement).
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")

# Valeur spéciale de DEFAULT évaluée au moment de l'INSERT (pas à la création).
CURRENT_TIMESTAMP_MARKER = "CURRENT_TIMESTAMP"


def pagination_meta(limit, offset, total):
    """Métadonnées de pagination (aucune donnée inventée)."""
    page_size = max(1, int(limit))
    page = (max(0, int(offset)) // page_size) + 1
    total_pages = max(1, (int(total) + page_size - 1) // page_size) if int(total) > 0 else 1
    return {
        "page": page,
        "page_size": page_size,
        "total": int(total),
        "total_pages": total_pages,
        "current_page": page,
    }


def _now_ms():
    return time.perf_counter() * 1000.0


class Timing:
    """Instrumentation réelle (aucune valeur en dur)."""

    __slots__ = ("read_ms", "write_ms", "parse_ms", "exec_ms", "total_ms", "rows", "engine")

    def __init__(self, engine="xml"):
        self.engine = engine
        self.read_ms = 0.0
        self.write_ms = 0.0
        self.parse_ms = 0.0
        self.exec_ms = 0.0
        self.total_ms = 0.0
        self.rows = 0

    def to_dict(self):
        return {
            "engine": self.engine,
            "total_ms": round(self.total_ms, 3),
            "parse_ms": round(self.parse_ms, 3),
            "exec_ms": round(self.exec_ms, 3),
            "read_ms": round(self.read_ms, 3),
            "write_ms": round(self.write_ms, 3),
            "rows": self.rows,
        }


def coerce_value(value, col_type):
    """Coerce une valeur stockée (chaîne) vers son type natif pour comparaison."""
    if value is None:
        return None
    base = str(col_type or "TEXT").upper()
    if base in INT_TYPES:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"Valeur entière invalide: {value!r}") from exc
    if base in REAL_TYPES:
        try:
            return float(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"Valeur numérique invalide: {value!r}") from exc
    if base in BOOL_TYPES:
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        raise DataValidationError(f"Valeur booléenne invalide: {value!r}")
    return str(value)


def _validate_temporal(value, base):
    """Valide le format documenté d'une valeur DATE/DATETIME/TIME."""
    text = str(value).strip()
    if base == "DATE" and not _DATE_RE.match(text):
        raise DataValidationError(f"DATE invalide (format attendu YYYY-MM-DD): {value!r}")
    if base in {"DATETIME", "TIMESTAMP"} and not _DATETIME_RE.match(text):
        raise DataValidationError(f"{base} invalide (format attendu YYYY-MM-DD HH:MM:SS): {value!r}")
    if base == "TIME" and not _TIME_RE.match(text):
        raise DataValidationError(f"TIME invalide (format attendu HH:MM:SS): {value!r}")
    return text


def coerce_literal(value, col_type):
    """Normalise un littéral SQL vers le type de la colonne cible.

    Aucune conversion silencieuse dangereuse : une valeur incompatible est
    refusée par ``DataValidationError``.
    """
    if value is None:
        return None
    base = str(col_type or "TEXT").upper()
    if base in INT_TYPES:
        if isinstance(value, bool):
            raise DataValidationError(f"Booléen invalide pour une colonne entière: {value!r}")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"Valeur entière invalide: {value!r}") from exc
    if base in REAL_TYPES:
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise DataValidationError(f"Valeur numérique invalide: {value!r}") from exc
    if base in BOOL_TYPES:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
        raise DataValidationError(f"Valeur booléenne invalide: {value!r}")
    if base in DATE_TYPES:
        return _validate_temporal(value, base)
    return str(value)


def check_length(value, col_type, length):
    """Refuse une chaîne trop longue pour VARCHAR/CHAR."""
    base = str(col_type or "TEXT").upper()
    if base not in {"VARCHAR", "CHAR"}:
        return value
    if length in (None, "", "-"):
        return value
    try:
        max_len = int(length)
    except (TypeError, ValueError):
        return value
    if len(str(value)) > max_len:
        raise DataValidationError(f"Valeur trop longue pour une colonne {base}({max_len}): {value!r}")
    return value


def _like_pattern_to_regex(pattern):
    import re

    parts = ["^"]
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
        i += 1
    parts.append("$")
    return re.compile("".join(parts), re.IGNORECASE)


class XmlIndex:
    """Index mémoire secondaire (PK / UNIQUE / index) reconstruit depuis le XML.

    - créé à la première utilisation (lazy), reconstruit depuis le document ;
    - invalidé après chaque mutation du document ;
    - ``maps[(table, col)] = {valeur_coercée: [rows...]}`` ;
    - utilisé pour les point-lookups d'égalité (WHERE = / IN) et les
      vérifications de clés étrangères (existence en O(1)~O(k)).

    Stratégie documentée dans XML_ENGINE.md : index **en mémoire**, recalculé
    depuis le fichier XML (aucune persistance sur disque) — comportement
    identique après redémarrage (reconstruction au premier accès).
    """

    def __init__(self):
        self.maps = {}
        self.types = {}

    def build(self, document):
        self.maps = {}
        self.types = {}
        for table in document.get("tables", []):
            cols = {c["name"]: c for c in table.get("columns", [])}
            candidates = set()
            for col in table.get("columns", []):
                if col.get("primary_key") or col.get("unique") or col.get("index"):
                    candidates.add((table["name"], col["name"], col.get("type", "TEXT")))
            # Index de table (simples et composites) : chaque colonne de l'index
            # est indexée individuellement pour les point-lookups.
            for index in table.get("indexes", []):
                for cname in index.get("columns", []):
                    if cname in cols:
                        candidates.add((table["name"], cname, cols[cname].get("type", "TEXT")))
            for (tname, cname, ctype) in candidates:
                key = (tname, cname)
                self.types[key] = ctype
                mapping = {}
                for row in table.get("rows", []):
                    value = coerce_value(row.get("data", {}).get(cname), ctype)
                    mapping.setdefault(value, []).append(row)
                self.maps[key] = mapping

    def invalidate(self):
        self.maps = {}
        self.types = {}

    def lookup_rows(self, table, column, value):
        mapping = self.maps.get((table, column))
        if mapping is None:
            return None
        col_type = self.types.get((table, column), "TEXT")
        coerced = coerce_value(value, col_type)
        return mapping.get(coerced, [])


def _extract_equalities(node, out):
    """Collecte les prédicats d'égalité simple (colonne = littéral) d'un WHERE.

    Accepte les deux formes d'AST : colonne chaîne (legacy) et
    {"column": ref} / {"literal": v} (nouvelle).
    """
    if not node:
        return
    op = str(node.get("op", "")).upper()
    if op == "AND":
        _extract_equalities(node.get("left"), out)
        _extract_equalities(node.get("right"), out)
        return
    if op != "=":
        return
    column = node.get("column")
    value = node.get("value")
    ref = column
    if isinstance(column, dict):
        if "column" in column:
            ref = column["column"]
        else:
            return
    literal = value
    if isinstance(value, dict):
        if "literal" in value:
            literal = value["literal"]
        else:
            return
    if isinstance(ref, str):
        out.append((ref, literal))


class XmlNativeEngine:
    """Moteur de données opérant sur un document XMLForge en mémoire."""

    def __init__(self, xml_path=None, xml_content=None, document=None):
        self.xml_path = xml_path
        self.xml_content = xml_content
        self.document = document
        self._index = XmlIndex()
        if document is None and (xml_path or xml_content):
            self.load()

    # ------------------------------------------------------------------ I/O
    def load(self, xml_path=None):
        start = _now_ms()
        path = xml_path or self.xml_path
        if path:
            if not os.path.exists(path):
                raise NotFoundError(f"Fichier XML introuvable: {path}")
            with open(path, "rb") as stream:
                content = stream.read()
        else:
            content = self.xml_content
        if content is None:
            raise ValidationFailed("Aucune source XML fournie au moteur")
        self.document = parse_document(content, validate=True)
        self.xml_path = path
        self.read_ms_last = _now_ms() - start
        self._index.invalidate()
        return self.document

    def save(self, xml_path=None, expected_version=None):
        """Sérialise et écrit le document de façon atomique, version +1.

        La vérification de version s'appuie sur la version réellement présente
        sur le disque (sous verrou) : un commit basé sur un état obsolète est
        refusé par ``ConflictError`` (conflit optimiste).
        """
        path = xml_path or self.xml_path
        if not path:
            raise ValidationFailed("Aucun chemin de fichier pour sauvegarder le document")
        document = self.document
        in_memory = int(document.get("version", 1))
        start = _now_ms()
        lock_path = os.path.abspath(path) + ".lock"
        with database_lock(lock_path):
            on_disk = None
            if os.path.exists(path):
                with open(path, "rb") as stream:
                    on_disk = int(parse_document(stream.read(), validate=False).get("version", 1))
            reference = on_disk if on_disk is not None else in_memory
            if expected_version is not None and int(expected_version) != reference:
                raise ConflictError(
                    f"Conflit de version: attendu {expected_version}, version courante {reference}",
                    details={"current_version": reference},
                )
            if expected_version is None and on_disk is not None and on_disk != in_memory:
                raise ConflictError(
                    f"Conflit de version: le fichier a été modifié entre-temps "
                    f"(disque {on_disk}, locale {in_memory})",
                    details={"current_version": on_disk},
                )
            document["version"] = reference + 1
            validate_document(document)
            xml_content = serialize_document(document)
            atomic_write(path, xml_content)
        self.write_ms_last = _now_ms() - start
        return document["version"]

    # ------------------------------------------------------------- tables
    def _active_tables(self):
        return [t for t in self.document.get("tables", []) if t.get("status") != "ARCHIVED"]

    def table(self, name):
        for table in self._active_tables():
            if table["name"] == name:
                return table
        raise NotFoundError(f"Table introuvable: {name}")

    def _table_or_none(self, name):
        for table in self.document.get("tables", []):
            if table["name"] == name:
                return table
        return None

    def list_tables(self):
        return [t["name"] for t in self._active_tables()]

    def _active_columns(self, table):
        return [c for c in table.get("columns", []) if c.get("status") != "ARCHIVED"]

    def list_columns(self, table_name):
        return [{"name": c["name"], "type": c["type"]} for c in self._active_columns(self.table(table_name))]

    def _invalidate_index(self):
        self._index.invalidate()

    def _ensure_index(self):
        if not self._index.maps:
            self._index.build(self.document)
        return self._index

    # ------------------------------------------------------- évaluation WHERE
    def _eval_condition(self, node, resolve, resolve_type, allow_aggregate=False):
        """Évalue une condition générique.

        ``resolve(ref)`` -> valeur coercée ; ``resolve_type(ref)`` -> type de colonne.
        Les colonnes peuvent être des chaînes (éventuellement qualifiées `t.col`),
        des dicts {"column": ref} ou {"aggregate": {...}}.
        """
        if not node:
            return True
        op = str(node.get("op", "")).upper()
        if op == "AND":
            return (self._eval_condition(node["left"], resolve, resolve_type, allow_aggregate)
                    and self._eval_condition(node["right"], resolve, resolve_type, allow_aggregate))
        if op == "OR":
            return (self._eval_condition(node["left"], resolve, resolve_type, allow_aggregate)
                    or self._eval_condition(node["right"], resolve, resolve_type, allow_aggregate))

        lhs, lhs_type = self._resolve_operand(node.get("column"), resolve, resolve_type, allow_aggregate, as_column=True)

        if op == "IS NULL":
            return lhs is None
        if op == "IS NOT NULL":
            return lhs is not None
        if op == "IN":
            values = node.get("value") or []
            coerced = [coerce_literal(v, lhs_type or "TEXT") for v in values]
            return lhs in coerced
        if op == "NOT IN":
            values = node.get("value") or []
            coerced = [coerce_literal(v, lhs_type or "TEXT") for v in values]
            return lhs not in coerced
        if op == "LIKE":
            pattern = node.get("value")
            pattern = pattern.get("literal") if isinstance(pattern, dict) else pattern
            if pattern is None:
                return False
            return bool(_like_pattern_to_regex(str(pattern)).match(str(lhs)))
        if op == "NOT LIKE":
            pattern = node.get("value")
            pattern = pattern.get("literal") if isinstance(pattern, dict) else pattern
            if pattern is None:
                return True
            return not bool(_like_pattern_to_regex(str(pattern)).match(str(lhs)))
        if op == "BETWEEN":
            bounds = node.get("value") or {}
            low = coerce_literal(bounds.get("low"), lhs_type or "TEXT")
            high = coerce_literal(bounds.get("high"), lhs_type or "TEXT")
            return lhs is not None and low <= lhs <= high

        rhs, _rhs_type = self._resolve_operand(node.get("value"), resolve, resolve_type, allow_aggregate, as_column=False)
        if op in {"=", "!=", "<>"}:
            eq = lhs == rhs
            return eq if op == "=" else not eq
        if op in {"<", "<=", ">", ">="}:
            if lhs is None:
                return False
            if op == "<":
                return lhs < rhs
            if op == "<=":
                return lhs <= rhs
            if op == ">":
                return lhs > rhs
            return lhs >= rhs
        raise ValidationFailed(f"Opérateur non supporté par le moteur XML: {op}")

    def _resolve_operand(self, spec, resolve, resolve_type, allow_aggregate, *, as_column):
        """Résout une opérande vers (valeur, type).

        ``as_column=True`` : le côté gauche d'une condition (colonne ou agrégat).
        ``as_column=False`` : le côté droit (littéral, colonne ou agrégat).
        """
        if isinstance(spec, dict):
            if "aggregate" in spec:
                if not allow_aggregate:
                    raise ValidationFailed("Agrégat non autorisé ici (WHERE/ON)")
                return resolve(spec["aggregate"]), None
            if "column" in spec:
                return resolve(spec["column"]), resolve_type(spec["column"])
            if "literal" in spec:
                return spec["literal"], None
            raise ValidationFailed(f"Opérande inconnue: {spec}")
        # spec nu : colonne (à gauche) ou littéral (à droite)
        if as_column:
            return resolve(spec), resolve_type(spec)
        return spec, None

    # ------------------------------------------------------------- SELECT
    def _build_schema(self, statement):
        """Construit {alias: {col: type}} + l'ordre des tables + les alias."""
        order = []
        schema = {}
        from_clause = statement.get("from", {})
        base_name = from_clause["table"]
        base_alias = from_clause.get("alias") or base_name
        if self._table_or_none(base_name) is None:
            raise NotFoundError(f"Table introuvable: {base_name}")
        order.append(base_alias)
        schema[base_alias] = {c["name"]: c.get("type", "TEXT") for c in self._active_columns(self.table(base_name))}
        for join in statement.get("joins", []):
            jname = join["table"]
            jalias = join.get("alias") or jname
            if self._table_or_none(jname) is None:
                raise NotFoundError(f"Table introuvable: {jname}")
            if jalias in schema:
                raise ValidationFailed(f"Alias de table ambigu: {jalias}")
            order.append(jalias)
            schema[jalias] = {c["name"]: c.get("type", "TEXT") for c in self._active_columns(self.table(jname))}
        return order, schema

    def _combine_rows(self, statement, order, schema):
        """Produit la liste des lignes combinées (clés `alias.col` coercées)."""
        from_clause = statement.get("from", {})
        base_alias = order[0]

        def table_rows(alias):
            table = self.table(self._alias_table(alias))
            out = []
            for row in table.get("rows", []):
                combined = {}
                for name, ctype in schema[alias].items():
                    combined[f"{alias}.{name}"] = coerce_value(row.get("data", {}).get(name), ctype)
                combined[f"{alias}.__uuid__"] = row.get("uuid")
                out.append(combined)
            return out

        # alias -> nom de table réel
        def real_name(alias):
            if alias == base_alias:
                return from_clause["table"]
            for join in statement.get("joins", []):
                if (join.get("alias") or join["table"]) == alias:
                    return join["table"]
            return alias

        self._alias_table = real_name

        combined = table_rows(base_alias)
        for join in statement.get("joins", []):
            jalias = join.get("alias") or join["table"]
            right_rows = table_rows(jalias)
            on = join.get("on")
            join_type = join.get("type", "INNER")
            merged = []
            for left in combined:
                matched = False
                for right in right_rows:
                    joined = {**left, **right}
                    resolve, resolve_type = self._row_resolvers(joined, order, schema)
                    if on is None or self._eval_condition(on, resolve, resolve_type, allow_aggregate=False):
                        merged.append(joined)
                        matched = True
                # LEFT JOIN : les lignes de gauche sans correspondance sont
                # conservées avec les colonnes de droite à NULL.
                if not matched and join_type == "LEFT":
                    nulls = {f"{jalias}.{name}": None for name in schema[jalias]}
                    nulls[f"{jalias}.__uuid__"] = None
                    merged.append({**left, **nulls})
            combined = merged
        return combined

    def _filter_rows(self, rows, statement, order, schema):
        where = statement.get("where")
        if not where:
            return rows
        # Optimisation index : restreindre les candidats via les égalités sur
        # colonnes indexées. Réservé aux requêtes mono-table (les candidats sont
        # des UUID de la table de base). Pour les JOIN, on retombe sur le scan.
        if len(order) == 1:
            equalities = []
            _extract_equalities(where, equalities)
            candidates = None
            base_alias = order[0]
            for col_ref, value in equalities:
                parts = col_ref.split(".", 1)
                alias = parts[0] if len(parts) == 2 and parts[0] == base_alias else (base_alias if len(parts) == 1 else None)
                col = parts[1] if len(parts) == 2 else parts[0]
                if alias is None:
                    continue
                table_name = self._alias_table(alias)
                hits = self._ensure_index().lookup_rows(table_name, col, value)
                if hits is None:
                    continue
                uuids = {r.get("uuid") for r in hits}
                candidates = uuids if candidates is None else (candidates & uuids)
            if candidates is not None:
                uuid_key = f"{base_alias}.__uuid__"
                rows = [r for r in rows if r.get(uuid_key) in candidates]

        out = []
        for row in rows:
            resolve, resolve_type = self._row_resolvers(row, order, schema)
            if self._eval_condition(where, resolve, resolve_type, allow_aggregate=False):
                out.append(row)
        return out

    def _resolve_select_item_value(self, item, row, resolve, resolve_type, order, schema):
        kind = item.get("kind")
        if kind == "column":
            return resolve(item["column"]), None
        if kind == "aggregate":
            # En mode non agrégé, un agrégat sans GROUP BY est traité par _execute_aggregate.
            raise ValidationFailed("Agrégat inattendu dans la projection")
        raise ValidationFailed(f"Élément de sélection inconnu: {kind}")

    def _aggregate_output_name(self, agg):
        func = agg["func"]
        arg = agg["arg"]
        return f"{func}({'*' if arg == '*' else arg})"

    def select_statement(self, statement, timing=None):
        """Exécute un SELECT (AST complet) sur le document."""
        start = _now_ms()
        order, schema = self._build_schema(statement)
        rows = self._combine_rows(statement, order, schema)
        rows = self._filter_rows(rows, statement, order, schema)

        select_list = statement.get("select_list") or []
        group_by = statement.get("group_by")
        having = statement.get("having")
        distinct = statement.get("distinct", False)
        limit = max(1, min(int(statement.get("limit", 100)), 500))
        offset = max(0, int(statement.get("offset", 0)))
        has_aggregate = any(item.get("kind") == "aggregate" for item in select_list)

        if has_aggregate or group_by:
            result_rows, total = self._execute_aggregate(rows, statement, order, schema, select_list, group_by, having)
        else:
            projected = []
            for row in rows:
                resolve, resolve_type = self._row_resolvers(row, order, schema)
                out = {}
                for item in select_list:
                    if item.get("kind") == "star":
                        for alias in order:
                            for name in schema[alias]:
                                out_name = name if len(order) == 1 else f"{alias}.{name}"
                                out[out_name] = row.get(f"{alias}.{name}")
                    else:
                        value, _ = self._resolve_select_item_value(item, row, resolve, resolve_type, order, schema)
                        out_name = item.get("alias") or self._item_output_name(item)
                        out[out_name] = value
                projected.append((out, row))
            if distinct:
                seen = set()
                dedup = []
                for out, row in projected:
                    key = tuple((k, repr(v)) for k, v in sorted(out.items()))
                    if key not in seen:
                        seen.add(key)
                        dedup.append((out, row))
                projected = dedup
            total = len(projected)
            projected = self._sort_and_page_rows(projected, statement, order, schema, limit, offset)
            result_rows = [out for out, _ in projected]

        if timing is not None:
            timing.exec_ms += _now_ms() - start
            timing.read_ms = timing.exec_ms
            timing.rows = len(result_rows)
        return {"rows": result_rows, "total": total, "limit": limit, "offset": offset,
                "pagination": pagination_meta(limit, offset, total)}

    def _row_resolvers(self, row, order, schema):
        def resolve(ref):
            if isinstance(ref, dict):
                if "aggregate" in ref:
                    return ref
                if "column" in ref:
                    return self._row_lookup(row, order, schema, ref["column"])
                if "literal" in ref:
                    return ref["literal"]
            return self._row_lookup(row, order, schema, ref)

        def resolve_type(ref):
            if isinstance(ref, dict):
                if "column" in ref:
                    ref = ref["column"]
                else:
                    return None
            if "." in ref:
                q, c = ref.split(".", 1)
                return schema.get(q, {}).get(c)
            matches = [a for a in order if ref in schema[a]]
            return schema[matches[0]][ref] if len(matches) == 1 else None
        return resolve, resolve_type

    def _row_lookup(self, row, order, schema, ref):
        if "." in ref:
            key = ref
        else:
            matches = [a for a in order if ref in schema[a]]
            if not matches:
                raise ValidationFailed(f"Colonne inconnue: {ref}")
            if len(matches) > 1:
                raise ValidationFailed(f"Colonne ambiguë: {ref}")
            key = f"{matches[0]}.{ref}"
        if key not in row:
            raise ValidationFailed(f"Colonne inconnue: {ref}")
        return row[key]

    def _item_output_name(self, item):
        kind = item.get("kind")
        if kind == "column":
            ref = item["column"]
            return ref.split(".", 1)[1] if "." in ref else ref
        if kind == "aggregate":
            return self._aggregate_output_name(item["aggregate"])
        return "*"

    def _bare_name(self, ref):
        return ref.split(".", 1)[1] if "." in ref else ref

    def _walk_aggregates(self, node, add):
        if not node:
            return
        op = str(node.get("op", "")).upper()
        if op in {"AND", "OR"}:
            self._walk_aggregates(node.get("left"), add)
            self._walk_aggregates(node.get("right"), add)
            return
        spec = node.get("column")
        if isinstance(spec, dict):
            if "aggregate" in spec:
                add(spec["aggregate"])
            elif "column" in spec:
                pass
        value = node.get("value")
        if isinstance(value, dict) and "aggregate" in value:
            add(value["aggregate"])

    def _execute_aggregate(self, rows, statement, order, schema, select_list, group_by, having):
        group_by = group_by or []
        groups = {}
        group_order = []
        for row in rows:
            key = tuple(self._row_lookup(row, order, schema, ref) for ref in group_by)
            if key not in groups:
                groups[key] = []
                group_order.append(key)
            groups[key].append(row)

        # Agrégats nécessaires : sélection + HAVING (noms canoniques dédupliqués).
        agg_specs = []

        def add_agg(agg):
            name = self._aggregate_output_name(agg)
            if name not in [n for n, _ in agg_specs]:
                agg_specs.append((name, agg))

        for item in select_list:
            if item.get("kind") == "aggregate":
                add_agg(item["aggregate"])
        if having:
            self._walk_aggregates(having, add_agg)

        def make_env_resolver(env):
            def resolve_env(ref):
                if isinstance(ref, dict):
                    agg = ref.get("aggregate") if "aggregate" in ref else (ref if "func" in ref else None)
                    if agg is not None:
                        name = self._aggregate_output_name(agg)
                    elif "column" in ref:
                        name = self._bare_name(ref["column"])
                    else:
                        return ref.get("literal")
                else:
                    name = self._bare_name(ref)
                if name not in env:
                    raise ValidationFailed(f"Colonne inconnue dans HAVING: {name}")
                return env[name]

            def resolve_type_env(ref):
                return None
            return resolve_env, resolve_type_env

        output_rows = []
        for key in group_order:
            group_rows = groups[key]
            resolve0, _ = self._row_resolvers(group_rows[0], order, schema)
            env = {}
            for ref in group_by:
                env[self._bare_name(ref)] = resolve0(ref)
            for name, agg in agg_specs:
                env[name] = self._aggregate_over_group(agg, group_rows, order, schema)
            for item in select_list:
                if item.get("kind") == "aggregate" and item.get("alias"):
                    env[item["alias"]] = env[self._aggregate_output_name(item["aggregate"])]

            if having is not None:
                resolve_env, resolve_type_env = make_env_resolver(env)
                if not self._eval_condition(having, resolve_env, resolve_type_env, allow_aggregate=True):
                    continue

            out = {}
            for item in select_list:
                if item.get("kind") == "aggregate":
                    agg = item["aggregate"]
                    out[item.get("alias") or self._aggregate_output_name(agg)] = env[self._aggregate_output_name(agg)]
                elif item.get("kind") == "column":
                    ref = item["column"]
                    out[item.get("alias") or self._bare_name(ref)] = resolve0(ref)
            output_rows.append((out, env))

        total = len(output_rows)
        limit = max(1, min(int(statement.get("limit", 100)), 500))
        offset = max(0, int(statement.get("offset", 0)))
        if statement.get("order_by"):
            for item in reversed(statement["order_by"]):
                col = item["column"]
                desc = (item.get("direction", "ASC") or "ASC").upper() == "DESC"
                if isinstance(col, dict) and "aggregate" in col:
                    name = self._aggregate_output_name(col["aggregate"])
                else:
                    name = self._bare_name(col)

                def sort_key(entry, _name=name):
                    out, env = entry
                    if _name in out:
                        value = out[_name]
                    elif _name in env:
                        value = env[_name]
                    else:
                        value = None
                    return (value is not None, value)
                output_rows.sort(key=sort_key, reverse=desc)
        page = output_rows[offset:offset + limit]
        return [out for out, _ in page], total

    def _aggregate_over_group(self, agg, group_rows, order, schema):
        func = agg["func"]
        arg = agg["arg"]
        if func == "COUNT":
            if arg == "*":
                return len(group_rows)
            count = 0
            for row in group_rows:
                if self._row_lookup(row, order, schema, arg) is not None:
                    count += 1
            return count
        values = []
        for row in group_rows:
            resolve, _ = self._row_resolvers(row, order, schema)
            value = resolve(arg)
            if value is not None:
                values.append(value)
        if not values:
            return None
        if func == "SUM":
            return sum(values)
        if func == "AVG":
            total = sum(values)
            return total / len(values)
        if func == "MIN":
            return min(values)
        if func == "MAX":
            return max(values)
        raise ValidationFailed(f"Agrégat non supporté: {func}")

    def _sort_and_page_rows(self, output_rows, statement, order, schema, limit, offset):
        if statement.get("order_by"):
            for item in reversed(statement["order_by"]):
                col = item["column"]
                desc = (item.get("direction", "ASC") or "ASC").upper() == "DESC"
                if isinstance(col, dict) and "aggregate" in col:
                    raise ValidationFailed("ORDER BY avec agrégat nécessite un GROUP BY / une agrégation")
                name = col.split(".", 1)[1] if "." in col else col

                def sort_key(entry, _name=name, _col=col):
                    out, row = entry
                    if _name in out:
                        value = out[_name]
                        return (value is not None, value)
                    # repli : colonne qualifiée non projetée
                    resolve, _ = self._row_resolvers(row, order, schema)
                    value = resolve(_col)
                    return (value is not None, value)
                output_rows.sort(key=sort_key, reverse=desc)
        return output_rows[offset:offset + limit]

    # ------------------------------------------------------------- SELECT (legacy)
    def select(self, table_name, columns=None, where=None, order_by=None, limit=100, offset=0, timing=None):
        select_list = []
        if not columns or columns in (["*"], "*"):
            select_list = [{"kind": "star"}]
        else:
            select_list = [{"kind": "column", "column": c, "alias": None} for c in columns]
        statement = {
            "operation": "select", "distinct": False,
            "from": {"table": table_name, "alias": None}, "joins": [],
            "select_list": select_list, "where": where, "group_by": None, "having": None,
            "order_by": order_by or [], "limit": limit, "offset": offset,
        }
        return self.select_statement(statement, timing=timing)

    # ------------------------------------------------------------- COUNT (legacy)
    def count(self, table_name, where=None, timing=None):
        start = _now_ms()
        result = self.select(table_name, columns=["*"], where=where, limit=500, offset=0, timing=timing)
        if timing is not None:
            timing.read_ms += _now_ms() - start
            timing.rows = result["total"]
        return result["total"]

    # ------------------------------------------------------------- INSERT
    def resolve_insert_rows(self, table_name, statement):
        """Normalise les lignes d'un INSERT en liste de dicts (colonnes → valeurs).

        Supporte la forme explicite `INSERT INTO t (cols) VALUES (...)` et la
        forme implicite `INSERT INTO t VALUES (...)` (ordre du schéma).
        """
        rows = statement.get("rows")
        if rows is None:
            rows = [statement.get("data")]
        if statement.get("columns") is not None:
            return [dict(r) for r in rows]
        table = self.table(table_name)
        col_names = [c["name"] for c in self._active_columns(table)]
        mapped = []
        for row in rows:
            if not row:
                # Tuple vide : tous les DEFAULT / AUTO_INCREMENT s'appliquent.
                mapped.append({})
                continue
            if len(row) != len(col_names):
                raise ValidationFailed(
                    f"INSERT: {len(row)} valeur(s) pour {len(col_names)} colonne(s)")
            mapped.append(dict(zip(col_names, row)))
        return mapped

    def _default_value(self, column):
        """Résout la valeur DEFAULT d'une colonne (évaluation à l'INSERT)."""
        default = column.get("default")
        if default in (None, ""):
            return None
        if str(default).strip().upper() == CURRENT_TIMESTAMP_MARKER:
            return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        return default

    def _compute_row_data(self, table, data, existing_rows):
        """Construit et valide une ligne (DEFAULT + AUTO_INCREMENT + contraintes).

        AUTO_INCREMENT utilise un compteur persistant (``next_auto_increment``)
        pour ne pas réutiliser les identifiants supprimés : le compteur est
        stocké dans le XML et survit au redémarrage.
        """
        columns = self._active_columns(table)
        columns_by_name = {c["name"]: c for c in columns}
        unknown = [k for k in data if k not in columns_by_name]
        if unknown:
            raise ValidationFailed(f"Colonnes inconnues: {sorted(unknown)}")

        row_data = {}
        for column in columns:
            name = column["name"]
            if name in data:
                row_data[name] = data[name]
            else:
                default = self._default_value(column)
                if default is not None:
                    row_data[name] = default
                elif column.get("auto_increment"):
                    row_data[name] = None
                else:
                    row_data[name] = None

        for column in columns:
            name = column["name"]
            if not column.get("auto_increment"):
                continue
            value = row_data.get(name)
            if value in (None, ""):
                counter = column.get("next_auto_increment")
                existing = [coerce_value(r.get("data", {}).get(name), column["type"]) for r in existing_rows]
                numeric = [v for v in existing if isinstance(v, int)]
                next_value = counter if counter else 1
                if numeric:
                    next_value = max(next_value, max(numeric) + 1)
                row_data[name] = next_value
                column["next_auto_increment"] = next_value + 1
            else:
                coerced = coerce_literal(value, column["type"])
                if isinstance(coerced, int) and (column.get("next_auto_increment") is None
                                                 or coerced >= column["next_auto_increment"]):
                    column["next_auto_increment"] = coerced + 1

        self._validate_row(table, row_data, columns, columns_by_name, existing_rows=existing_rows)
        return row_data

    def insert(self, table_name, data, timing=None):
        start = _now_ms()
        table = self.table(table_name)
        row_data = self._compute_row_data(table, data, table.get("rows", []))
        row_uuid = str(uuid_lib.uuid4())
        table.setdefault("rows", []).append({"uuid": row_uuid, "data": row_data})
        self._invalidate_index()
        if timing is not None:
            timing.exec_ms += _now_ms() - start
            timing.rows = 1
        columns_by_name = {c["name"]: c for c in self._active_columns(table)}
        return {"uuid": row_uuid,
                "data": {k: coerce_value(v, columns_by_name[k]["type"]) for k, v in row_data.items()}}

    def insert_many(self, table_name, rows, timing=None):
        """Insertion multi-lignes : validation globale avant application."""
        start = _now_ms()
        table = self.table(table_name)
        working = [dict(r) for r in table.get("rows", [])]
        prepared = []
        for data in rows:
            row_data = self._compute_row_data(table, data, working)
            row_uuid = str(uuid_lib.uuid4())
            prepared.append({"uuid": row_uuid, "data": row_data})
            working.append({"uuid": row_uuid, "data": row_data})
        table["rows"] = working
        self._invalidate_index()
        if timing is not None:
            timing.exec_ms += _now_ms() - start
            timing.rows = len(prepared)
        return {"inserted": len(prepared)}

    def _validate_row(self, table, row_data, columns, columns_by_name, exclude_uuid=None, existing_rows=None):
        existing = existing_rows if existing_rows is not None else table.get("rows", [])
        for column in columns:
            name = column["name"]
            value = row_data.get(name)
            col_type = column.get("type", "TEXT")
            if value is None:
                if column.get("primary_key") and not column.get("auto_increment"):
                    raise ConstraintViolation(f"La clé primaire {name} ne peut pas être NULL")
                if not column.get("nullable", True):
                    raise ConstraintViolation(f"La colonne {name} n'accepte pas NULL (NOT NULL)")
                continue
            coerced = coerce_literal(value, col_type)
            if coerced is None:
                raise ConstraintViolation(f"Valeur invalide pour {name}")
            check_length(value, col_type, column.get("length"))
            if column.get("unique"):
                for other in existing:
                    if other.get("uuid") == exclude_uuid:
                        continue
                    other_value = coerce_value(other.get("data", {}).get(name), col_type)
                    if other_value is not None and other_value == coerced:
                        raise ConstraintViolation(f"Valeur dupliquée pour la contrainte UNIQUE sur {name}: {value!r}")
            if column.get("references"):
                self._check_foreign_key(column, coerced)
        self._check_unique_indexes(table, row_data, columns_by_name, exclude_uuid, existing)
        pk_cols = [c["name"] for c in columns if c.get("primary_key")]
        if pk_cols:
            key = tuple(coerce_literal(row_data.get(name), columns_by_name[name]["type"]) for name in pk_cols)
            if any(v is None for v in key):
                raise ConstraintViolation("La clé primaire ne peut pas contenir NULL")
            for other in existing:
                if other.get("uuid") == exclude_uuid:
                    continue
                other_key = tuple(coerce_value(other.get("data", {}).get(name), columns_by_name[name]["type"]) for name in pk_cols)
                if other_key == key:
                    raise ConstraintViolation(f"Clé primaire dupliquée: {dict(zip(pk_cols, key))}")

    def _check_unique_indexes(self, table, row_data, columns_by_name, exclude_uuid, existing):
        """Applique les index UNIQUE (simples et composites) définis sur la table."""
        for index in table.get("indexes", []):
            if not index.get("unique"):
                continue
            cols = index.get("columns", [])
            key = tuple(
                coerce_literal(row_data.get(c), columns_by_name[c]["type"])
                if c in columns_by_name else None for c in cols)
            if any(v is None for v in key):
                continue  # NULL ne participe pas à l'unicité
            for other in existing:
                if other.get("uuid") == exclude_uuid:
                    continue
                other_key = tuple(
                    coerce_value(other.get("data", {}).get(c), columns_by_name[c]["type"]) for c in cols)
                if other_key == key:
                    raise ConstraintViolation(
                        f"Index UNIQUE violé sur {', '.join(cols)}: {dict(zip(cols, key))}")

    def _check_foreign_key(self, column, value):
        ref_table_name, ref_col_name = column["references"].split(".", 1)
        ref_table = self._table_or_none(ref_table_name)
        if not ref_table:
            raise ConstraintViolation(f"Table référencée introuvable: {ref_table_name}")
        ref_col = next((c for c in ref_table.get("columns", []) if c["name"] == ref_col_name), None)
        if not ref_col:
            raise ConstraintViolation(f"Colonne référencée introuvable: {column['references']}")
        if value is None:
            return
        hits = self._ensure_index().lookup_rows(ref_table_name, ref_col_name, value)
        if hits is not None:
            if hits:
                return
            raise ConstraintViolation(f"Clé étrangère invalide: {column['references']} = {value!r} n'existe pas")
        matches = any(
            coerce_value(r.get("data", {}).get(ref_col_name), ref_col.get("type", "TEXT")) == value
            for r in ref_table.get("rows", [])
        )
        if not matches:
            raise ConstraintViolation(f"Clé étrangère invalide: {column['references']} = {value!r} n'existe pas")

    # ------------------------------------------------------------- UPDATE
    def _strip_qualifier(self, ref, table_name):
        if "." in ref:
            qualifier, name = ref.split(".", 1)
            if qualifier != table_name:
                raise ValidationFailed(f"Colonne inconnue dans WHERE: {ref}")
            return name
        return ref

    def _candidate_uuids(self, table_name, columns_by_name, where):
        """Optimisation index : candidats UUID pour un WHERE avec égalités."""
        if not where:
            return None
        equalities = []
        _extract_equalities(where, equalities)
        candidates = None
        for ref, value in equalities:
            name = self._strip_qualifier(ref, table_name)
            if name not in columns_by_name:
                continue
            hits = self._ensure_index().lookup_rows(table_name, name, value)
            if hits is None:
                continue
            uuids = {r.get("uuid") for r in hits}
            candidates = uuids if candidates is None else (candidates & uuids)
        return candidates

    def update(self, table_name, data, where=None, row_uuid=None, timing=None, replace=False):
        start = _now_ms()
        table = self.table(table_name)
        columns = self._active_columns(table)
        columns_by_name = {c["name"]: c for c in columns}
        unknown = [k for k in data if k not in columns_by_name]
        if unknown:
            raise ValidationFailed(f"Colonnes inconnues: {sorted(unknown)}")

        candidates = self._candidate_uuids(table_name, columns_by_name, where)
        matched = []
        for row in table.get("rows", []):
            if row_uuid and row["uuid"] == row_uuid:
                matched.append(row)
                continue
            if not row_uuid and where is None:
                raise ValidationFailed("UPDATE sans WHERE est refusé par sécurité")
            if not row_uuid and candidates is not None and row.get("uuid") not in candidates:
                continue
            if not row_uuid and where is not None:
                coerced = {name: coerce_value(row.get("data", {}).get(name), c.get("type", "TEXT")) for name, c in columns_by_name.items()}

                def resolve(ref):
                    name = self._strip_qualifier(ref, table_name)
                    if name in coerced:
                        return coerced[name]
                    raise ValidationFailed(f"Colonne inconnue dans WHERE: {ref}")

                def resolve_type(ref):
                    name = self._strip_qualifier(ref, table_name)
                    return columns_by_name.get(name, {}).get("type", "TEXT")
                if self._eval_condition(where, resolve, resolve_type, allow_aggregate=False):
                    matched.append(row)
        if not matched:
            if timing is not None:
                timing.exec_ms += _now_ms() - start
            return {"updated": 0}

        def merged_data(row):
            if replace:
                merged = dict(data)
                for column in columns:
                    if column.get("auto_increment") and column["name"] not in merged:
                        merged[column["name"]] = row.get("data", {}).get(column["name"])
                return merged
            return {**row.get("data", {}), **data}

        changed_references = self._collect_reference_changes(table_name, data, matched, columns_by_name)
        for row in matched:
            self._validate_row(table, merged_data(row), columns, columns_by_name, exclude_uuid=row.get("uuid"))
        self._propagate_reference_updates(changed_references, table, columns_by_name)
        for row in matched:
            row["data"] = merged_data(row)
        self._invalidate_index()
        if timing is not None:
            timing.exec_ms += _now_ms() - start
            timing.rows = len(matched)
        return {"updated": len(matched)}

    def _collect_reference_changes(self, table_name, data, matched_rows, columns_by_name):
        changed = {}
        for name, new_value in data.items():
            column = columns_by_name.get(name)
            if not column or not (column.get("primary_key") or column.get("unique")):
                continue
            reference_key = f"{table_name}.{name}"
            for row in matched_rows:
                old_value = coerce_value(row.get("data", {}).get(name), column["type"])
                coerced_new = coerce_literal(new_value, column["type"])
                if old_value != coerced_new:
                    changed.setdefault(reference_key, []).append((old_value, coerced_new))
        return changed

    def _referencing_columns(self, reference_key):
        result = []
        for table in self.document.get("tables", []):
            for column in table.get("columns", []):
                if column.get("references") == reference_key:
                    result.append((table, column))
        return result

    def _propagate_reference_updates(self, changed_references, table, columns_by_name):
        for reference_key, pairs in changed_references.items():
            for table_doc, column in self._referencing_columns(reference_key):
                action = (column.get("on_update") or "NO ACTION").upper()
                if action not in REFERENTIAL_ACTIONS:
                    raise ConstraintViolation(f"Action ON UPDATE non supportée par le moteur XML: {action}")
                for old_value, new_value in pairs:
                    for row in table_doc.get("rows", []):
                        cell = row.get("data", {}).get(column["name"])
                        if cell is None:
                            continue
                        stored = coerce_value(cell, column.get("type", "TEXT"))
                        if stored == old_value:
                            if action in {"NO ACTION", "RESTRICT"}:
                                raise ConstraintViolation(
                                    f"Impossible de modifier {reference_key}: valeur référencée par {table_doc['name']}.{column['name']}")
                            if action == "CASCADE":
                                row["data"][column["name"]] = str(new_value)
                            elif action == "SET NULL":
                                if not column.get("nullable", True):
                                    raise ConstraintViolation(
                                        f"SET NULL impossible: {table_doc['name']}.{column['name']} est NOT NULL")
                                row["data"][column["name"]] = None

    # ------------------------------------------------------------- DELETE
    def delete(self, table_name, where=None, row_uuid=None, timing=None):
        start = _now_ms()
        table = self.table(table_name)
        columns_by_name = {c["name"]: c for c in self._active_columns(table)}
        candidates = self._candidate_uuids(table_name, columns_by_name, where)
        matched = []
        for row in table.get("rows", []):
            if row_uuid and row["uuid"] == row_uuid:
                matched.append(row)
                continue
            if not row_uuid and where is None:
                raise ValidationFailed("DELETE sans WHERE est refusé par sécurité")
            if not row_uuid and candidates is not None and row.get("uuid") not in candidates:
                continue
            if not row_uuid and where is not None:
                coerced = {name: coerce_value(row.get("data", {}).get(name), c.get("type", "TEXT")) for name, c in columns_by_name.items()}

                def resolve(ref):
                    name = self._strip_qualifier(ref, table_name)
                    if name in coerced:
                        return coerced[name]
                    raise ValidationFailed(f"Colonne inconnue dans WHERE: {ref}")

                def resolve_type(ref):
                    name = self._strip_qualifier(ref, table_name)
                    return columns_by_name.get(name, {}).get("type", "TEXT")
                if self._eval_condition(where, resolve, resolve_type, allow_aggregate=False):
                    matched.append(row)
        if not matched:
            if timing is not None:
                timing.exec_ms += _now_ms() - start
            return {"deleted": 0}

        to_delete = self._resolve_cascades(table_name, matched)
        removed = 0
        for target_name, uuids in to_delete.items():
            target_table = self._table_or_none(target_name)
            target_table["rows"] = [r for r in target_table.get("rows", []) if r["uuid"] not in uuids]
            removed += len(uuids)
        self._invalidate_index()
        if timing is not None:
            timing.exec_ms += _now_ms() - start
            timing.rows = removed
        return {"deleted": removed}

    def _resolve_cascades(self, table_name, matched_rows):
        plan = {}
        plan.setdefault(table_name, set()).update(r["uuid"] for r in matched_rows)
        queue = [(table_name, list(matched_rows))]
        while queue:
            origin_name, origin_rows = queue.pop(0)
            origin = self._table_or_none(origin_name)
            origin_columns = {c["name"]: c for c in origin.get("columns", [])}
            candidate_keys = {f"{origin_name}.{name}" for name in origin_columns}
            for table_doc in self.document.get("tables", []):
                for column in table_doc.get("columns", []):
                    ref = column.get("references")
                    if not ref or ref not in candidate_keys:
                        continue
                    ref_col_name = ref.split(".", 1)[1]
                    action = (column.get("on_delete") or "NO ACTION").upper()
                    if action not in REFERENTIAL_ACTIONS:
                        raise ConstraintViolation(f"Action ON DELETE non supportée par le moteur XML: {action}")
                    for origin_row in origin_rows:
                        origin_value = coerce_value(
                            origin_row.get("data", {}).get(ref_col_name),
                            origin_columns[ref_col_name]["type"],
                        )
                        referencing = []
                        for row in table_doc.get("rows", []):
                            cell = row.get("data", {}).get(column["name"])
                            if cell is None:
                                continue
                            stored = coerce_value(cell, column.get("type", "TEXT"))
                            if stored == origin_value:
                                referencing.append(row)
                        if not referencing:
                            continue
                        if action in {"NO ACTION", "RESTRICT"}:
                            raise ConstraintViolation(
                                f"Impossible de supprimer la ligne de {origin_name}: référencée par {table_doc['name']}.{column['name']}")
                        if action == "CASCADE":
                            plan.setdefault(table_doc["name"], set()).update(r["uuid"] for r in referencing)
                            queue.append((table_doc["name"], referencing))
                        elif action == "SET NULL":
                            if not column.get("nullable", True):
                                raise ConstraintViolation(
                                    f"SET NULL impossible: {table_doc['name']}.{column['name']} est NOT NULL")
                            for row in referencing:
                                row["data"][column["name"]] = None
        return plan

    # ------------------------------------------------------------- DDL
    def create_table(self, name, columns=None, description="", protected=False, file_identifier=None):
        if self._table_or_none(name):
            raise ConstraintViolation(f"Table déjà existante: {name}")
        col_docs = []
        for spec in columns or []:
            column = {
                "uuid": str(uuid_lib.uuid4()),
                "name": spec["name"],
                "type": (spec.get("type") or "TEXT").upper(),
                "length": spec.get("length", "-"),
                "nullable": bool(spec.get("nullable", True)),
                "primary_key": bool(spec.get("primary_key", False)),
                "foreign_key": bool(spec.get("foreign_key", False) or spec.get("references")),
                "references": spec.get("references"),
                "on_delete": (spec.get("on_delete") or "NO ACTION").upper(),
                "on_update": (spec.get("on_update") or "NO ACTION").upper(),
                "unique": bool(spec.get("unique", False)),
                "auto_increment": bool(spec.get("auto_increment", False)),
                "index": bool(spec.get("index", False)),
                "default": spec.get("default"),
                "comment": spec.get("comment", ""),
                "status": "ACTIVE",
            }
            col_docs.append(column)
        self.document.setdefault("tables", []).append({
            "uuid": str(uuid_lib.uuid4()),
            "name": name,
            "description": description,
            "comment": "",
            "protected": bool(protected),
            "file_identifier": file_identifier,
            "status": "ACTIVE",
            "constraints": [],
            "indexes": [],
            "columns": col_docs,
            "rows": [],
        })
        validate_document(self.document)
        self._invalidate_index()
        return self._table_or_none(name)

    def add_column(self, table_name, spec):
        table = self.table(table_name)
        if any(c["name"] == spec["name"] for c in table.get("columns", [])):
            raise ConstraintViolation(f"Colonne déjà existante: {spec['name']}")
        column = {
            "uuid": str(uuid_lib.uuid4()),
            "name": spec["name"],
            "type": (spec.get("type") or "TEXT").upper(),
            "length": spec.get("length", "-"),
            "nullable": bool(spec.get("nullable", True)),
            "primary_key": bool(spec.get("primary_key", False)),
            "foreign_key": bool(spec.get("foreign_key", False) or spec.get("references")),
            "references": spec.get("references"),
            "on_delete": (spec.get("on_delete") or "NO ACTION").upper(),
            "on_update": (spec.get("on_update") or "NO ACTION").upper(),
            "unique": bool(spec.get("unique", False)),
            "auto_increment": bool(spec.get("auto_increment", False)),
            "index": bool(spec.get("index", False)),
            "default": spec.get("default"),
            "comment": spec.get("comment", ""),
            "status": "ACTIVE",
        }
        if table.get("rows") and not column["nullable"] and column.get("default") in (None, ""):
            raise ConstraintViolation(
                f"Ajout de colonne NOT NULL sans défaut impossible: la table {table_name} contient déjà des lignes")
        table.setdefault("columns", []).append(column)
        # Backfill du DEFAULT dans les lignes existantes (comportement SQL standard).
        default = self._default_value(column)
        if table.get("rows") and default is not None:
            for row in table["rows"]:
                row.setdefault("data", {})[column["name"]] = default
        validate_document(self.document)
        self._invalidate_index()
        return column

    def drop_column(self, table_name, name):
        table = self.table(table_name)
        column = next((c for c in table.get("columns", []) if c["name"] == name), None)
        if not column:
            raise NotFoundError(f"Colonne introuvable: {name}")
        for other in self.document.get("tables", []):
            for col in other.get("columns", []):
                if col.get("references") == f"{table_name}.{name}":
                    raise ConstraintViolation(f"Colonne référencée par {other['name']}.{col['name']}")
        table["columns"] = [c for c in table.get("columns", []) if c["name"] != name]
        for row in table.get("rows", []):
            row.get("data", {}).pop(name, None)
        table["indexes"] = [idx for idx in table.get("indexes", []) if name not in idx.get("columns", [])]
        validate_document(self.document)
        self._invalidate_index()
        return True

    def drop_table(self, name):
        table = self._table_or_none(name)
        if not table:
            raise NotFoundError(f"Table introuvable: {name}")
        for other in self.document.get("tables", []):
            for col in other.get("columns", []):
                if (col.get("references") or "").startswith(f"{name}."):
                    raise ConstraintViolation(f"Table référencée par {other['name']}.{col['name']}")
        self.document["tables"] = [t for t in self.document.get("tables", []) if t["name"] != name]
        self._invalidate_index()
        return True

    # ------------------------------------------------------------- indexes
    def _check_index_uniqueness(self, table, columns):
        """Vérifie qu'aucune ligne existante ne viole un (futur) index UNIQUE.

        NULL ne participe pas à l'unicité (comportement SQL standard).
        """
        col_types = {c["name"]: c.get("type", "TEXT") for c in table.get("columns", [])}
        seen = set()
        for row in table.get("rows", []):
            key = tuple(coerce_value(row.get("data", {}).get(c), col_types[c]) for c in columns)
            if any(v is None for v in key):
                continue
            if key in seen:
                raise ConstraintViolation(
                    f"Index UNIQUE violé sur {', '.join(columns)}: {dict(zip(columns, key))}")
            seen.add(key)

    def create_index(self, table_name, name, columns, unique=False):
        table = self.table(table_name)
        active = {c["name"] for c in self._active_columns(table)}
        for c in columns:
            if c not in active:
                raise ValidationFailed(f"Colonne inconnue dans l'index: {c}")
        indexes = table.setdefault("indexes", [])
        if any(i["name"] == name for i in indexes):
            raise ConstraintViolation(f"Index déjà existant: {name}")
        if unique:
            self._check_index_uniqueness(table, columns)
        indexes.append({"name": name, "columns": list(columns), "unique": bool(unique)})
        if len(columns) == 1 and not unique:
            col = next((c for c in table.get("columns", []) if c["name"] == columns[0]), None)
            if col is not None:
                col["index"] = True
        validate_document(self.document)
        self._invalidate_index()
        return {"name": name, "columns": list(columns), "unique": bool(unique)}

    def drop_index(self, table_name, name):
        if table_name:
            table = self.table(table_name)
            indexes = table.get("indexes", [])
            index = next((i for i in indexes if i["name"] == name), None)
            if index is None:
                raise NotFoundError(f"Index introuvable: {name}")
            if len(index["columns"]) == 1:
                col = next((c for c in table.get("columns", []) if c["name"] == index["columns"][0]), None)
                if col is not None and not any(
                        other["name"] != name and index["columns"][0] in other["columns"]
                        for other in indexes):
                    col["index"] = False
            table["indexes"] = [i for i in indexes if i["name"] != name]
            validate_document(self.document)
            self._invalidate_index()
            return True
        # DROP INDEX name (sans table) : recherche sur toutes les tables.
        for t in self.document.get("tables", []):
            if any(i["name"] == name for i in t.get("indexes", [])):
                return self.drop_index(t["name"], name)
        raise NotFoundError(f"Index introuvable: {name}")

    # ------------------------------------------------------------- ALTER
    def modify_column(self, table_name, name, spec):
        table = self.table(table_name)
        column = next((c for c in table.get("columns", []) if c["name"] == name), None)
        if not column:
            raise NotFoundError(f"Colonne introuvable: {name}")
        new_type = (spec.get("type") or column["type"]).upper()
        new_length = spec.get("length", column.get("length", "-"))
        new_nullable = bool(spec.get("nullable", column.get("nullable", True)))
        # Vérifier les valeurs existantes contre le nouveau type/longueur.
        for row in table.get("rows", []):
            value = row.get("data", {}).get(name)
            if value is None:
                if not new_nullable:
                    raise ConstraintViolation(
                        f"Impossible de rendre {name} NOT NULL: des lignes ont une valeur NULL")
                continue
            try:
                coerce_literal(value, new_type)
            except DataValidationError as exc:
                raise ConstraintViolation(
                    f"Valeur incompatible avec le nouveau type {new_type}: {value!r}") from exc
            if new_type in {"VARCHAR", "CHAR"} and new_length not in (None, "", "-"):
                if len(str(value)) > int(new_length):
                    raise ConstraintViolation(
                        f"Valeur trop longue pour le nouveau type {new_type}({new_length}): {value!r}")
        column["type"] = new_type
        column["length"] = str(new_length)
        column["nullable"] = new_nullable
        if "default" in spec:
            column["default"] = spec["default"]
        validate_document(self.document)
        self._invalidate_index()
        return column

    def rename_table(self, table_name, new_name):
        table = self._table_or_none(table_name)
        if not table:
            raise NotFoundError(f"Table introuvable: {table_name}")
        if self._table_or_none(new_name):
            raise ConstraintViolation(f"Table déjà existante: {new_name}")
        old = table["name"]
        table["name"] = new_name
        # Met à jour les références FK internes pointant vers l'ancien nom.
        for other in self.document.get("tables", []):
            for col in other.get("columns", []):
                ref = col.get("references")
                if ref and ref.startswith(old + "."):
                    col["references"] = new_name + ref[len(old):]
        validate_document(self.document)
        self._invalidate_index()
        return table

    def deep_copy(self):
        return copy.deepcopy(self.document)
