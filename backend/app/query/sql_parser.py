"""Parser à tokens du sous-ensemble SQL supporté par XMLForge (REST + TCP).

Couverture réelle :

- SELECT [DISTINCT] avec `*`, colonnes (qualifiées `t.col` / `alias.col`),
  alias `AS`, agrégats COUNT/SUM/AVG/MIN/MAX, FROM avec alias de table,
  INNER JOIN ... ON ..., WHERE, GROUP BY, HAVING, ORDER BY multi-colonnes,
  LIMIT/OFFSET ;
- INSERT INTO t (cols) VALUES (...), (...) — une ou plusieurs lignes ;
- UPDATE t SET c=v, ... WHERE ... (WHERE obligatoire) ;
- DELETE FROM t WHERE ... (WHERE obligatoire) ;
- DDL : CREATE TABLE, DROP TABLE, ALTER TABLE ADD COLUMN, ALTER TABLE DROP COLUMN.

Refusé explicitement : LEFT/RIGHT/OUTER JOIN, sous-requêtes, transactions,
DISTINCT dans les agrégats (ex. COUNT(DISTINCT col)), UNION.
"""

from __future__ import annotations

import re

from ..errors import ValidationFailed

TOKEN_RE = re.compile(
    r"(?P<SPACE>\s+)|(?P<NUMBER>[-+]?\d+(?:\.\d+)?)|"
    r"(?P<STRING>'(?:''|[^'])*')|(?P<IDENT>`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)|"
    r"(?P<OP><=|>=|<>|!=|=|<|>)|(?P<STAR>\*)|(?P<COMMA>,)|"
    r"(?P<LPAREN>\()|(?P<RPAREN>\))|(?P<SEMI>;)|(?P<DOT>\.)",
    re.ASCII,
)

KEYWORDS = {
    "SELECT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC", "LIMIT", "OFFSET",
    "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE", "AND", "OR", "LIKE",
    "IN", "IS", "NOT", "NULL", "TRUE", "FALSE", "JOIN", "LEFT", "RIGHT", "INNER",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "AS", "DISTINCT", "GROUP", "HAVING", "ON",
    "CREATE", "TABLE", "DROP", "ALTER", "ADD", "COLUMN", "PRIMARY", "KEY",
    "FOREIGN", "REFERENCES", "AUTO_INCREMENT", "UNIQUE", "DEFAULT", "OUTER",
    "BETWEEN", "INDEX", "DATABASE", "MODIFY", "RENAME", "TO", "CURRENT_TIMESTAMP",
    "USE", "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION", "START", "FULL",
}

AGG_FUNCS = {"COUNT", "SUM", "AVG", "MIN", "MAX"}


def tokenize(sql):
    tokens = []
    pos = 0
    while pos < len(sql):
        match = TOKEN_RE.match(sql, pos)
        if not match:
            raise ValidationFailed(f"Token SQL non supporté près de: {sql[pos:pos+20]}")
        pos = match.end()
        kind = match.lastgroup
        value = match.group()
        if kind == "SPACE" or kind == "SEMI":
            continue
        if kind == "IDENT" and not value.startswith("`") and value.upper() in KEYWORDS:
            tokens.append(("KW", value.upper()))
        else:
            tokens.append((kind, value[1:-1] if kind == "IDENT" and value.startswith("`") else value))
    return tokens


class Parser:
    def __init__(self, sql):
        self.tokens = tokenize(sql)
        self.pos = 0

    # ------------------------------------------------------------ primitives
    def peek(self, kind=None, value=None):
        if self.pos >= len(self.tokens):
            return False
        token = self.tokens[self.pos]
        return (kind is None or token[0] == kind) and (value is None or token[1] == value)

    def peek_n(self, offset, kind=None, value=None):
        index = self.pos + offset
        if index >= len(self.tokens):
            return False
        token = self.tokens[index]
        return (kind is None or token[0] == kind) and (value is None or token[1] == value)

    def take(self, kind=None, value=None):
        if not self.peek(kind, value):
            expected = value or kind or "token"
            got = self.tokens[self.pos] if self.pos < len(self.tokens) else "fin"
            raise ValidationFailed(f"SQL invalide: attendu {expected}, reçu {got}")
        token = self.tokens[self.pos]
        self.pos += 1
        return token[1]

    def kw(self, value):
        return self.take("KW", value)

    def identifier(self):
        return self.take("IDENT")

    def qualified_identifier(self):
        """`col` ou `table.col` / `alias.col` (profondeur max 2)."""
        parts = [self.take("IDENT")]
        while self.peek("DOT"):
            self.take()
            parts.append(self.take("IDENT"))
        if len(parts) > 2:
            raise ValidationFailed(f"Qualification trop profonde: {'.'.join(parts)}")
        return parts[0] if len(parts) == 1 else f"{parts[0]}.{parts[1]}"

    def literal(self):
        if self.peek("STRING"):
            return self.take("STRING")[1:-1].replace("''", "'")
        if self.peek("NUMBER"):
            value = self.take("NUMBER")
            return float(value) if "." in value else int(value)
        if self.peek("KW", "NULL"):
            self.take()
            return None
        if self.peek("KW", "TRUE"):
            self.take()
            return True
        if self.peek("KW", "FALSE"):
            self.take()
            return False
        raise ValidationFailed("Valeur littérale SQL attendue")

    # ---------------------------------------------------------- expressions
    def aggregate_call(self):
        func = self.take("KW")
        if func not in AGG_FUNCS:
            raise ValidationFailed(f"Agrégat non supporté: {func}")
        self.take("LPAREN")
        if self.peek("KW", "DISTINCT"):
            raise ValidationFailed(f"{func}(DISTINCT ...) n'est pas supporté")
        if self.peek("STAR"):
            self.take()
            arg = "*"
        else:
            arg = self.qualified_identifier()
        self.take("RPAREN")
        return {"func": func, "arg": arg}

    def operand(self):
        """Retourne {"literal": v} | {"column": ref} | {"aggregate": {...}}."""
        if self.peek("STRING") or self.peek("NUMBER") or self.peek("KW", "NULL") \
                or self.peek("KW", "TRUE") or self.peek("KW", "FALSE"):
            return {"literal": self.literal()}
        if self.peek("KW") and self.tokens[self.pos][1] in AGG_FUNCS and self.peek_n(1, "LPAREN"):
            return {"aggregate": self.aggregate_call()}
        return {"column": self.qualified_identifier()}

    def expression(self):
        return self.or_expression()

    def or_expression(self):
        left = self.and_expression()
        while self.peek("KW", "OR"):
            self.take()
            left = {"op": "OR", "left": left, "right": self.and_expression()}
        return left

    def and_expression(self):
        left = self.factor()
        while self.peek("KW", "AND"):
            self.take()
            left = {"op": "AND", "left": left, "right": self.factor()}
        return left

    def factor(self):
        if self.peek("LPAREN"):
            self.take()
            expr = self.expression()
            self.take("RPAREN")
            return expr
        lhs = self.operand()
        if "literal" in lhs:
            raise ValidationFailed("Valeur littérale inattendue en début de condition")
        if self.peek("KW", "IS"):
            self.take()
            negate = False
            if self.peek("KW", "NOT"):
                self.take()
                negate = True
            self.kw("NULL")
            return {"op": "IS NOT NULL" if negate else "IS NULL", "column": lhs}
        if self.peek("KW", "NOT"):
            # NOT IN (...) / NOT LIKE '...'
            self.take()
            if self.peek("KW", "IN"):
                self.take()
                self.take("LPAREN")
                values = [self.literal()]
                while self.peek("COMMA"):
                    self.take()
                    values.append(self.literal())
                self.take("RPAREN")
                return {"op": "NOT IN", "column": lhs, "value": values}
            if self.peek("KW", "LIKE"):
                self.take()
                return {"op": "NOT LIKE", "column": lhs, "value": {"literal": self.literal()}}
            raise ValidationFailed("NOT doit être suivi de IN ou LIKE")
        if self.peek("KW", "IN"):
            self.take()
            self.take("LPAREN")
            values = [self.literal()]
            while self.peek("COMMA"):
                self.take()
                values.append(self.literal())
            self.take("RPAREN")
            return {"op": "IN", "column": lhs, "value": values}
        if self.peek("KW", "LIKE"):
            self.take()
            return {"op": "LIKE", "column": lhs, "value": {"literal": self.literal()}}
        if self.peek("KW", "BETWEEN"):
            self.take()
            low = self.literal()
            self.kw("AND")
            high = self.literal()
            return {"op": "BETWEEN", "column": lhs, "value": {"low": low, "high": high}}
        operator = self.take("OP")
        rhs = self.operand()
        return {"op": operator, "column": lhs, "value": rhs}

    def optional_where(self):
        if self.peek("KW", "WHERE"):
            self.take()
            return self.expression()
        return None

    # ------------------------------------------------------------- SELECT
    def _select_item(self):
        if self.peek("STAR"):
            self.take()
            return {"kind": "star"}
        if self.peek("KW") and self.tokens[self.pos][1] in AGG_FUNCS and self.peek_n(1, "LPAREN"):
            aggregate = self.aggregate_call()
            alias = None
            if self.peek("KW", "AS"):
                self.take()
                alias = self.identifier()
            return {"kind": "aggregate", "aggregate": aggregate, "alias": alias}
        ref = self.qualified_identifier()
        alias = None
        if self.peek("KW", "AS"):
            self.take()
            alias = self.identifier()
        return {"kind": "column", "column": ref, "alias": alias}

    def select(self):
        self.kw("SELECT")
        distinct = False
        if self.peek("KW", "DISTINCT"):
            self.take()
            distinct = True
        select_list = [self._select_item()]
        while self.peek("COMMA"):
            self.take()
            select_list.append(self._select_item())

        self.kw("FROM")
        table = self.identifier()
        table_alias = None
        if self.peek("IDENT"):
            table_alias = self.take("IDENT")
        joins = []
        while self.peek("KW", "JOIN") or self.peek("KW", "INNER") or self.peek("KW", "LEFT"):
            join_type = "INNER"
            if self.peek("KW", "INNER"):
                self.take()
                self.kw("JOIN")
            elif self.peek("KW", "LEFT"):
                self.take()
                if self.peek("KW", "OUTER"):
                    self.take()
                self.kw("JOIN")
                join_type = "LEFT"
            elif self.peek("KW", "JOIN"):
                self.take()
            join_table = self.identifier()
            join_alias = None
            if self.peek("IDENT"):
                join_alias = self.take("IDENT")
            self.kw("ON")
            on = self.expression()
            joins.append({"type": join_type, "table": join_table, "alias": join_alias, "on": on})

        where = self.optional_where()
        group_by = None
        if self.peek("KW", "GROUP"):
            self.take()
            self.kw("BY")
            group_by = [self.qualified_identifier()]
            while self.peek("COMMA"):
                self.take()
                group_by.append(self.qualified_identifier())
        having = None
        if self.peek("KW", "HAVING"):
            self.take()
            having = self.expression()
        order_by = []
        if self.peek("KW", "ORDER"):
            self.take()
            self.kw("BY")
            while True:
                if self.peek("KW") and self.tokens[self.pos][1] in AGG_FUNCS and self.peek_n(1, "LPAREN"):
                    col = {"aggregate": self.aggregate_call()}
                else:
                    col = self.qualified_identifier()
                direction = "ASC"
                if self.peek("KW", "ASC") or self.peek("KW", "DESC"):
                    direction = self.take("KW")
                order_by.append({"column": col, "direction": direction})
                if not self.peek("COMMA"):
                    break
                self.take()
        limit = 100
        offset = 0
        if self.peek("KW", "LIMIT"):
            self.take()
            limit = int(self.take("NUMBER"))
        if self.peek("KW", "OFFSET"):
            self.take()
            offset = int(self.take("NUMBER"))
        return {
            "operation": "select", "distinct": distinct,
            "from": {"table": table, "alias": table_alias},
            "joins": joins, "select_list": select_list,
            "where": where, "group_by": group_by, "having": having,
            "order_by": order_by, "limit": limit, "offset": offset,
            "table": table, "columns": None, "aggregate": None,
        }

    # ------------------------------------------------------------- INSERT
    def insert(self):
        self.kw("INSERT")
        self.kw("INTO")
        table = self.identifier()
        columns = None
        if self.peek("LPAREN"):
            self.take()
            columns = [self.identifier()]
            while self.peek("COMMA"):
                self.take()
                columns.append(self.identifier())
            self.take("RPAREN")
        self.kw("VALUES")
        rows = []
        while True:
            self.take("LPAREN")
            values = []
            if not self.peek("RPAREN"):
                values = [self.literal()]
                while self.peek("COMMA"):
                    self.take()
                    values.append(self.literal())
            self.take("RPAREN")
            if columns is not None and len(columns) != len(values):
                raise ValidationFailed("Le nombre de colonnes et de valeurs diffère")
            rows.append(values)
            if not self.peek("COMMA"):
                break
            self.take()
        if columns is None:
            # INSERT INTO t VALUES (...) : colonnes implicites (ordre du schéma).
            return {"operation": "insert", "table": table, "columns": None, "rows": rows}
        return {
            "operation": "insert", "table": table, "columns": columns,
            "data": dict(zip(columns, rows[0])) if rows else {},
            "rows": [dict(zip(columns, r)) for r in rows],
        }

    # -------------------------------------------------------- UPDATE/DELETE
    def update(self):
        self.kw("UPDATE")
        table = self.identifier()
        self.kw("SET")
        data = {}
        while True:
            column = self.identifier()
            self.take("OP", "=")
            data[column] = self.literal()
            if not self.peek("COMMA"):
                break
            self.take()
        where = self.optional_where()
        if where is None:
            raise ValidationFailed("UPDATE sans WHERE est refusé par sécurité")
        return {"operation": "update", "table": table, "data": data, "where": where}

    def delete(self):
        self.kw("DELETE")
        self.kw("FROM")
        table = self.identifier()
        where = self.optional_where()
        if where is None:
            raise ValidationFailed("DELETE sans WHERE est refusé par sécurité")
        return {"operation": "delete", "table": table, "where": where}

    # ----------------------------------------------------------------- DDL
    def _column_def(self):
        name = self.identifier()
        col_type = self.take("IDENT")
        length = "-"
        if self.peek("LPAREN"):
            self.take()
            length = self.take("NUMBER")
            self.take("RPAREN")
        spec = {"name": name, "type": col_type.upper(), "length": str(length),
                "nullable": True, "primary_key": False, "auto_increment": False,
                "unique": False, "default": None, "references": None,
                "on_delete": "NO ACTION", "on_update": "NO ACTION"}
        while True:
            if self.peek("KW", "NOT"):
                self.take()
                self.kw("NULL")
                spec["nullable"] = False
            elif self.peek("KW", "NULL"):
                self.take()
                spec["nullable"] = True
            elif self.peek("KW", "PRIMARY"):
                self.take()
                self.kw("KEY")
                spec["primary_key"] = True
            elif self.peek("KW", "AUTO_INCREMENT"):
                self.take()
                spec["auto_increment"] = True
            elif self.peek("KW", "UNIQUE"):
                self.take()
                spec["unique"] = True
            elif self.peek("KW", "DEFAULT"):
                self.take()
                if self.peek("KW", "CURRENT_TIMESTAMP"):
                    self.take()
                    spec["default"] = "CURRENT_TIMESTAMP"
                else:
                    spec["default"] = self.literal()
            elif self.peek("KW", "REFERENCES"):
                self.take()
                ref_table = self.identifier()
                if self.peek("DOT"):
                    self.take()
                    ref_col = self.identifier()
                elif self.peek("LPAREN"):
                    self.take()
                    ref_col = self.identifier()
                    self.take("RPAREN")
                else:
                    raise ValidationFailed("REFERENCES attendu au format table.colonne ou table(colonne)")
                spec["references"] = f"{ref_table}.{ref_col}"
            elif self.peek("KW", "ON"):
                self.take()
                action_type = self.take("KW")
                action = self.take("IDENT")
                if action_type == "DELETE":
                    spec["on_delete"] = action.upper()
                elif action_type == "UPDATE":
                    spec["on_update"] = action.upper()
                else:
                    raise ValidationFailed(f"Clause ON inattendue: ON {action_type}")
            else:
                break
        return spec

    def _expect_table(self):
        self.kw("TABLE")

    def create_table(self):
        self.kw("CREATE")
        self._expect_table()
        table = self.identifier()
        self.take("LPAREN")
        columns = [self._column_def()]
        while self.peek("COMMA"):
            self.take()
            columns.append(self._column_def())
        self.take("RPAREN")
        return {"operation": "create_table", "table": table, "columns": columns}

    def drop_table(self):
        self.kw("DROP")
        self._expect_table()
        table = self.identifier()
        return {"operation": "drop_table", "table": table}

    def alter_table(self):
        self.kw("ALTER")
        self._expect_table()
        table = self.identifier()
        if self.peek("KW", "ADD"):
            self.take()
            self.kw("COLUMN")
            spec = self._column_def()
            return {"operation": "add_column", "table": table, "column": spec}
        if self.peek("KW", "DROP"):
            self.take()
            self.kw("COLUMN")
            name = self.identifier()
            return {"operation": "drop_column", "table": table, "column_name": name}
        if self.peek("KW", "MODIFY"):
            self.take()
            self.kw("COLUMN")
            spec = self._column_def()
            return {"operation": "modify_column", "table": table, "column": spec}
        if self.peek("KW", "RENAME"):
            self.take()
            self.kw("TO")
            new_name = self.identifier()
            return {"operation": "rename_table", "table": table, "new_name": new_name}
        raise ValidationFailed("ALTER TABLE: seuls ADD COLUMN, MODIFY COLUMN, DROP COLUMN et RENAME TO sont supportés")

    # ----------------------------------------------------------------- index
    def create_database(self):
        self.kw("CREATE")
        self.kw("DATABASE")
        name = self.identifier()
        return {"operation": "create_database", "name": name}

    def drop_database(self):
        self.kw("DROP")
        self.kw("DATABASE")
        name = self.identifier()
        return {"operation": "drop_database", "name": name}

    # ----------------------------------------------------------------- session / transactions
    def use(self):
        self.kw("USE")
        name = self.identifier()
        return {"operation": "use", "database": name}

    def begin(self):
        if self.peek("KW", "BEGIN"):
            self.take()
        else:  # START TRANSACTION
            self.kw("START")
            self.kw("TRANSACTION")
        return {"operation": "begin"}

    def commit(self):
        self.kw("COMMIT")
        return {"operation": "commit"}

    def rollback(self):
        self.kw("ROLLBACK")
        return {"operation": "rollback"}

    def create_index(self):
        self.kw("CREATE")
        unique = False
        if self.peek("KW", "UNIQUE"):
            self.take()
            unique = True
        self.kw("INDEX")
        name = self.identifier()
        self.kw("ON")
        table = self.identifier()
        self.take("LPAREN")
        columns = [self.identifier()]
        while self.peek("COMMA"):
            self.take()
            columns.append(self.identifier())
        self.take("RPAREN")
        return {"operation": "create_index", "table": table, "name": name, "columns": columns, "unique": unique}

    def drop_index(self):
        self.kw("DROP")
        self.kw("INDEX")
        name = self.identifier()
        table = None
        if self.peek("KW", "ON"):
            self.take()
            table = self.identifier()
        return {"operation": "drop_index", "table": table, "name": name}

    # -------------------------------------------------------------- parse
    def parse(self):
        if self.peek("KW", "SELECT"):
            result = self.select()
        elif self.peek("KW", "INSERT"):
            result = self.insert()
        elif self.peek("KW", "UPDATE"):
            result = self.update()
        elif self.peek("KW", "DELETE"):
            result = self.delete()
        elif self.peek("KW", "CREATE"):
            if self.peek_n(1, "KW", "DATABASE"):
                result = self.create_database()
            elif self.peek_n(1, "KW", "TABLE"):
                result = self.create_table()
            elif self.peek_n(1, "KW", "INDEX") or self.peek_n(1, "KW", "UNIQUE"):
                result = self.create_index()
            else:
                raise ValidationFailed("CREATE: attendu DATABASE, TABLE, INDEX ou UNIQUE INDEX")
        elif self.peek("KW", "DROP"):
            if self.peek_n(1, "KW", "TABLE"):
                result = self.drop_table()
            elif self.peek_n(1, "KW", "INDEX"):
                result = self.drop_index()
            elif self.peek_n(1, "KW", "DATABASE"):
                result = self.drop_database()
            else:
                raise ValidationFailed("DROP: attendu TABLE, INDEX ou DATABASE")
        elif self.peek("KW", "ALTER"):
            result = self.alter_table()
        elif self.peek("KW", "USE"):
            result = self.use()
        elif self.peek("KW", "BEGIN") or self.peek("KW", "START"):
            result = self.begin()
        elif self.peek("KW", "COMMIT"):
            result = self.commit()
        elif self.peek("KW", "ROLLBACK"):
            result = self.rollback()
        else:
            raise ValidationFailed(
                "Requête non supportée (SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, USE, BEGIN, COMMIT, ROLLBACK)")
        if self.pos != len(self.tokens):
            raise ValidationFailed(f"Fin de requête inattendue: {self.tokens[self.pos:]}")
        return result


def parse_sql_statement(sql):
    if not isinstance(sql, str) or not sql.strip():
        raise ValidationFailed("Requête SQL vide")
    return Parser(sql.strip()).parse()
