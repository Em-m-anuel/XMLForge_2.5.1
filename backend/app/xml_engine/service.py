"""Facade Data Plane XML (Phase 6J-B).

Délègue au ``XmlDataPlane`` : lecture, mutation atomique, remplacement et
suppression de documents. Aucune dépendance SQLite/SQLAlchemy.
"""

from __future__ import annotations

from .document import parse_document, serialize_document


class XmlEngineService:
    @staticmethod
    def sync_projection_enabled():
        """Toujours False : la projection SQLite a été retirée (6J-B)."""
        return False

    @staticmethod
    def read_document(database_or_id):
        from ..data_plane import get_data_plane
        return get_data_plane().read_document(database_or_id)

    @staticmethod
    def mutate(database_id, mutator, *, expected_version=None):
        from ..data_plane import get_data_plane
        return get_data_plane().mutate(database_id, mutator, expected_version)

    @staticmethod
    def replace_document(database_id, xml_content, *, expected_version=None):
        incoming = parse_document(xml_content, validate=True)

        def replace(current):
            version = current.get("version", 1)
            current.clear()
            current.update(incoming)
            current["version"] = version

        return XmlEngineService.mutate(database_id, replace, expected_version=expected_version)

    @staticmethod
    def delete_storage(database):
        from ..data_plane import get_data_plane
        return get_data_plane().delete_storage(database.id)

    @staticmethod
    def initialize_all():
        return []
