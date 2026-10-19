"""XMLForge — client Python officiel du serveur de base de données (Phase 7).

Le client communique uniquement avec le serveur TCP (port 3307) ; il n'accède
jamais directement aux fichiers XML.
"""

from .client import connect, Connection
from .errors import XmlforgeError
from .result import Result

__version__ = "1.0.0"
__all__ = ["connect", "Connection", "XmlforgeError", "Result"]
