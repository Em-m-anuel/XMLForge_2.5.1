"""Services métier XMLForge.

Import volontairement léger : les consommateurs importent les sous-modules
directement (``from ..services.auth_service import AuthService``). Évite un
import circulaire (``query.service`` ↔ ``services.row_service``) lors de
l'import du package.
"""
