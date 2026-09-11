"""Colonnes — Data Plane XML (Phase 6J-B)."""

from __future__ import annotations

from ..data_plane import get_data_plane
from ..data_plane import xml_services


class ColumnService:
    @staticmethod
    def _normalize(data):
        result = dict(data)
        aliases = {"primaryKey": "primary_key", "foreignKey": "foreign_key",
                   "autoIncrement": "auto_increment"}
        for source, target in aliases.items():
            if source in result:
                result[target] = bool(result.get(target)) or bool(result.get(source))
        if "indexed" in result and "index" not in result:
            result["index"] = result["indexed"]
        return result

    @staticmethod
    def get_by_table(table_id, include_archived=True, user_id=None):
        return xml_services.list_columns_for_table(table_id, include_archived, user_id)

    @staticmethod
    def get_by_id(col_id):
        return xml_services.get_column(col_id)

    @staticmethod
    def create(data, creator_id, creator_name, provided_key=None, ip_address=None,
               expected_version=None):
        data = ColumnService._normalize(data)
        return xml_services.create_column(data, creator_id, creator_name,
                                          provided_key=provided_key, ip_address=ip_address,
                                          expected_version=expected_version)

    @staticmethod
    def update(col_id, data, user_id, user_name, provided_key=None, ip_address=None,
               expected_version=None):
        data = ColumnService._normalize(data)
        return xml_services.update_column(col_id, data, user_id, user_name,
                                          provided_key=provided_key, ip_address=ip_address,
                                          expected_version=expected_version)

    @staticmethod
    def delete(col_id, user_id, user_name, provided_key=None, ip_address=None,
               expected_version=None):
        return xml_services.delete_column(col_id, user_id, user_name,
                                          provided_key=provided_key, ip_address=ip_address,
                                          expected_version=expected_version)

    @staticmethod
    def update_comment(col_id, comment, user_id, user_name, ip_address=None, provided_key=None):
        return ColumnService.update(col_id, {"comment": comment}, user_id, user_name,
                                    provided_key, ip_address)

    @staticmethod
    def archive(col_id, user_id, user_name, ip_address=None, provided_key=None):
        return ColumnService.update(col_id, {"status": "ARCHIVED"}, user_id, user_name,
                                    provided_key, ip_address)

    @staticmethod
    def restore(col_id, user_id, user_name, ip_address=None, provided_key=None):
        return ColumnService.update(col_id, {"status": "ACTIVE"}, user_id, user_name,
                                    provided_key, ip_address)
