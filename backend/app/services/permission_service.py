"""Autorisation centralisée pour REST, services internes et TCP.

Les données du plan de contrôle (users, bases, grants) sont lues/écrites via la
couche d'adaptation ``control_plane`` (backend XML, unique). Les tables,
colonnes et lignes (Data Plane) sont résolues via les documents XML.
"""
from ..control_plane import effective_common_permission, get_backend
from ..data_plane import get_table
from .audit_service import AuditService


class PermissionService:
    ACTION_TO_FIELD = {
        "read": "can_read",
        "write": "can_write",
        "ddl": "can_ddl",
        "admin": "can_admin",
        "delete": "can_admin",
    }

    @staticmethod
    def _common_access(database):
        """Accès collectif d'une base COMMON (aucun grant individuel requis)."""
        level = effective_common_permission(database)
        if level == "MANAGE":
            return {"can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "common"}
        if level == "EDIT":
            return {"can_read": True, "can_write": True, "can_ddl": False,
                    "can_admin": False, "level": "EDIT", "source": "common"}
        return {"can_read": True, "can_write": False, "can_ddl": False,
                "can_admin": False, "level": "VIEW", "source": "common"}

    @staticmethod
    def _user(user_or_id):
        if hasattr(user_or_id, "is_active") and hasattr(user_or_id, "id"):
            return user_or_id
        try:
            return get_backend().get_user(int(user_or_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _database(database_or_id):
        if hasattr(database_or_id, "owner_id") and hasattr(database_or_id, "id"):
            return database_or_id
        try:
            return get_backend().get_database(int(database_or_id))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _table(table_or_id):
        if (hasattr(table_or_id, "database_id") and hasattr(table_or_id, "id")
                and hasattr(table_or_id, "is_protected")):
            return table_or_id
        return get_table(table_or_id)

    @staticmethod
    def database_access(user_or_id, database_or_id):
        user = PermissionService._user(user_or_id)
        database = PermissionService._database(database_or_id)
        denied = {
            "can_read": False, "can_write": False, "can_ddl": False,
            "can_admin": False, "level": "NONE", "source": "none",
        }
        if not user or not user.is_active or not database:
            return denied
        if user.is_admin():
            return {**denied, "can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "role"}
        if PermissionService.is_owner(user, database):
            return {**denied, "can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "owner"}
        # COMMON : accès collectif selon common_permission (défaut VIEW).
        if getattr(database, "scope", None) == "COMMON":
            return PermissionService._common_access(database)
        permission = get_backend().get_database_permission(database.id, user.id)
        if not permission:
            return denied
        access = {
            "can_read": bool(permission.can_read),
            "can_write": bool(permission.can_write),
            "can_ddl": bool(permission.can_ddl),
            "can_admin": bool(permission.can_admin),
            "source": "shared",
        }
        access["level"] = "MANAGE" if access["can_admin"] else "EDIT" if access["can_write"] or access["can_ddl"] else "VIEW"
        return access

    @staticmethod
    def table_access(user_or_id, table_or_id):
        user = PermissionService._user(user_or_id)
        table = PermissionService._table(table_or_id)
        if not user or not table:
            return {"can_read": False, "can_write": False, "can_ddl": False,
                    "can_admin": False, "level": "NONE", "source": "none"}
        base_access = PermissionService.database_access(user, table.database_id)
        override = get_backend().get_table_permission(table.id, user.id)
        if not override or base_access["can_admin"]:
            return base_access
        access = {
            "can_read": base_access["can_read"] or bool(override.can_read),
            "can_write": base_access["can_write"] or bool(override.can_write),
            "can_ddl": base_access["can_ddl"] or bool(override.can_ddl),
            "can_admin": base_access["can_admin"] or bool(override.can_admin),
            "source": "table" if any((override.can_read, override.can_write,
                                      override.can_ddl, override.can_admin)) else base_access["source"],
        }
        access["level"] = "MANAGE" if access["can_admin"] else "EDIT" if access["can_write"] or access["can_ddl"] else "VIEW" if access["can_read"] else "NONE"
        return access

    @staticmethod
    def is_admin(user_or_id):
        user = PermissionService._user(user_or_id)
        return bool(user and user.is_active and user.is_admin())

    @staticmethod
    def is_owner(user_or_id, database):
        user = PermissionService._user(user_or_id)
        owner_id = database.owner_id or database.creator_id
        return bool(user and int(owner_id) == int(user.id))

    @staticmethod
    def can_database(user_or_id, database_or_id, action="read"):
        user = PermissionService._user(user_or_id)
        database = PermissionService._database(database_or_id)
        if not user or not user.is_active or not database:
            return False
        if user.is_admin() or PermissionService.is_owner(user, database):
            return True
        if getattr(database, "scope", None) == "COMMON":
            access = PermissionService._common_access(database)
            field = PermissionService.ACTION_TO_FIELD.get(action, "can_read")
            return bool(access.get(field, False))
        permission = get_backend().get_database_permission(database.id, user.id)
        field = PermissionService.ACTION_TO_FIELD.get(action, "can_read")
        return bool(permission and getattr(permission, field, False))

    @staticmethod
    def can_table(user_or_id, table_or_id, action="read"):
        user = PermissionService._user(user_or_id)
        table = PermissionService._table(table_or_id)
        if not user or not table:
            return False
        if PermissionService.can_database(user, table.database_id, action):
            return True
        override = get_backend().get_table_permission(table.id, user.id)
        field = PermissionService.ACTION_TO_FIELD.get(action, "can_read")
        return bool(override and getattr(override, field, False))

    @staticmethod
    def accessible_databases(user_or_id, include_archived=True):
        user = PermissionService._user(user_or_id)
        if not user or not user.is_active:
            return []
        candidates = get_backend().list_databases(include_archived=include_archived)
        return [d for d in candidates if PermissionService.can_database(user, d, "read")]

    @staticmethod
    def grant_database(actor_id, database_id, user_id, rights):
        database = PermissionService._database(database_id)
        target = get_backend().get_user(user_id)
        if not database:
            return None, "Base introuvable"
        if not target:
            return None, "Utilisateur introuvable"
        if not PermissionService.can_database(actor_id, database, "admin"):
            return None, "Permission d'administration de la base requise"
        if PermissionService.is_owner(target, database):
            return None, "Le propriétaire possède déjà tous les droits"
        if getattr(database, "scope", None) == "COMMON":
            return None, "Les bases COMMON utilisent un accès collectif (common_permission), pas de grants individuels"
        # Un droit supérieur implique la lecture.
        if rights.get("can_write") or rights.get("can_ddl") or rights.get("can_admin"):
            rights["can_read"] = True
        permission = get_backend().upsert_database_permission(
            database.id, user_id, rights, granted_by_id=actor_id)
        AuditService.log(user_id=actor_id, action="PARTAGE_BASE", element_type="base",
                         element_name=database.name,
                         meta={"database_id": database.id, "target_user_id": user_id, "rights": rights})
        return permission, None

    @staticmethod
    def revoke_database(actor_id, database_id, user_id):
        database = PermissionService._database(database_id)
        if not database:
            return False, "Base introuvable"
        if not PermissionService.can_database(actor_id, database, "admin"):
            return False, "Permission d'administration de la base requise"
        ok = get_backend().delete_database_permission(database.id, user_id)
        if not ok:
            return False, "Partage introuvable"
        AuditService.log(user_id=actor_id, action="RETRAIT_PARTAGE_BASE", element_type="base",
                         element_name=database.name,
                         meta={"database_id": database.id, "target_user_id": user_id})
        return True, None

    @staticmethod
    def list_database_permissions(actor_id, database_id):
        database = PermissionService._database(database_id)
        if not database:
            return None, "Base introuvable"
        if not PermissionService.can_database(actor_id, database, "admin"):
            return None, "Permission d'administration de la base requise"
        return get_backend().list_database_permissions(database_id), None

    @staticmethod
    def list_table_permissions(actor_id, table_id):
        table = PermissionService._table(table_id)
        if not table:
            return None, "Table introuvable"
        if not PermissionService.can_table(actor_id, table, "admin"):
            return None, "Permission d'administration de la table requise"
        return get_backend().list_table_permissions(table_id=table_id), None

    @staticmethod
    def grant_table(actor_id, table_id, user_id, rights):
        table = PermissionService._table(table_id)
        target = get_backend().get_user(user_id)
        if not table or not target:
            return None, "Table ou utilisateur introuvable"
        if not PermissionService.can_table(actor_id, table, "admin"):
            return None, "Permission d'administration de la table requise"
        database = get_backend().get_database(table.database_id)
        if database is not None and getattr(database, "scope", None) == "COMMON":
            return None, "Les bases COMMON utilisent un accès collectif (common_permission), pas de grants individuels"
        if rights.get("can_write") or rights.get("can_ddl") or rights.get("can_admin"):
            rights["can_read"] = True
        permission = get_backend().upsert_table_permission(
            table_id, user_id, rights, granted_by_id=actor_id, database_id=table.database_id)
        AuditService.log(user_id=actor_id, action="PARTAGE_TABLE", element_type="table",
                         element_name=table.name,
                         meta={"table_id": table_id, "target_user_id": user_id, "rights": rights})
        return permission, None

    @staticmethod
    def revoke_table(actor_id, table_id, user_id):
        table = PermissionService._table(table_id)
        if not table:
            return False, "Table introuvable"
        if not PermissionService.can_table(actor_id, table, "admin"):
            return False, "Permission d'administration de la table requise"
        ok = get_backend().delete_table_permission(table_id, user_id)
        if not ok:
            return False, "Permission table introuvable"
        AuditService.log(user_id=actor_id, action="RETRAIT_PARTAGE_TABLE", element_type="table",
                         element_name=table.name, meta={"table_id": table_id, "target_user_id": user_id})
        return True, None
