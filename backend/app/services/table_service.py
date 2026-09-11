"""Tables — Data Plane XML (Phase 6J-B)."""

from __future__ import annotations

from ..data_plane import get_table, list_tables
from ..data_plane import xml_services
from .permission_service import PermissionService
from .unlock_service import UnlockService


class TableService:
    @staticmethod
    def get_by_database(database_id, include_archived=True, user_id=None):
        if user_id is not None and not PermissionService.can_database(user_id, database_id, "read"):
            return []
        tables = list_tables(database_id)
        if not include_archived:
            tables = [t for t in tables if t.status == "ACTIVE"]
        tables.sort(key=lambda t: t.id or 0)
        return tables

    @staticmethod
    def get_by_id(table_id):
        return get_table(table_id)

    @staticmethod
    def _check_protection(table, provided_key=None, user_id=None):
        return UnlockService.check_protection(user_id, table, provided_key)

    @staticmethod
    def create(name, description, database_id, creator_id, creator_name, is_protected=False,
               comment="", file_identifier=None, ip_address=None, expected_version=None):
        return xml_services.create_table(
            name, description, database_id, creator_id, creator_name,
            is_protected=is_protected, comment=comment, file_identifier=file_identifier,
            ip_address=ip_address, expected_version=expected_version)

    @staticmethod
    def update(table_id, data, user_id, user_name, provided_key=None, ip_address=None,
               expected_version=None):
        return xml_services.update_table(table_id, data, user_id, user_name,
                                         provided_key=provided_key, ip_address=ip_address,
                                         expected_version=expected_version)

    @staticmethod
    def delete(table_id, user_id, user_name, provided_key=None, ip_address=None,
               expected_version=None):
        return xml_services.delete_table(table_id, user_id, user_name,
                                         provided_key=provided_key, ip_address=ip_address,
                                         expected_version=expected_version)

    @staticmethod
    def update_comment(table_id, comment, user_id, user_name, ip_address=None, provided_key=None):
        return TableService.update(table_id, {"comment": comment}, user_id, user_name,
                                   provided_key, ip_address)

    @staticmethod
    def archive(table_id, user_id, user_name, ip_address=None, provided_key=None):
        return TableService.update(table_id, {"status": "ARCHIVED"}, user_id, user_name,
                                   provided_key, ip_address)

    @staticmethod
    def restore(table_id, user_id, user_name, ip_address=None, provided_key=None):
        return TableService.update(table_id, {"status": "ACTIVE"}, user_id, user_name,
                                   provided_key, ip_address)

    @staticmethod
    def unlock(table_id, key_identifier, user_id=None):
        table = get_table(table_id)
        if not table:
            return False, "Table introuvable"
        if not PermissionService.can_table(user_id, table.id, "write"):
            return False, "Permission d'écriture requise avant déverrouillage"
        return UnlockService.unlock_table(user_id, table_id, key_identifier)
