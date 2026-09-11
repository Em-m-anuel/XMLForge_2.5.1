"""Nom explicite de la façade d'accès utilisée par les tests et intégrations.

PermissionService reste le nom historique. AccessService hérite de la même
implémentation afin de garantir une seule source de règles d'autorisation.
"""
from .permission_service import PermissionService


class AccessService(PermissionService):
    pass
