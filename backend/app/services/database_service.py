"""Bases — Data Plane + Control Plane XML (Phase 6J-B)."""

from __future__ import annotations

from ..data_plane import get_data_plane
from ..data_plane import xml_services
from .permission_service import PermissionService


class DatabaseService:
    @staticmethod
    def get_all(include_archived=True, user_id=None):
        if user_id is not None:
            return PermissionService.accessible_databases(user_id, include_archived)
        return get_data_plane().list_databases(include_archived=include_archived)

    @staticmethod
    def get_by_id(db_id):
        return get_data_plane().get_database(db_id)

    @staticmethod
    def get_by_key(key_identifier):
        return get_data_plane().get_database_by_key(key_identifier)

    @staticmethod
    def create(name, description, creator_id, creator_name, comment="", ip_address=None,
               scope="PERSONAL", common_permission=None):
        return xml_services.create_database(
            name, description, creator_id, creator_name, comment=comment,
            ip_address=ip_address, scope=scope, common_permission=common_permission)

    @staticmethod
    def update(db_id, data, user_id, user_name, ip_address=None, expected_version=None):
        return xml_services.update_database(db_id, data, user_id, user_name,
                                            ip_address=ip_address, expected_version=expected_version)

    @staticmethod
    def delete(db_id, user_id, user_name, ip_address=None):
        return xml_services.delete_database(db_id, user_id, user_name, ip_address=ip_address)

    @staticmethod
    def update_comment(db_id, comment, user_id, user_name, ip_address=None):
        return DatabaseService.update(db_id, {"comment": comment}, user_id, user_name, ip_address)

    @staticmethod
    def archive(db_id, user_id, user_name, ip_address=None):
        return xml_services.archive_database(db_id, user_id, user_name, ip_address=ip_address)

    @staticmethod
    def restore(db_id, user_id, user_name, ip_address=None):
        return xml_services.restore_database(db_id, user_id, user_name, ip_address=ip_address)

    @staticmethod
    def get_database_by_name(user_id, database_name):
        candidates = [d for d in get_data_plane().list_databases(include_archived=False)
                      if d.name == database_name]
        return next((d for d in candidates if PermissionService.can_database(user_id, d, "read")), None)

    @staticmethod
    def get_database_by_name_any_user(database_name):
        return next((d for d in get_data_plane().list_databases(include_archived=False)
                     if d.name == database_name), None)
