"""Sélection du backend Control Plane (XML uniquement).

``CONTROL_BACKEND=xml`` est l'unique backend (SQLite retiré en 6J-B).
"""

from __future__ import annotations

from flask import current_app, has_app_context


def backend_name():
    return "xml"


def get_backend():
    """Retourne l'unique backend Control Plane : ``XmlControlPlane``."""
    if not has_app_context():
        raise RuntimeError("get_backend() nécessite un contexte d'application")
    app = current_app
    cache = getattr(app, "_control_plane_backend", None)
    if cache is None:
        from .xml_backend import XmlControlPlane
        cache = XmlControlPlane.from_config(app.config)
        setattr(app, "_control_plane_backend", cache)
    return cache


def effective_common_permission(database):
    """Niveau collectif effectif d'une base COMMON.

    ``database.common_permission`` explicite sinon ``COMMON_PERMISSION_DEFAULT``.
    La valeur stockée n'est jamais modifiée (distinction stocké/effectif).
    """
    value = getattr(database, "common_permission", None)
    if value is not None:
        value = getattr(value, "value", value)
        value = str(value).upper()
        if value in ("VIEW", "EDIT", "MANAGE"):
            return value
    if has_app_context():
        return str(current_app.config.get("COMMON_PERMISSION_DEFAULT", "VIEW")).upper()
    return "VIEW"
