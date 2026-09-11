"""Couche d'accès au Control Plane XML (Phase 6J-B).

Le backend XML est l'unique implémentation du plan de contrôle (SQLite retiré).
"""

from .base import (  # noqa: F401
    backend_name, effective_common_permission, get_backend,
)

__all__ = ["get_backend", "backend_name", "effective_common_permission"]
