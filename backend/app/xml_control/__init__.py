"""Control Plane XML — infrastructure (Phase 6A).

Ce package fournit la couche d'infrastructure du Control Plane XML :
stockage atomique, verrous, version, checksum, snapshot/restore et
validation XSD. Aucune logique métier (users, ACL, audit…) n'y figure :
elle arrivera dans les phases 6B et suivantes.

Le Control Plane XML est l'unique implémentation du plan de contrôle.
"""

from . import store  # noqa: F401

__all__ = ["store"]
