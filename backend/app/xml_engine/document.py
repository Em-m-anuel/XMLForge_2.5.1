"""Parseur et sérialiseur uniques du document XMLForge canonique."""
from __future__ import annotations

import copy
import os
import re
import uuid as uuid_lib
from datetime import datetime
from functools import lru_cache
from lxml import etree
from ..errors import XmlValidationError

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_TYPES = {
    "INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT",
    "TEXT", "VARCHAR", "CHAR", "CLOB",
    "REAL", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC",
    "BOOLEAN", "BOOL", "DATE", "DATETIME", "TIMESTAMP", "TIME",
    "BLOB", "JSON",
}


def as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes"}


def _int_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def validate_identifier(name, kind="identifiant"):
    if not name or not IDENTIFIER_RE.fullmatch(name):
        raise XmlValidationError(
            f"{kind} invalide '{name}'. Utilisez lettres, chiffres et underscore, sans commencer par un chiffre."
        )
    return name


def normalize_type(value):
    value = (value or "TEXT").strip().upper()
    base = value.split("(", 1)[0].strip()
    if base not in ALLOWED_TYPES:
        raise XmlValidationError(f"Type de colonne non supporté: {value}")
    return base


@lru_cache(maxsize=1)
def _xsd_schema():
    xsd_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "xmlforge.xsd")
    try:
        return etree.XMLSchema(etree.parse(xsd_path))
    except Exception as exc:
        raise XmlValidationError(f"Impossible de charger le XSD XMLForge: {exc}") from exc


def validate_xml_bytes(xml_bytes):
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True, huge_tree=False)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as exc:
        raise XmlValidationError(f"XML mal formé: {exc}") from exc
    schema = _xsd_schema()
    if not schema.validate(root):
        errors = [e.message for e in schema.error_log]
        raise XmlValidationError("XML non conforme au schéma XMLForge", details=errors)
    return root


def _parse_column(elem):
    name = validate_identifier(elem.get("name"), "Nom de colonne")
    references = elem.get("references") or elem.get("foreignKeyRef")
    if references:
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)[.(]([A-Za-z_][A-Za-z0-9_]*)\)?", references)
        if not match:
            raise XmlValidationError(f"Référence FK invalide pour {name}: {references}")
        references = f"{match.group(1)}.{match.group(2)}"
    return {
        "internal_id": _int_or_none(elem.get("internal_id")),
        "uuid": elem.get("uuid") or str(uuid_lib.uuid4()),
        "name": name,
        "type": normalize_type(elem.get("type")),
        "length": elem.get("length", "-"),
        "nullable": as_bool(elem.get("nullable"), True),
        "primary_key": as_bool(elem.get("primary_key", elem.get("primaryKey"))),
        "foreign_key": as_bool(elem.get("foreign_key", elem.get("foreignKey"))) or bool(references),
        "references": references,
        "on_delete": (elem.get("on_delete") or "NO ACTION").upper(),
        "on_update": (elem.get("on_update") or "NO ACTION").upper(),
        "unique": as_bool(elem.get("unique")),
        "auto_increment": as_bool(elem.get("auto_increment", elem.get("autoIncrement"))),
        "next_auto_increment": _int_or_none(elem.get("next_auto_increment")),
        "index": as_bool(elem.get("index")),
        "default": elem.get("default"),
        "comment": elem.get("comment", ""),
        "status": (elem.get("status") or "ACTIVE").upper(),
        "creator_id": _int_or_none(elem.get("creator_id")),
        "creator_name": elem.get("creator_name"),
        "created_at": elem.get("created_at"),
        "updated_at": elem.get("updated_at"),
    }


def _parse_constraints(table_elem):
    result = []
    parent = table_elem.find("constraints")
    if parent is None:
        return result
    for elem in parent:
        columns = [validate_identifier(c.get("name"), "Colonne de contrainte") for c in elem.findall("column")]
        item = {"kind": elem.tag, "name": elem.get("name"), "columns": columns}
        if elem.tag == "foreign-key":
            item.update({
                "references_table": validate_identifier(elem.get("references_table"), "Table référencée"),
                "references_columns": [validate_identifier(c.strip(), "Colonne référencée") for c in (elem.get("references_columns") or "").split(",") if c.strip()],
                "on_delete": (elem.get("on_delete") or "NO ACTION").upper(),
                "on_update": (elem.get("on_update") or "NO ACTION").upper(),
            })
        result.append(item)
    return result


def _parse_indexes(table_elem):
    result = []
    parent = table_elem.find("indexes")
    if parent is None:
        return result
    for elem in parent.findall("index"):
        result.append({
            "name": validate_identifier(elem.get("name"), "Nom d'index"),
            "unique": as_bool(elem.get("unique")),
            "columns": [validate_identifier(c.get("name"), "Colonne d'index") for c in elem.findall("column")],
        })
    return result


def _parse_rows(table_elem, known_columns):
    rows = []
    parent = table_elem.find("rows")
    if parent is None:
        return rows
    known = set(known_columns)
    for row_elem in parent.findall("row"):
        data = {}
        for cell in row_elem.findall("cell"):
            column = cell.get("column")
            if column not in known:
                raise XmlValidationError(f"Cellule associée à une colonne inconnue: {column}")
            data[column] = None if as_bool(cell.get("null")) else (cell.text or "")
        rows.append({
            "internal_id": _int_or_none(row_elem.get("internal_id")),
            "uuid": row_elem.get("uuid") or str(uuid_lib.uuid4()),
            "data": data,
        })
    return rows


def _parse_table(elem):
    name = validate_identifier(elem.get("name"), "Nom de table")
    columns_parent = elem.find("columns")
    column_elems = columns_parent.findall("column") if columns_parent is not None else elem.findall("column")
    columns = [_parse_column(c) for c in column_elems]
    names = [c["name"] for c in columns]
    if len(names) != len(set(names)):
        raise XmlValidationError(f"Colonnes dupliquées dans la table {name}")
    table = {
        "internal_id": _int_or_none(elem.get("internal_id")),
        "uuid": elem.get("uuid") or str(uuid_lib.uuid4()),
        "name": name,
        "description": elem.get("description", ""),
        "comment": elem.get("comment", ""),
        "protected": as_bool(elem.get("protected", elem.get("is_protected"))),
        "file_identifier": elem.get("file_identifier") or elem.get("fileIdentifier"),
        "status": "ARCHIVED" if as_bool(elem.get("archived")) else (elem.get("status") or "ACTIVE").upper(),
        "columns": columns,
        "constraints": _parse_constraints(elem),
        "indexes": _parse_indexes(elem),
        "creator_id": _int_or_none(elem.get("creator_id")),
        "creator_name": elem.get("creator_name"),
        "created_at": elem.get("created_at"),
        "updated_at": elem.get("updated_at"),
    }
    table["rows"] = _parse_rows(elem, names)
    return table


def parse_document(xml_content, validate=True):
    xml_bytes = xml_content.encode("utf-8") if isinstance(xml_content, str) else xml_content
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True, huge_tree=False)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as exc:
        raise XmlValidationError(f"XML mal formé: {exc}") from exc

    # Compatibilité : l'ancien format autorisait des <column> directs. Il est
    # normalisé avant validation canonique.
    if root.tag == "table":
        db_root = etree.Element("database", name="imported_database", version="1", status="ACTIVE", scope="PERSONAL")
        db_root.append(copy.deepcopy(root))
        root = db_root
    elif root.tag == "tables":
        db_root = etree.Element("database", name="imported_database", version="1", status="ACTIVE", scope="PERSONAL")
        for table in root.findall("table"):
            db_root.append(copy.deepcopy(table))
        root = db_root
    elif root.tag != "database":
        candidate = root.find(".//database")
        if candidate is None:
            raise XmlValidationError("La racine doit être <database>, <table> ou <tables>")
        root = copy.deepcopy(candidate)

    for table in root.findall("table"):
        direct = table.findall("column")
        if direct and table.find("columns") is None:
            wrapper = etree.Element("columns")
            for col in direct:
                table.remove(col)
                wrapper.append(col)
            table.insert(0, wrapper)

    if validate:
        canonical_bytes = etree.tostring(root, encoding="utf-8", xml_declaration=True)
        root = validate_xml_bytes(canonical_bytes)

    name = validate_identifier(root.get("name"), "Nom de base")
    tables = [_parse_table(t) for t in root.findall("table")]
    table_names = [t["name"] for t in tables]
    if len(table_names) != len(set(table_names)):
        raise XmlValidationError("Noms de tables dupliqués")
    document = {
        "internal_id": _int_or_none(root.get("internal_id")),
        "uuid": root.get("uuid") or str(uuid_lib.uuid4()),
        "name": name,
        "description": root.get("description", ""),
        "comment": root.get("comment", ""),
        "status": (root.get("status") or "ACTIVE").upper(),
        "scope": (root.get("scope") or "PERSONAL").upper(),
        "owner_id": _int_or_none(root.get("owner_id")),
        "version": max(1, _int_or_none(root.get("version")) or 1),
        "generator": root.get("generator", "XMLForge"),
        "created_at": root.get("created_at", datetime.utcnow().isoformat()),
        "author": root.get("author", ""),
        "tables": tables,
    }
    validate_document(document)
    return document


def validate_document(document):
    validate_identifier(document.get("name"), "Nom de base")
    if document.get("scope") not in {"PERSONAL", "COMMON"}:
        raise XmlValidationError("scope doit être PERSONAL ou COMMON")
    tables = document.get("tables", [])
    names = set()
    for table in tables:
        validate_identifier(table.get("name"), "Nom de table")
        if table["name"] in names:
            raise XmlValidationError(f"Table dupliquée: {table['name']}")
        names.add(table["name"])
        column_names = {c["name"] for c in table.get("columns", [])}
        for col in table.get("columns", []):
            validate_identifier(col["name"], "Nom de colonne")
            normalize_type(col["type"])
            if col.get("auto_increment") and (not col.get("primary_key") or col["type"] not in {"INT", "INTEGER", "BIGINT"}):
                raise XmlValidationError(f"AUTO_INCREMENT exige une PK entière: {table['name']}.{col['name']}")
            if col.get("references"):
                ref_table, ref_col = col["references"].split(".", 1)
                target = next((t for t in tables if t["name"] == ref_table), None)
                if not target or ref_col not in {x["name"] for x in target.get("columns", [])}:
                    raise XmlValidationError(f"Référence FK introuvable: {col['references']}")
        for row in table.get("rows", []):
            unknown = set(row.get("data", {})) - column_names
            if unknown:
                raise XmlValidationError(f"Colonnes inconnues dans une ligne de {table['name']}: {sorted(unknown)}")
    return document


def _set_optional(attrs, key, value):
    if value not in (None, ""):
        attrs[key] = str(value)


def _table_element(table):
    attrs = {
        "name": table["name"],
        "uuid": table.get("uuid") or str(uuid_lib.uuid4()),
        "description": table.get("description", ""),
        "comment": table.get("comment", ""),
        "protected": str(bool(table.get("protected"))).lower(),
        "archived": str(table.get("status") == "ARCHIVED").lower(),
        "status": table.get("status", "ACTIVE"),
    }
    _set_optional(attrs, "internal_id", table.get("internal_id"))
    _set_optional(attrs, "file_identifier", table.get("file_identifier"))
    _set_optional(attrs, "creator_id", table.get("creator_id"))
    _set_optional(attrs, "creator_name", table.get("creator_name"))
    _set_optional(attrs, "created_at", table.get("created_at"))
    _set_optional(attrs, "updated_at", table.get("updated_at"))
    elem = etree.Element("table", **attrs)
    columns_elem = etree.SubElement(elem, "columns")
    for col in table.get("columns", []):
        c_attrs = {
            "name": col["name"], "type": col["type"], "length": str(col.get("length", "-")),
            "nullable": str(bool(col.get("nullable", True))).lower(),
            "primary_key": str(bool(col.get("primary_key"))).lower(),
            "foreign_key": str(bool(col.get("foreign_key"))).lower(),
            "unique": str(bool(col.get("unique"))).lower(),
            "auto_increment": str(bool(col.get("auto_increment"))).lower(),
            "index": str(bool(col.get("index"))).lower(),
            "uuid": col.get("uuid") or str(uuid_lib.uuid4()),
            "status": col.get("status", "ACTIVE"),
        }
        for key in ("internal_id", "references", "on_delete", "on_update", "default", "comment"):
            _set_optional(c_attrs, key, col.get(key))
        for key in ("creator_id", "creator_name", "created_at", "updated_at"):
            _set_optional(c_attrs, key, col.get(key))
        _set_optional(c_attrs, "next_auto_increment", col.get("next_auto_increment"))
        etree.SubElement(columns_elem, "column", **c_attrs)
    if table.get("constraints"):
        parent = etree.SubElement(elem, "constraints")
        for constraint in table["constraints"]:
            cattrs = {}
            _set_optional(cattrs, "name", constraint.get("name"))
            if constraint["kind"] == "foreign-key":
                cattrs.update({
                    "references_table": constraint["references_table"],
                    "references_columns": ",".join(constraint["references_columns"]),
                    "on_delete": constraint.get("on_delete", "NO ACTION"),
                    "on_update": constraint.get("on_update", "NO ACTION"),
                })
            c_elem = etree.SubElement(parent, constraint["kind"], **cattrs)
            for name in constraint.get("columns", []):
                etree.SubElement(c_elem, "column", name=name)
    if table.get("indexes"):
        parent = etree.SubElement(elem, "indexes")
        for index in table["indexes"]:
            i_elem = etree.SubElement(parent, "index", name=index["name"], unique=str(bool(index.get("unique"))).lower())
            for name in index.get("columns", []):
                etree.SubElement(i_elem, "column", name=name)
    rows_elem = etree.SubElement(elem, "rows")
    for row in table.get("rows", []):
        r_attrs = {"uuid": row.get("uuid") or str(uuid_lib.uuid4())}
        _set_optional(r_attrs, "internal_id", row.get("internal_id"))
        row_elem = etree.SubElement(rows_elem, "row", **r_attrs)
        for name, value in row.get("data", {}).items():
            if value is None:
                etree.SubElement(row_elem, "cell", column=name, null="true")
            else:
                cell = etree.SubElement(row_elem, "cell", column=name)
                cell.text = str(value)
    return elem


def serialize_document(document, pretty=True):
    validate_document(document)
    attrs = {
        "name": document["name"],
        "uuid": document.get("uuid") or str(uuid_lib.uuid4()),
        "description": document.get("description", ""),
        "comment": document.get("comment", ""),
        "status": document.get("status", "ACTIVE"),
        "scope": document.get("scope", "PERSONAL"),
        "version": str(max(1, int(document.get("version", 1)))),
        "generator": "XMLForge",
        "created_at": document.get("created_at") or datetime.utcnow().isoformat(),
        "author": document.get("author", ""),
    }
    for key in ("internal_id", "owner_id"):
        _set_optional(attrs, key, document.get(key))
    root = etree.Element("database", **attrs)
    for table in document.get("tables", []):
        root.append(_table_element(table))
    xml_bytes = etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=pretty)
    validate_xml_bytes(xml_bytes)
    return xml_bytes.decode("utf-8")


def serialize_table(table):
    elem = _table_element(table)
    xml_bytes = etree.tostring(elem, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    validate_xml_bytes(xml_bytes)
    return xml_bytes.decode("utf-8")
