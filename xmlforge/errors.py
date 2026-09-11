"""Codes d'erreur métier XMLForge (Phase 7).

Exposés par le serveur dans le champ ``error_code`` des messages d'erreur TCP.
Le champ ``code`` (numérique) reste le code de protocole historique.
"""

# Erreurs de protocole (numériques, compat serveur)
AUTH_REQUIRED = "AUTH_REQUIRED"
AUTH_FAILED = "AUTH_FAILED"
SESSION_ERROR = "SESSION_ERROR"
TIMEOUT = "TIMEOUT"
CONNECTION_ERROR = "CONNECTION_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"

# Erreurs métier (code métier du serveur)
ACCESS_DENIED = "ACCESS_DENIED"
DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
COLUMN_NOT_FOUND = "COLUMN_NOT_FOUND"
DATABASE_NOT_SELECTED = "DATABASE_NOT_SELECTED"
INVALID_QUERY = "INVALID_QUERY"
SYNTAX_ERROR = "SYNTAX_ERROR"
CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
CONFLICT = "CONFLICT"
TRANSACTION_ACTIVE = "TRANSACTION_ACTIVE"
TRANSACTION_NOT_ACTIVE = "TRANSACTION_NOT_ACTIVE"
TRANSACTION_ERROR = "TRANSACTION_ERROR"


class XmlforgeError(Exception):
    """Erreur retournée par le serveur XMLForge (protocole ou métier)."""

    def __init__(self, message, code=None, numeric_code=None):
        super().__init__(message)
        self.message = message
        self.code = code  # code métier (str)
        self.numeric_code = numeric_code  # code de protocole (int)
