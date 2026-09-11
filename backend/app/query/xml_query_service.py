"""Service d'intégration : exécution des requêtes via le moteur XML natif.

Chemin de données 100% XML (Phase 6J-B) : lecture du document canonique,
mutations via ``XmlDataPlane.mutate`` (aucune projection, aucun ORM).
Métriques réelles (parse, lecture, exécution, écriture, total).
"""

from __future__ import annotations

import time

from ..data_plane import get_data_plane, resolve_table
from ..errors import NotFoundError, PermissionDenied, ValidationFailed
from ..services.permission_service import PermissionService
from ..services.unlock_service import UnlockService
from ..utils.helpers import now_utc
from ..xml_engine.xml_native import Timing, XmlNativeEngine
from .sql_parser import parse_sql_statement


def _now_ms():
    return time.perf_counter() * 1000.0


class XmlQueryService:
    @staticmethod
    def _resolve_table(database_id, table_name_or_id):
        table = resolve_table(database_id, table_name_or_id)
        if not table or table.status == "ARCHIVED":
            raise NotFoundError("Table active introuvable")
        return table

    @staticmethod
    def _authorize(user_id, table, action, provided_key=None):
        if not PermissionService.can_table(user_id, table.id, action):
            raise PermissionDenied(f"Permission {action} refusée sur la table {table.name}")
        if action in {"write", "ddl", "delete"} and table.is_protected:
            allowed, message = UnlockService.check_protection(user_id, table, provided_key)
            if not allowed:
                raise PermissionDenied(message)

    @staticmethod
    def _authorize_tables(database_id, user_id, statement, action):
        table = XmlQueryService._resolve_table(database_id, statement["from"]["table"])
        XmlQueryService._authorize(user_id, table, action)
        for join in statement.get("joins", []):
            joined = XmlQueryService._resolve_table(database_id, join["table"])
            XmlQueryService._authorize(user_id, joined, action)
        return table

    @staticmethod
    def _run_read(database_id, user_id, statement, timing):
        from ..control_plane import get_backend
        if get_backend().get_database(database_id) is None:
            raise NotFoundError("Base introuvable")
        XmlQueryService._authorize_tables(database_id, user_id, statement, "read")
        start = _now_ms()
        document = get_data_plane().read_document(database_id)
        timing.read_ms += _now_ms() - start
        engine = XmlNativeEngine(document=document)
        return engine.select_statement(statement, timing=timing)

    @staticmethod
    def _run_write(database_id, user_id, statement, provided_key, expected_version, timing):
        from ..control_plane import get_backend
        database = get_backend().get_database(database_id)
        if not database:
            raise NotFoundError("Base introuvable")
        table = XmlQueryService._resolve_table(database_id, statement["table"])
        XmlQueryService._authorize(user_id, table, "write", provided_key)
        operation = statement["operation"]
        table_name = statement["table"]
        holder = {}

        def mutation(document):
            engine = XmlNativeEngine(document=document)
            if operation == "insert":
                rows = engine.resolve_insert_rows(table_name, statement)
                if len(rows) == 1:
                    holder["result"] = engine.insert(table_name, rows[0], timing=timing)
                    tdoc = engine.table(table_name)
                    row = tdoc["rows"][-1]
                    row["internal_id"] = get_data_plane().allocate_object_id()
                    holder["result"]["internal_id"] = row["internal_id"]
                else:
                    holder["result"] = engine.insert_many(table_name, rows, timing=timing)
                    tdoc = engine.table(table_name)
                    for row in tdoc["rows"][-len(rows):]:
                        row["internal_id"] = get_data_plane().allocate_object_id()
            elif operation == "update":
                holder["result"] = engine.update(table_name, statement["data"],
                                                 where=statement.get("where"), timing=timing)
            elif operation == "delete":
                holder["result"] = engine.delete(table_name, where=statement.get("where"), timing=timing)
            else:
                raise ValidationFailed(f"Écriture non supportée par le moteur XML: {operation}")
            return None

        start = _now_ms()
        get_data_plane().mutate(database_id, mutation, expected_version=expected_version)
        timing.write_ms += _now_ms() - start

        result = holder.get("result", {})
        if operation == "insert" and len(statement.get("rows") or [statement.get("data")]) == 1:
            return {"inserted": 1, "row": result}
        if operation == "insert":
            return {"inserted": result.get("inserted", len(statement.get("rows") or []))}
        return result

    @staticmethod
    def _run_ddl(database_id, user_id, statement, provided_key, expected_version, timing):
        from ..control_plane import get_backend
        database = get_backend().get_database(database_id)
        if not database:
            raise NotFoundError("Base introuvable")
        operation = statement["operation"]
        target_table = statement["table"] if "table" in statement else None
        if operation == "create_table":
            if not PermissionService.can_database(user_id, database_id, "ddl"):
                raise PermissionDenied(f"Permission ddl refusée sur la base {database.name}")
        elif operation == "drop_index":
            if target_table:
                table = XmlQueryService._resolve_table(database_id, target_table)
                if not table:
                    raise NotFoundError("Table active introuvable")
                XmlQueryService._authorize(user_id, table, "ddl", provided_key)
            elif not PermissionService.can_database(user_id, database_id, "ddl"):
                raise PermissionDenied(f"Permission ddl refusée sur la base {database.name}")
        else:
            table = XmlQueryService._resolve_table(database_id, target_table)
            if not table:
                raise NotFoundError("Table active introuvable")
            XmlQueryService._authorize(user_id, table, "ddl", provided_key)

        holder = {}

        def mutation(document):
            engine = XmlNativeEngine(document=document)
            if operation == "create_table":
                engine.create_table(statement["table"], columns=statement.get("columns"))
                tdoc = engine.table(statement["table"])
                tdoc["internal_id"] = get_data_plane().allocate_object_id()
                tdoc["creator_id"] = user_id
                from ..control_plane import get_backend
                actor = get_backend().get_user(user_id)
                tdoc["creator_name"] = actor.full_name if actor else None
                tdoc["created_at"] = now_utc().isoformat()
                tdoc["updated_at"] = now_utc().isoformat()
                holder["result"] = {"created": statement["table"]}
            elif operation == "drop_table":
                engine.drop_table(statement["table"])
                holder["result"] = {"dropped": statement["table"]}
            elif operation == "add_column":
                engine.add_column(statement["table"], statement["column"])
                tdoc = engine.table(statement["table"])
                col = next(c for c in tdoc["columns"] if c["name"] == statement["column"]["name"])
                col["internal_id"] = get_data_plane().allocate_object_id()
                col["creator_id"] = user_id
                col["created_at"] = now_utc().isoformat()
                col["updated_at"] = now_utc().isoformat()
                holder["result"] = {"added": statement["column"]["name"], "table": statement["table"]}
            elif operation == "drop_column":
                engine.drop_column(statement["table"], statement["column_name"])
                holder["result"] = {"dropped_column": statement["column_name"], "table": statement["table"]}
            elif operation == "modify_column":
                engine.modify_column(statement["table"], statement["column"]["name"], statement["column"])
                holder["result"] = {"modified": statement["column"]["name"], "table": statement["table"]}
            elif operation == "rename_table":
                engine.rename_table(statement["table"], statement["new_name"])
                holder["result"] = {"renamed": statement["table"], "new_name": statement["new_name"]}
            elif operation == "create_index":
                index = engine.create_index(statement["table"], statement["name"],
                                            statement["columns"], unique=statement.get("unique", False))
                holder["result"] = {"index": index}
            elif operation == "drop_index":
                engine.drop_index(statement.get("table"), statement["name"])
                holder["result"] = {"dropped_index": statement["name"]}
            return None

        start = _now_ms()
        get_data_plane().mutate(database_id, mutation, expected_version=expected_version)
        timing.write_ms += _now_ms() - start
        return holder["result"]

    @staticmethod
    def execute_sql(database_id, user_id, sql, *, provided_key=None, expected_version=None):
        timing = Timing(engine="xml")
        start = _now_ms()
        statement = parse_sql_statement(sql)
        timing.parse_ms = _now_ms() - start

        try:
            from flask import current_app, has_app_context
            if has_app_context():
                current_app.logger.info(
                    "[QUERY] engine=xml operation=%s database=%s table=%s",
                    statement["operation"].upper(), database_id, statement.get("table") or "-")
        except Exception:
            pass

        operation = statement["operation"]
        if operation == "select":
            result = XmlQueryService._run_read(database_id, user_id, statement, timing)
            select_list = statement.get("select_list") or []
            if (len(select_list) == 1 and select_list[0].get("kind") == "aggregate"
                    and select_list[0]["aggregate"]["func"] == "COUNT"
                    and not statement.get("group_by")):
                agg = select_list[0]["aggregate"]
                alias = select_list[0].get("alias")
                key = alias or f"COUNT({agg['arg']})"
                count_value = result["rows"][0].get(key) if result["rows"] else 0
                result = {"count": count_value, "table": statement["table"]}
        elif operation in {"insert", "update", "delete"}:
            result = XmlQueryService._run_write(database_id, user_id, statement, provided_key,
                                                expected_version, timing)
        elif operation in {"create_table", "drop_table", "add_column", "drop_column",
                           "modify_column", "rename_table", "create_index", "drop_index"}:
            result = XmlQueryService._run_ddl(database_id, user_id, statement, provided_key,
                                              expected_version, timing)
        elif operation == "create_database":
            from ..services.database_service import DatabaseService
            from ..services.auth_service import AuthService
            user = AuthService.get_user_by_id(user_id)
            if not user:
                raise NotFoundError("Utilisateur introuvable")
            database = DatabaseService.create(
                name=statement["name"], description="", creator_id=user.id,
                creator_name=user.full_name, ip_address=None, scope="PERSONAL")
            result = {"created": statement["name"], "database_id": database.id}
        elif operation == "drop_database":
            from ..services.database_service import DatabaseService
            from ..services.auth_service import AuthService
            from ..services.permission_service import PermissionService
            user = AuthService.get_user_by_id(user_id)
            if not user:
                raise NotFoundError("Utilisateur introuvable")
            database = DatabaseService.get_database_by_name_any_user(statement["name"])
            if not database:
                raise NotFoundError(f"Base '{statement['name']}' introuvable")
            if not PermissionService.can_database(user_id, database.id, "admin"):
                raise PermissionDenied(f"Permission d'administration de la base '{statement['name']}' requise")
            ok, error = DatabaseService.delete(database.id, user.id, user.full_name)
            if not ok:
                raise ValidationFailed(error or "Suppression de base impossible")
            result = {"dropped": statement["name"], "database_id": database.id}
        elif operation in ("use", "begin", "commit", "rollback"):
            raise ValidationFailed(
                f"'{operation.upper()}' est géré au niveau de la session TCP (REST est sans état)")
        else:
            raise ValidationFailed(f"Opération non supportée par le moteur XML: {operation}")

        timing.total_ms = _now_ms() - start
        return {"result": result, "metrics": timing.to_dict()}
