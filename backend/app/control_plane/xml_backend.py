"""Backend XML du Control Plane (Phase 6E).

Utilise exclusivement ``XmlControlPlaneService`` + records + XSD : **aucune
dépendance SQLAlchemy**. Fail-closed (fichiers absents/corrompus → erreur).
"""

from __future__ import annotations

import os
from datetime import datetime

from ..errors import ControlPlaneIntegrityError
from ..xml_control import records as R
from ..xml_control.service import XmlControlPlaneService
from . import views


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _now_iso():
    return datetime.utcnow().isoformat()


class XmlControlPlane:
    name = "xml"

    def __init__(self, storage_folder, common_permission_default="VIEW",
                 audit_retention_months=24, audit_compress=True):
        self.storage_folder = storage_folder
        self.audit_retention_months = int(audit_retention_months or 24)
        self.audit_compress = bool(audit_compress)
        self._service = XmlControlPlaneService(
            storage_folder=storage_folder,
            common_permission_default=common_permission_default)

    @classmethod
    def from_config(cls, config):
        return cls(storage_folder=config.get("CONTROL_STORAGE_FOLDER"),
                   common_permission_default=config.get("COMMON_PERMISSION_DEFAULT", "VIEW"),
                   audit_retention_months=config.get("AUDIT_RETENTION_MONTHS", 24),
                   audit_compress=config.get("AUDIT_COMPRESS_OLD_MONTHS", True))

    def _security(self):
        return self._service._load_security()

    @staticmethod
    def _int_id(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _role_name(self, role_id):
        role = self._service.get_role(self._int_id(role_id))
        return role.name if role else None

    # ---------------------------------------------------------------- users
    def _user_view(self, record):
        if record is None:
            return None
        return views.UserView(
            id=record.internal_id, full_name=record.full_name, email=record.email,
            password_hash=record.password_hash, created_at=record.created_at,
            updated_at=record.updated_at, is_active=record.is_active,
            last_login=record.last_login, token_version=record.token_version,
            role_id=record.role_id, role_name=self._role_name(record.role_id))

    def get_user(self, user_id):
        return self._user_view(self._service.get_user(self._int_id(user_id)))

    def get_user_by_email(self, email):
        return self._user_view(self._service.get_user_by_email(email))

    def list_users(self, search=None, include_inactive=True):
        users = [self._user_view(u) for u in self._service.list_users()]
        if search:
            needle = search.lower()
            users = [u for u in users if needle in (u.email or "").lower()
                     or needle in (u.full_name or "").lower()]
        if not include_inactive:
            users = [u for u in users if u.is_active]
        users.sort(key=lambda u: (u.created_at is None, u.created_at or ""), reverse=True)
        return users

    def _next_internal_id(self, records, attr="internal_id"):
        ids = [getattr(r, attr) for r in records if getattr(r, attr) is not None]
        return (max(ids) + 1) if ids else 1

    def insert_user(self, full_name, email, password_hash, role_id, is_active=True,
                    token_version=1, created_at=None, updated_at=None, internal_id=None):
        record = R.UserRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            email=email, role_id=role_id,
            full_name=full_name, password_hash=password_hash, is_active=is_active,
            token_version=token_version, created_at=_iso(created_at),
            updated_at=_iso(updated_at))
        self._service.create_user(record)
        return self._user_view(record)

    def update_user_fields(self, user_id, changes):
        user_id = self._int_id(user_id)
        record = self._service.get_user(user_id)
        if record is None:
            return None
        record.full_name = changes.get("full_name", record.full_name)
        record.email = changes.get("email", record.email)
        record.is_active = changes.get("is_active", record.is_active)
        record.role_id = changes.get("role_id", record.role_id)
        record.token_version = changes.get("token_version", record.token_version)
        record.password_hash = changes.get("password_hash", record.password_hash)
        record.last_login = _iso(changes.get("last_login", record.last_login))
        record.updated_at = _iso(changes.get("updated_at", record.updated_at))
        self._service.update_user(record)
        return self._user_view(record)

    def delete_user(self, user_id):
        self._service.delete_user(self._int_id(user_id))
        return True

    # ---------------------------------------------------------------- roles
    def _role_view(self, record):
        if record is None:
            return None
        return views.RoleView(id=record.internal_id, name=record.name,
                              description=record.description, created_at=record.created_at)

    def get_role(self, role_id):
        return self._role_view(self._service.get_role(self._int_id(role_id)))

    def get_role_by_name(self, name):
        return self._role_view(self._service.get_role_by_name(name))

    def list_roles(self):
        return [self._role_view(r) for r in self._service.list_roles()]

    def ensure_role(self, name, description=""):
        role = self._service.get_role_by_name(name)
        if role is None:
            role = self.insert_role((name or "").lower(), description)
        return role

    def insert_role(self, name, description="", created_at=None, internal_id=None):
        record = R.RoleRecord(
            internal_id=internal_id if internal_id is not None else self._next_internal_id(self._service.list_roles()),
                              name=(name or "").lower(), description=description,
                              created_at=_iso(created_at))
        self._service.create_role(record)
        return self._role_view(record)

    def update_role_fields(self, role_id, changes):
        role_id = self._int_id(role_id)
        record = self._service.get_role(role_id)
        if record is None:
            return None
        record.name = changes.get("name", record.name)
        record.description = changes.get("description", record.description)
        self._service.update_role(record)
        return self._role_view(record)

    def count_active_admins(self):
        users = self._service.list_users()
        return sum(1 for u in users if u.is_active and self._role_name(u.role_id) == "admin")

    # ------------------------------------------------------------- databases
    def _tables_count(self, xml_file_path):
        if not xml_file_path:
            return 0
        try:
            from ..xml_engine.document import parse_document
            with open(xml_file_path, "rb") as stream:
                document = parse_document(stream.read(), validate=False)
            return len(document.get("tables", []))
        except Exception:
            return 0

    def _database_view(self, record):
        if record is None:
            return None
        creator_name = (self._service.get_user(record.creator_id) or None)
        creator_name = creator_name.full_name if creator_name else None
        owner_id = record.owner_id or record.creator_id
        owner_name = None
        if owner_id is not None:
            owner = self._service.get_user(owner_id)
            owner_name = owner.full_name if owner else None
        return views.DatabaseView(
            id=record.internal_id, uuid=record.uuid, name=record.name,
            description=record.description, creator_id=record.creator_id,
            creator_name=creator_name, owner_id=record.owner_id, owner_name=owner_name,
            scope=record.scope.value if isinstance(record.scope, R.Scope) else record.scope,
            common_permission=(record.common_permission.value
                               if isinstance(record.common_permission, R.CommonPermission)
                               else record.common_permission),
            document_version=record.document_version, sync_status=record.sync_status,
            created_at=record.created_at, updated_at=record.updated_at,
            last_modified_by_id=record.last_modified_by_id,
            last_modified_by_name=record.last_modified_by_name,
            comment=record.comment, status=record.status,
            key_identifier=record.key_identifier, xml_file_path=record.xml_file_path,
            projection_path=record.projection_path,
            tables_count=self._tables_count(record.xml_file_path))

    def get_database(self, database_id):
        return self._database_view(self._service.get_database(self._int_id(database_id)))

    def get_database_by_key(self, key_identifier):
        record = next((d for d in self._service.list_databases()
                       if d.key_identifier == key_identifier), None)
        return self._database_view(record)

    def list_databases(self, include_archived=True):
        records = self._service.list_databases()
        if not include_archived:
            records = [d for d in records if d.status == "ACTIVE"]
        views_list = [self._database_view(d) for d in records]
        views_list.sort(key=lambda d: (d.updated_at is None, d.updated_at or ""), reverse=True)
        return views_list

    def mirror_database(self, record):
        if self._service.get_database(record.internal_id) is None:
            self._service.create_database(record)
        else:
            self._service.update_database(record)
        return record

    def mirror_database_update(self, record):
        self._service.update_database(record)
        return record

    def mirror_database_delete(self, database_id):
        self._service.delete_database(self._int_id(database_id))
        return True

    # ------------------------------------------------------------ permissions
    def _perm_view(self, record):
        if record is None:
            return None
        user = self._service.get_user(record.user_id)
        return views.DatabasePermissionView(
            id=record.internal_id, database_id=record.database_id, user_id=record.user_id,
            user_email=user.email if user else None,
            user_name=user.full_name if user else None,
            can_read=record.can_read, can_write=record.can_write,
            can_ddl=record.can_ddl, can_admin=record.can_admin,
            granted_by_id=record.granted_by_id, created_at=record.created_at,
            updated_at=record.updated_at)

    def get_database_permission(self, database_id, user_id):
        items = self._service.list_database_permissions(database_id=database_id, user_id=user_id)
        return self._perm_view(items[0]) if items else None

    def list_database_permissions(self, database_id=None):
        return [self._perm_view(p) for p in self._service.list_database_permissions(database_id=database_id)]

    def upsert_database_permission(self, database_id, user_id, rights, granted_by_id=None,
                                   internal_id=None):
        existing = self._service.list_database_permissions(database_id=database_id, user_id=user_id)
        if existing:
            record = existing[0]
            for field in ("can_read", "can_write", "can_ddl", "can_admin"):
                if field in rights:
                    setattr(record, field, bool(rights[field]))
            record.granted_by_id = granted_by_id
            self._service.update_database_permission(record)
            return self._perm_view(record)
        record = R.DatabasePermissionRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            database_id=database_id, user_id=user_id,
            can_read=bool(rights.get("can_read", False)),
            can_write=bool(rights.get("can_write", False)),
            can_ddl=bool(rights.get("can_ddl", False)),
            can_admin=bool(rights.get("can_admin", False)),
            granted_by_id=granted_by_id)
        self._service.create_database_permission(record)
        return self._perm_view(record)

    def delete_database_permission(self, database_id, user_id):
        existing = self._service.list_database_permissions(database_id=database_id, user_id=user_id)
        if not existing:
            return False
        self._service.delete_database_permission(existing[0].internal_id)
        return True

    def _table_perm_view(self, record):
        if record is None:
            return None
        return views.TablePermissionView(
            id=record.internal_id, table_id=record.table_id, user_id=record.user_id,
            database_id=record.database_id, can_read=record.can_read,
            can_write=record.can_write, can_ddl=record.can_ddl, can_admin=record.can_admin,
            granted_by_id=record.granted_by_id, created_at=record.created_at,
            updated_at=record.updated_at)

    def get_table_permission(self, table_id, user_id):
        items = self._service.list_table_permissions(table_id=table_id, user_id=user_id)
        return self._table_perm_view(items[0]) if items else None

    def list_table_permissions(self, table_id=None):
        return [self._table_perm_view(p) for p in self._service.list_table_permissions(table_id=table_id)]

    def upsert_table_permission(self, table_id, user_id, rights, granted_by_id=None,
                                database_id=None, internal_id=None):
        existing = self._service.list_table_permissions(table_id=table_id, user_id=user_id)
        if existing:
            record = existing[0]
            for field in ("can_read", "can_write", "can_ddl", "can_admin"):
                if field in rights:
                    setattr(record, field, bool(rights[field]))
            record.granted_by_id = granted_by_id
            if database_id is not None:
                record.database_id = database_id
            self._service.update_table_permission(record)
            return self._table_perm_view(record)
        record = R.TablePermissionRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            table_id=table_id, user_id=user_id, database_id=database_id,
            can_read=bool(rights.get("can_read", False)),
            can_write=bool(rights.get("can_write", False)),
            can_ddl=bool(rights.get("can_ddl", False)),
            can_admin=bool(rights.get("can_admin", False)),
            granted_by_id=granted_by_id)
        self._service.create_table_permission(record)
        return self._table_perm_view(record)

    def delete_table_permission(self, table_id, user_id):
        existing = self._service.list_table_permissions(table_id=table_id, user_id=user_id)
        if not existing:
            return False
        self._service.delete_table_permission(existing[0].internal_id)
        return True

    # ---------------------------------------------------------- TCP credentials
    def _cred_view(self, record):
        if record is None:
            return None
        return views.TcpCredentialView(
            id=record.internal_id, user_id=record.user_id, tcp_username=record.tcp_username,
            tcp_password=record.tcp_password, tcp_host=record.tcp_host,
            tcp_port=record.tcp_port, is_active=record.is_active,
            created_at=record.created_at, updated_at=record.updated_at)

    def get_tcp_credential_by_user(self, user_id):
        user_id = self._int_id(user_id)
        return self._cred_view(next((c for c in self._service.list_tcp_credentials()
                                     if c.user_id == user_id), None))

    def get_tcp_credential_by_username(self, tcp_username):
        return self._cred_view(self._service.get_tcp_credential_by_username(tcp_username))

    def list_tcp_credentials(self):
        return [self._cred_view(c) for c in self._service.list_tcp_credentials()]

    def insert_tcp_credential(self, user_id, tcp_username, tcp_password_hash,
                              tcp_host="127.0.0.1", tcp_port=3307, is_active=True,
                              created_at=None, updated_at=None, internal_id=None):
        user_id = self._int_id(user_id)
        record = R.TcpCredentialRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            user_id=user_id, tcp_username=tcp_username, tcp_password=tcp_password_hash,
            tcp_host=tcp_host, tcp_port=tcp_port, is_active=is_active,
            created_at=_iso(created_at), updated_at=_iso(updated_at))
        self._service.create_tcp_credential(record)
        return self._cred_view(record)

    def update_tcp_credential_fields(self, credential_id, changes):
        credential_id = self._int_id(credential_id)
        record = self._service.get_tcp_credential(credential_id)
        if record is None:
            return None
        for key, value in changes.items():
            setattr(record, key, value)
        self._service.update_tcp_credential(record)
        return self._cred_view(record)

    def delete_tcp_credential(self, credential_id):
        self._service.delete_tcp_credential(self._int_id(credential_id))
        return True

    # ------------------------------------------------------------- history
    def _history_view(self, record):
        if record is None:
            return None
        return views.HistoryView(
            id=record.internal_id, uuid=record.uuid, user_id=record.user_id,
            user_name=record.user_name, action_type=record.action_type,
            element_type=record.element_type, element_name=record.element_name,
            description=record.description, ip_address=record.ip_address,
            before_data=record.before_data, after_data=record.after_data,
            database_id=record.database_id, table_id=record.table_id,
            created_at=record.created_at)

    def list_history(self, limit=100, database_id=None):
        entries = [self._history_view(e) for e in self._service.list_history(database_id=database_id)]
        entries.sort(key=lambda e: (e.created_at is None, e.created_at or ""), reverse=True)
        return entries[:limit]

    def add_history(self, user_id, user_name, action_type, element_type, element_name,
                    description="", database_id=None, table_id=None, ip_address=None,
                    before=None, after=None, created_at=None, internal_id=None):
        import json as _json
        record = R.HistoryRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            user_id=user_id, user_name=user_name,
            action_type=action_type, element_type=element_type, element_name=element_name,
            created_at=_iso(created_at) or _now_iso(), description=description,
            ip_address=ip_address, database_id=database_id, table_id=table_id,
            before_data=_json.dumps(before, ensure_ascii=False) if before is not None else None,
            after_data=_json.dumps(after, ensure_ascii=False) if after is not None else None)
        self._service.add_history(record)
        return self._history_view(record)

    # --------------------------------------------------------------- audit
    def _audit_view(self, record):
        if record is None:
            return None
        return views.AuditView(
            id=record.internal_id, uuid=record.uuid, user_id=record.user_id,
            user_name=record.user_name, ip_address=record.ip_address, action=record.action,
            element_type=record.element_type, element_name=record.element_name,
            description=record.description, meta_data=record.meta_data,
            timestamp=record.timestamp)

    def list_audit(self, limit=100):
        entries = [self._audit_view(e) for e in self._service.list_audit()]
        entries.sort(key=lambda e: (e.timestamp is None, e.timestamp or ""), reverse=True)
        return entries[:limit]

    def add_audit(self, user_id=None, user_name=None, ip_address=None, action="",
                  element_type=None, element_name=None, description="", meta=None,
                  timestamp=None, internal_id=None):
        import json as _json
        ts = timestamp or datetime.utcnow()
        month = ts.strftime("%Y-%m") if isinstance(ts, datetime) else str(ts)[:7]
        # Rotation : à la création d'un nouveau mois, appliquer la politique
        # (compression des mois anciens + purge au-delà de la rétention).
        new_month = self._service._audit_file(month) is None
        record = R.AuditRecord(
            internal_id=internal_id,  # None -> allocation sous verrou par le service
            action=action,
            timestamp=_iso(ts), user_id=user_id, user_name=user_name,
            ip_address=ip_address, element_type=element_type, element_name=element_name,
            description=description,
            meta_data=_json.dumps(meta, ensure_ascii=False) if meta is not None else None)
        self._service.add_audit(record, month)
        if new_month:
            self._service.audit_policy(
                retention_months=self.audit_retention_months, compress=self.audit_compress)
        return self._audit_view(record)
