"""Modèles du Control Plane XML — Phase 6B.

Structures de données Python (dataclasses + enums) représentant les documents
XML du plan de contrôle, avec sérialisation/désérialisation et validation XSD.

- Indépendant de Flask et de SQLAlchemy : n'importe que ``lxml``, le module
  ``store`` (Phase 6A) et les erreurs métier.
- Aucune logique métier (auth, ACL, CRUD) ici : uniquement représentation,
  conversion XML <-> records et validation.
- ``internal_id`` = ancien identifiant SQLAlchemy (conservé) ; ``uuid``
  optionnel (backfill en 6C). L'un ne remplace jamais l'autre.
- Représentation de NULL : attribut/élément **absent**. Une chaîne vide reste
  une chaîne vide ; rien n'est transformé en "" ni en "NULL".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

from lxml import etree

from . import store
from .. import paths

XSD_DIR = os.path.join(paths.static_dir(), "control")


def schema_path(name):
    return os.path.join(XSD_DIR, name)


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"true", "1", "yes"}


def _bool_str(value):
    return "true" if value else "false"


def _set_opt(elem, attr, value):
    if value is not None:
        elem.set(attr, str(value))


def _get_int(elem, attr):
    value = elem.get(attr)
    return int(value) if value is not None else None


def _get_bool(elem, attr, default=False):
    return _as_bool(elem.get(attr), default)


def _get_str(elem, attr):
    value = elem.get(attr)
    return value if value is not None else None


def _text_child(parent, tag, text):
    if text is None:
        return None
    child = etree.SubElement(parent, tag)
    child.text = text
    return child


def _cdata_child(parent, tag, text):
    if text is None:
        return None
    child = etree.SubElement(parent, tag)
    child.text = etree.CDATA(text)
    return child


def _child_text(elem, tag):
    """Texte d'un enfant ; ``None`` si l'élément est absent (NULL), sinon str."""
    child = elem.find(tag)
    if child is None:
        return None
    return child.text or ""


def _serialize(root, xsd, *, validate):
    data = etree.tostring(root, encoding="UTF-8", xml_declaration=True, pretty_print=True)
    if validate:
        store.validate_bytes(data, store.cached_schema(xsd))
    return data


def _deserialize(data, xsd, *, validate):
    root = store.parse_safely(data)
    if validate:
        store.validate_bytes(etree.tostring(root, encoding="UTF-8"), store.cached_schema(xsd))
    return root


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class Scope(str, Enum):
    PERSONAL = "PERSONAL"
    COMMON = "COMMON"


class CommonPermission(str, Enum):
    VIEW = "VIEW"
    EDIT = "EDIT"
    MANAGE = "MANAGE"


def _to_scope(value):
    if isinstance(value, Scope):
        return value
    return Scope(str(value).upper())


def _to_common_permission(value):
    if value is None or isinstance(value, CommonPermission):
        return value
    return CommonPermission(str(value).upper())


# --------------------------------------------------------------------------
# security.xml
# --------------------------------------------------------------------------

@dataclass
class RoleRecord:
    internal_id: int
    name: str
    uuid: str | None = None
    description: str | None = None
    created_at: str | None = None

    def to_element(self):
        elem = etree.Element("role", internal_id=str(self.internal_id), name=self.name)
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "description", self.description)
        _set_opt(elem, "created_at", self.created_at)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            name=elem.get("name"),
            uuid=_get_str(elem, "uuid"),
            description=_get_str(elem, "description"),
            created_at=_get_str(elem, "created_at"),
        )


@dataclass
class UserRecord:
    internal_id: int
    email: str
    role_id: int
    full_name: str
    password_hash: str
    uuid: str | None = None
    is_active: bool = True
    token_version: int = 1
    created_at: str | None = None
    updated_at: str | None = None
    last_login: str | None = None

    def to_element(self):
        elem = etree.Element(
            "user",
            internal_id=str(self.internal_id),
            email=self.email,
            role_id=str(self.role_id),
            is_active=_bool_str(self.is_active),
            token_version=str(self.token_version),
        )
        _set_opt(elem, "uuid", self.uuid)
        _text_child(elem, "full_name", self.full_name)
        _text_child(elem, "password_hash", self.password_hash)
        _text_child(elem, "created_at", self.created_at)
        _text_child(elem, "updated_at", self.updated_at)
        _text_child(elem, "last_login", self.last_login)
        return elem

    @classmethod
    def from_element(cls, elem):
        token_version = _get_int(elem, "token_version")
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            email=elem.get("email"),
            role_id=_get_int(elem, "role_id"),
            full_name=_child_text(elem, "full_name"),
            password_hash=_child_text(elem, "password_hash"),
            uuid=_get_str(elem, "uuid"),
            is_active=_get_bool(elem, "is_active", True),
            # 0 est une valeur stockée valide (cohérence SQLAlchemy) ; seul
            # l'attribut absent retombe sur la valeur par défaut 1.
            token_version=token_version if token_version is not None else 1,
            created_at=_child_text(elem, "created_at"),
            updated_at=_child_text(elem, "updated_at"),
            last_login=_child_text(elem, "last_login"),
        )


@dataclass
class TcpCredentialRecord:
    internal_id: int
    user_id: int
    tcp_username: str
    tcp_password: str
    uuid: str | None = None
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 3307
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None

    def to_element(self):
        elem = etree.Element(
            "credential",
            internal_id=str(self.internal_id),
            user_id=str(self.user_id),
            tcp_username=self.tcp_username,
            tcp_host=self.tcp_host,
            tcp_port=str(self.tcp_port),
            is_active=_bool_str(self.is_active),
        )
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "created_at", self.created_at)
        _set_opt(elem, "updated_at", self.updated_at)
        _text_child(elem, "password_hash", self.tcp_password)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            user_id=_get_int(elem, "user_id"),
            tcp_username=elem.get("tcp_username"),
            tcp_password=_child_text(elem, "password_hash"),
            uuid=_get_str(elem, "uuid"),
            tcp_host=elem.get("tcp_host") or "127.0.0.1",
            tcp_port=_get_int(elem, "tcp_port") or 3307,
            is_active=_get_bool(elem, "is_active", True),
            created_at=_get_str(elem, "created_at"),
            updated_at=_get_str(elem, "updated_at"),
        )


@dataclass
class SecurityDocument:
    roles: list[RoleRecord] = field(default_factory=list)
    users: list[UserRecord] = field(default_factory=list)
    tcp_credentials: list[TcpCredentialRecord] = field(default_factory=list)
    version: int = 1

    XSD = "security.xsd"

    def to_root(self):
        root = etree.Element("security", version=str(self.version))
        roles = etree.SubElement(root, "roles")
        for item in self.roles:
            roles.append(item.to_element())
        users = etree.SubElement(root, "users")
        for item in self.users:
            users.append(item.to_element())
        credentials = etree.SubElement(root, "tcp_credentials")
        for item in self.tcp_credentials:
            credentials.append(item.to_element())
        return root

    def to_xml_bytes(self, *, validate=True):
        return _serialize(self.to_root(), schema_path(self.XSD), validate=validate)

    @classmethod
    def from_root(cls, root):
        return cls(
            version=int(root.get("version", "1")),
            roles=[RoleRecord.from_element(e) for e in root.findall("roles/role")],
            users=[UserRecord.from_element(e) for e in root.findall("users/user")],
            tcp_credentials=[TcpCredentialRecord.from_element(e) for e in root.findall("tcp_credentials/credential")],
        )

    @classmethod
    def from_xml_bytes(cls, data, *, validate=True):
        return cls.from_root(_deserialize(data, schema_path(cls.XSD), validate=validate))


# --------------------------------------------------------------------------
# catalog.xml
# --------------------------------------------------------------------------

@dataclass
class DatabaseRecord:
    internal_id: int
    name: str
    key_identifier: str
    creator_id: int
    uuid: str | None = None
    description: str | None = None
    owner_id: int | None = None
    scope: Scope = Scope.PERSONAL
    common_permission: CommonPermission | None = None
    xml_file_path: str | None = None
    projection_path: str | None = None
    document_version: int = 1
    xml_checksum: str | None = None
    sync_status: str = "PENDING"
    status: str = "ACTIVE"
    created_at: str | None = None
    updated_at: str | None = None
    last_modified_by_id: int | None = None
    last_modified_by_name: str | None = None
    comment: str | None = None

    def to_element(self):
        elem = etree.Element(
            "database",
            internal_id=str(self.internal_id),
            name=self.name,
            key_identifier=self.key_identifier,
            creator_id=str(self.creator_id),
            scope=_to_scope(self.scope).value,
            document_version=str(self.document_version),
        )
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "description", self.description)
        _set_opt(elem, "comment", self.comment)
        _set_opt(elem, "owner_id", self.owner_id)
        _set_opt(elem, "common_permission", _to_common_permission(self.common_permission).value if self.common_permission else None)
        _set_opt(elem, "xml_file_path", self.xml_file_path)
        _set_opt(elem, "projection_path", self.projection_path)
        _set_opt(elem, "xml_checksum", self.xml_checksum)
        _set_opt(elem, "sync_status", self.sync_status)
        _set_opt(elem, "status", self.status)
        _set_opt(elem, "created_at", self.created_at)
        _set_opt(elem, "updated_at", self.updated_at)
        _set_opt(elem, "last_modified_by_id", self.last_modified_by_id)
        _set_opt(elem, "last_modified_by_name", self.last_modified_by_name)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            name=elem.get("name"),
            key_identifier=elem.get("key_identifier"),
            creator_id=_get_int(elem, "creator_id"),
            uuid=_get_str(elem, "uuid"),
            description=_get_str(elem, "description"),
            owner_id=_get_int(elem, "owner_id"),
            scope=_to_scope(elem.get("scope") or "PERSONAL"),
            common_permission=_to_common_permission(elem.get("common_permission")),
            xml_file_path=_get_str(elem, "xml_file_path"),
            projection_path=_get_str(elem, "projection_path"),
            document_version=_get_int(elem, "document_version") or 1,
            xml_checksum=_get_str(elem, "xml_checksum"),
            sync_status=elem.get("sync_status") or "PENDING",
            status=elem.get("status") or "ACTIVE",
            created_at=_get_str(elem, "created_at"),
            updated_at=_get_str(elem, "updated_at"),
            last_modified_by_id=_get_int(elem, "last_modified_by_id"),
            last_modified_by_name=_get_str(elem, "last_modified_by_name"),
            comment=_get_str(elem, "comment"),
        )


@dataclass
class DatabasePermissionRecord:
    internal_id: int
    database_id: int
    user_id: int
    can_read: bool = False
    can_write: bool = False
    can_ddl: bool = False
    can_admin: bool = False
    uuid: str | None = None
    granted_by_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_element(self):
        elem = etree.Element(
            "database_permission",
            internal_id=str(self.internal_id),
            database_id=str(self.database_id),
            user_id=str(self.user_id),
            can_read=_bool_str(self.can_read),
            can_write=_bool_str(self.can_write),
            can_ddl=_bool_str(self.can_ddl),
            can_admin=_bool_str(self.can_admin),
        )
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "granted_by_id", self.granted_by_id)
        _set_opt(elem, "created_at", self.created_at)
        _set_opt(elem, "updated_at", self.updated_at)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            database_id=_get_int(elem, "database_id"),
            user_id=_get_int(elem, "user_id"),
            can_read=_get_bool(elem, "can_read", False),
            can_write=_get_bool(elem, "can_write", False),
            can_ddl=_get_bool(elem, "can_ddl", False),
            can_admin=_get_bool(elem, "can_admin", False),
            uuid=_get_str(elem, "uuid"),
            granted_by_id=_get_int(elem, "granted_by_id"),
            created_at=_get_str(elem, "created_at"),
            updated_at=_get_str(elem, "updated_at"),
        )


@dataclass
class TablePermissionRecord:
    internal_id: int
    table_id: int
    user_id: int
    database_id: int | None = None
    can_read: bool = False
    can_write: bool = False
    can_ddl: bool = False
    can_admin: bool = False
    uuid: str | None = None
    granted_by_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_element(self):
        elem = etree.Element(
            "table_permission",
            internal_id=str(self.internal_id),
            table_id=str(self.table_id),
            user_id=str(self.user_id),
            can_read=_bool_str(self.can_read),
            can_write=_bool_str(self.can_write),
            can_ddl=_bool_str(self.can_ddl),
            can_admin=_bool_str(self.can_admin),
        )
        _set_opt(elem, "database_id", self.database_id)
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "granted_by_id", self.granted_by_id)
        _set_opt(elem, "created_at", self.created_at)
        _set_opt(elem, "updated_at", self.updated_at)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            table_id=_get_int(elem, "table_id"),
            user_id=_get_int(elem, "user_id"),
            database_id=_get_int(elem, "database_id"),
            can_read=_get_bool(elem, "can_read", False),
            can_write=_get_bool(elem, "can_write", False),
            can_ddl=_get_bool(elem, "can_ddl", False),
            can_admin=_get_bool(elem, "can_admin", False),
            uuid=_get_str(elem, "uuid"),
            granted_by_id=_get_int(elem, "granted_by_id"),
            created_at=_get_str(elem, "created_at"),
            updated_at=_get_str(elem, "updated_at"),
        )


@dataclass
class CatalogDocument:
    databases: list[DatabaseRecord] = field(default_factory=list)
    database_permissions: list[DatabasePermissionRecord] = field(default_factory=list)
    table_permissions: list[TablePermissionRecord] = field(default_factory=list)
    version: int = 1
    next_object_id: int | None = None

    XSD = "catalog.xsd"

    def to_root(self):
        root = etree.Element("catalog", version=str(self.version))
        if self.next_object_id is not None:
            root.set("next_object_id", str(self.next_object_id))
        databases = etree.SubElement(root, "databases")
        for item in self.databases:
            databases.append(item.to_element())
        db_perms = etree.SubElement(root, "database_permissions")
        for item in self.database_permissions:
            db_perms.append(item.to_element())
        table_perms = etree.SubElement(root, "table_permissions")
        for item in self.table_permissions:
            table_perms.append(item.to_element())
        return root

    def to_xml_bytes(self, *, validate=True):
        return _serialize(self.to_root(), schema_path(self.XSD), validate=validate)

    @classmethod
    def from_root(cls, root):
        next_id = root.get("next_object_id")
        return cls(
            version=int(root.get("version", "1")),
            databases=[DatabaseRecord.from_element(e) for e in root.findall("databases/database")],
            database_permissions=[DatabasePermissionRecord.from_element(e) for e in root.findall("database_permissions/database_permission")],
            table_permissions=[TablePermissionRecord.from_element(e) for e in root.findall("table_permissions/table_permission")],
            next_object_id=int(next_id) if next_id is not None else None,
        )

    @classmethod
    def from_xml_bytes(cls, data, *, validate=True):
        return cls.from_root(_deserialize(data, schema_path(cls.XSD), validate=validate))


# --------------------------------------------------------------------------
# history.xml
# --------------------------------------------------------------------------

@dataclass
class HistoryRecord:
    internal_id: int
    user_id: int
    user_name: str
    action_type: str
    element_type: str
    element_name: str
    created_at: str
    uuid: str | None = None
    description: str | None = None
    ip_address: str | None = None
    database_id: int | None = None
    table_id: int | None = None
    before_data: str | None = None
    after_data: str | None = None

    def to_element(self):
        elem = etree.Element(
            "entry",
            internal_id=str(self.internal_id),
            user_id=str(self.user_id),
            user_name=self.user_name,
            action_type=self.action_type,
            element_type=self.element_type,
            element_name=self.element_name,
            created_at=self.created_at,
        )
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "ip_address", self.ip_address)
        _set_opt(elem, "database_id", self.database_id)
        _set_opt(elem, "table_id", self.table_id)
        _text_child(elem, "description", self.description)
        _cdata_child(elem, "before_data", self.before_data)
        _cdata_child(elem, "after_data", self.after_data)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            user_id=_get_int(elem, "user_id"),
            user_name=elem.get("user_name"),
            action_type=elem.get("action_type"),
            element_type=elem.get("element_type"),
            element_name=elem.get("element_name"),
            created_at=elem.get("created_at"),
            uuid=_get_str(elem, "uuid"),
            description=_child_text(elem, "description"),
            ip_address=_get_str(elem, "ip_address"),
            database_id=_get_int(elem, "database_id"),
            table_id=_get_int(elem, "table_id"),
            before_data=_child_text(elem, "before_data"),
            after_data=_child_text(elem, "after_data"),
        )


@dataclass
class HistoryDocument:
    entries: list[HistoryRecord] = field(default_factory=list)
    version: int = 1

    XSD = "history.xsd"

    def to_root(self):
        root = etree.Element("history", version=str(self.version))
        entries = etree.SubElement(root, "entries")
        for item in self.entries:
            entries.append(item.to_element())
        return root

    def to_xml_bytes(self, *, validate=True):
        return _serialize(self.to_root(), schema_path(self.XSD), validate=validate)

    @classmethod
    def from_root(cls, root):
        return cls(
            version=int(root.get("version", "1")),
            entries=[HistoryRecord.from_element(e) for e in root.findall("entries/entry")],
        )

    @classmethod
    def from_xml_bytes(cls, data, *, validate=True):
        return cls.from_root(_deserialize(data, schema_path(cls.XSD), validate=validate))


# --------------------------------------------------------------------------
# audit/audit-YYYY-MM.xml
# --------------------------------------------------------------------------

@dataclass
class AuditRecord:
    internal_id: int
    action: str
    timestamp: str
    uuid: str | None = None
    user_id: int | None = None
    user_name: str | None = None
    ip_address: str | None = None
    element_type: str | None = None
    element_name: str | None = None
    description: str | None = None
    meta_data: str | None = None

    def to_element(self):
        elem = etree.Element(
            "entry",
            internal_id=str(self.internal_id),
            action=self.action,
            timestamp=self.timestamp,
        )
        _set_opt(elem, "uuid", self.uuid)
        _set_opt(elem, "user_id", self.user_id)
        _set_opt(elem, "user_name", self.user_name)
        _set_opt(elem, "ip_address", self.ip_address)
        _set_opt(elem, "element_type", self.element_type)
        _set_opt(elem, "element_name", self.element_name)
        _text_child(elem, "description", self.description)
        _cdata_child(elem, "meta_data", self.meta_data)
        return elem

    @classmethod
    def from_element(cls, elem):
        return cls(
            internal_id=_get_int(elem, "internal_id"),
            action=elem.get("action"),
            timestamp=elem.get("timestamp"),
            uuid=_get_str(elem, "uuid"),
            user_id=_get_int(elem, "user_id"),
            user_name=_get_str(elem, "user_name"),
            ip_address=_get_str(elem, "ip_address"),
            element_type=_get_str(elem, "element_type"),
            element_name=_get_str(elem, "element_name"),
            description=_child_text(elem, "description"),
            meta_data=_child_text(elem, "meta_data"),
        )


@dataclass
class AuditDocument:
    month: str
    entries: list[AuditRecord] = field(default_factory=list)
    version: int = 1

    XSD = "audit.xsd"

    def to_root(self):
        root = etree.Element("audit", version=str(self.version), month=self.month)
        entries = etree.SubElement(root, "entries")
        for item in self.entries:
            entries.append(item.to_element())
        return root

    def to_xml_bytes(self, *, validate=True):
        return _serialize(self.to_root(), schema_path(self.XSD), validate=validate)

    @classmethod
    def from_root(cls, root):
        return cls(
            month=root.get("month"),
            version=int(root.get("version", "1")),
            entries=[AuditRecord.from_element(e) for e in root.findall("entries/entry")],
        )

    @classmethod
    def from_xml_bytes(cls, data, *, validate=True):
        return cls.from_root(_deserialize(data, schema_path(cls.XSD), validate=validate))


__all__ = [
    "Scope", "CommonPermission",
    "RoleRecord", "UserRecord", "TcpCredentialRecord", "SecurityDocument",
    "DatabaseRecord", "DatabasePermissionRecord", "TablePermissionRecord", "CatalogDocument",
    "HistoryRecord", "HistoryDocument",
    "AuditRecord", "AuditDocument",
    "schema_path",
]
