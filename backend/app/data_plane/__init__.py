"""Abstraction du Data Plane — architecture XML-only (Phase 6J-B).

Unique implémentation : XML (``XmlDataPlane``). Aucune dépendance SQLite.
"""

from __future__ import annotations

from flask import current_app, has_app_context


def get_data_plane():
    """Retourne le singleton ``XmlDataPlane`` de l'application."""
    if not has_app_context():
        raise RuntimeError("get_data_plane() nécessite un contexte d'application")
    cache = getattr(current_app, "_xml_data_plane", None)
    if cache is None:
        from .xml_backend import XmlDataPlane
        cache = XmlDataPlane(current_app.config)
        setattr(current_app, "_xml_data_plane", cache)
    return cache


def resolve_table(database_id, table_id_or_name):
    """Résout une table (TableView) par id ou nom, dans une base donnée."""
    return get_data_plane().resolve_table(database_id, table_id_or_name)


def get_table(table_id):
    """Résout une table par id global (scan des documents)."""
    return get_data_plane().table_by_id(table_id)


def list_tables(database_id):
    return get_data_plane().list_tables(database_id)


__all__ = ["get_data_plane", "resolve_table", "get_table", "list_tables"]
