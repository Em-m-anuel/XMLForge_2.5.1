"""Vues du Control Plane XML (Phase 6E).

Objets légers (dataclasses) exposant ``.to_dict()`` et les attributs consommés
par les services — sans ORM. Contrats REST/TCP stables.
"""

from __future__ import annotations

from datetime import datetime


def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class RoleView:
    __slots__ = ("id", "name", "description", "created_at")

    def __init__(self, id, name, description=None, created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}


class UserView:
    __slots__ = ("id", "full_name", "email", "password_hash", "created_at",
                 "updated_at", "is_active", "last_login", "token_version",
                 "role_id", "role_name")

    def __init__(self, id, full_name, email, password_hash, created_at=None,
                 updated_at=None, is_active=True, last_login=None,
                 token_version=1, role_id=None, role_name=None):
        self.id = id
        self.full_name = full_name
        self.email = email
        self.password_hash = password_hash
        self.created_at = created_at
        self.updated_at = updated_at
        self.is_active = is_active
        self.last_login = last_login
        self.token_version = token_version
        self.role_id = role_id
        self.role_name = role_name

    def is_admin(self):
        return bool(self.role_name and self.role_name.lower() == "admin")

    def is_archived(self):
        return not self.is_active

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "is_active": self.is_active,
            "last_login": _iso(self.last_login),
            "role": self.role_name or "user",
            "role_id": self.role_id,
            "is_admin": self.is_admin(),
        }
        if include_private:
            data["password_hash"] = "***"
        return data


class TcpCredentialView:
    __slots__ = ("id", "user_id", "tcp_username", "tcp_password", "tcp_host",
                 "tcp_port", "is_active", "created_at", "updated_at")

    def __init__(self, id, user_id, tcp_username, tcp_password, tcp_host="127.0.0.1",
                 tcp_port=3307, is_active=True, created_at=None, updated_at=None):
        self.id = id
        self.user_id = user_id
        self.tcp_username = tcp_username
        self.tcp_password = tcp_password
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "tcp_username": self.tcp_username,
            "tcp_host": self.tcp_host,
            "tcp_port": self.tcp_port,
            "is_active": self.is_active,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


class DatabaseView:
    __slots__ = ("id", "uuid", "name", "description", "creator_id", "creator_name",
                 "owner_id", "owner_name", "scope", "common_permission",
                 "document_version", "sync_status", "created_at", "updated_at",
                 "last_modified_by_id", "last_modified_by_name", "comment", "status",
                 "key_identifier", "xml_file_path", "projection_path", "tables_count")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def is_archived(self):
        return self.status == "ARCHIVED"

    def to_dict(self, include_key=False):
        data = {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "owner_id": self.owner_id or self.creator_id,
            "owner_name": self.owner_name or self.creator_name,
            "scope": self.scope or "PERSONAL",
            "common_permission": self.common_permission,
            "document_version": self.document_version or 1,
            "sync_status": self.sync_status or "PENDING",
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name,
            "comment": self.comment or "",
            "status": self.status,
            "tables_count": self.tables_count or 0,
        }
        if include_key:
            data["key_identifier"] = self.key_identifier
        return data


class DatabasePermissionView:
    __slots__ = ("id", "database_id", "user_id", "user_email", "user_name",
                 "can_read", "can_write", "can_ddl", "can_admin", "granted_by_id",
                 "created_at", "updated_at")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def to_dict(self):
        return {
            "id": self.id,
            "database_id": self.database_id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "user_name": self.user_name,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_ddl": self.can_ddl,
            "can_admin": self.can_admin,
            "granted_by_id": self.granted_by_id,
        }


class TablePermissionView:
    __slots__ = ("id", "table_id", "user_id", "database_id",
                 "can_read", "can_write", "can_ddl", "can_admin", "granted_by_id",
                 "created_at", "updated_at")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def to_dict(self):
        return {
            "id": self.id,
            "table_id": self.table_id,
            "user_id": self.user_id,
            "can_read": self.can_read,
            "can_write": self.can_write,
            "can_ddl": self.can_ddl,
            "can_admin": self.can_admin,
            "granted_by_id": self.granted_by_id,
        }


class TableView:
    __slots__ = ("id", "uuid", "name", "description", "database_id", "creator_id",
                 "creator_name", "created_at", "updated_at", "last_modified_by_id",
                 "last_modified_by_name", "comment", "status", "is_protected",
                 "file_identifier", "columns_count")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def is_archived(self):
        return self.status == "ARCHIVED"

    def get_required_key(self):
        return self.file_identifier or None

    def to_dict(self, include_secret=False):
        data = {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "database_id": self.database_id,
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name,
            "comment": self.comment or "",
            "status": self.status,
            "is_protected": self.is_protected,
            "has_file_identifier": bool(self.file_identifier),
            "protected": self.is_protected,
            "archived": self.is_archived(),
            "columns_count": self.columns_count or 0,
        }
        if include_secret:
            data["file_identifier"] = self.file_identifier or ""
        return data


class ColumnView:
    __slots__ = ("id", "uuid", "name", "type", "length", "nullable", "primary_key",
                 "foreign_key", "unique", "auto_increment", "default_value",
                 "references", "on_delete", "on_update", "indexed", "comment",
                 "status", "table_id")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def is_archived(self):
        return self.status == "ARCHIVED"

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "type": self.type,
            "length": self.length,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
            "foreign_key": self.foreign_key,
            "unique": self.unique,
            "auto_increment": self.auto_increment,
            "default": self.default_value,
            "references": self.references,
            "on_delete": self.on_delete or "NO ACTION",
            "on_update": self.on_update or "NO ACTION",
            "index": self.indexed,
            "comment": self.comment or "",
            "status": self.status,
            "table_id": self.table_id,
        }


class HistoryView:
    __slots__ = ("id", "uuid", "user_id", "user_name", "action_type", "element_type",
                 "element_name", "description", "ip_address", "before_data", "after_data",
                 "database_id", "table_id", "created_at")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def to_dict(self):
        created = _iso(self.created_at)
        return {
            "id": self.id,
            "uuid": self.uuid,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action_type": self.action_type,
            "element_type": self.element_type,
            "element_name": self.element_name,
            "description": self.description,
            "ip_address": self.ip_address,
            "before": self.before_data,
            "after": self.after_data,
            "database_id": self.database_id,
            "table_id": self.table_id,
            "created_at": created,
            "date": created,
        }


class AuditView:
    __slots__ = ("id", "uuid", "user_id", "user_name", "ip_address", "action",
                 "element_type", "element_name", "description", "meta_data", "timestamp")

    def __init__(self, **kw):
        for key in self.__slots__:
            setattr(self, key, kw.get(key))

    def to_dict(self):
        ts = _iso(self.timestamp)
        return {
            "id": self.id,
            "uuid": self.uuid,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "ip_address": self.ip_address,
            "action": self.action,
            "element_type": self.element_type,
            "element_name": self.element_name,
            "description": self.description,
            "meta_data": self.meta_data,
            "timestamp": ts,
            "created_at": ts,
        }
