"""Configuration centralisée XMLForge Backend — architecture XML-only (6J-B).

Plus de base SQLite/SQLAlchemy : les plans de contrôle et de données sont en XML.

Préparation au packaging Windows :
- les dossiers de données runtime sont résolus via ``app.paths`` : en mode gelé,
  ils vivent sous ``%LOCALAPPDATA%\\XMLForge`` (jamais dans le dossier
  d'installation, jamais dans ``_MEIPASS``) ;
- la configuration ``.env`` est chargée depuis des emplacements déterministes
  (dossier de config runtime puis dossier du backend) — indépendante du CWD ;
- en mode gelé, ``SECRET_KEY``/``JWT_SECRET_KEY`` sont générés et persistés
  s'ils n'existent pas (jamais de valeur de développement en production).
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

from . import paths

# --- 1) Configuration locale déterministe (indépendante du CWD) ------------
for _dotenv_path in (
    os.path.join(paths.config_folder(), ".env"),  # config installée (prioritaire)
    os.path.join(paths.resource_root(), ".env"),  # projet (développement)
):
    if os.path.isfile(_dotenv_path):
        load_dotenv(_dotenv_path)

# --- 2) Secrets persistants en mode gelé (jamais en développement) ----------
if paths.is_frozen():
    from .runtime import ensure_secrets  # noqa: E402

    ensure_secrets()


class Config:
    # Flask / HTTP
    SECRET_KEY = os.getenv('SECRET_KEY', 'xmlforge-dev-secret-key-please-change-40chars')
    HTTP_HOST = os.getenv('XMLFORGE_HTTP_HOST', '0.0.0.0')
    HTTP_PORT = int(os.getenv('XMLFORGE_HTTP_PORT', '5000'))

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'xmlforge-dev-jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('JWT_EXPIRES_HOURS', '24')))

    # Ressources applicatives et données runtime (séparées pour le packaging).
    BACKEND_ROOT = paths.resource_root()
    CONTROL_STORAGE_FOLDER = os.getenv('CONTROL_STORAGE_FOLDER') or paths.control_folder()
    XML_STORAGE_FOLDER = os.getenv('XML_STORAGE_FOLDER') or paths.xml_folder()
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER') or paths.uploads_folder()
    EXPORT_FOLDER = os.getenv('EXPORT_FOLDER') or paths.exports_folder()
    LOG_FOLDER = paths.logs_folder()
    CONFIG_FOLDER = paths.config_folder()
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Frontend buildé : servi par Flask s'il existe (valeur re-résolue au démarrage).
    FRONTEND_DIST_FOLDER = os.getenv('XMLFORGE_FRONTEND_DIST') or None

    # Logs fichier : automatiques en mode gelé, sinon via XMLFORGE_FILE_LOGS.
    _FILE_LOGS = os.getenv('XMLFORGE_FILE_LOGS')
    FILE_LOGS_ENABLED = (_FILE_LOGS.lower() in ('1', 'true', 'yes')
                         if _FILE_LOGS else paths.is_frozen())

    # TCP/IP
    TCP_ENABLED = os.getenv('TCP_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    TCP_HOST = os.getenv('TCP_HOST', '0.0.0.0')
    TCP_PORT = int(os.getenv('TCP_PORT', '3307'))
    TCP_SESSION_TIMEOUT_MINUTES = int(os.getenv('TCP_SESSION_TIMEOUT_MINUTES', '30'))

    # Moteur de requêtes : XML natif uniquement (SQLite retiré en 6J-B).
    QUERY_BACKEND = 'xml'
    # La projection SQLite n'existe plus.
    SYNC_SQLITE_PROJECTION = False

    # Control Plane : XML uniquement.
    CONTROL_BACKEND = 'xml'
    # Data Plane : XML uniquement.
    DATA_BACKEND = 'xml'

    # Rétention de l'audit XML rotatif, en mois.
    AUDIT_RETENTION_MONTHS = int(os.getenv('AUDIT_RETENTION_MONTHS', '24') or '24')
    # Compresser (gzip) les mois d'audit anciens.
    AUDIT_COMPRESS_OLD_MONTHS = os.getenv('AUDIT_COMPRESS_OLD_MONTHS', 'true').lower() in ('1', 'true', 'yes')
    # Niveau d'accès collectif par défaut des bases COMMON.
    COMMON_PERMISSION_DEFAULT = (os.getenv('COMMON_PERMISSION_DEFAULT', 'VIEW') or 'VIEW').upper()

    # Serveur de développement uniquement.
    ALLOW_UNSAFE_WERKZEUG = os.getenv('ALLOW_UNSAFE_WERKZEUG', 'true').lower() in ('1', 'true', 'yes')

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')

    @classmethod
    def validate(cls):
        if cls.COMMON_PERMISSION_DEFAULT not in ('VIEW', 'EDIT', 'MANAGE'):
            raise RuntimeError(
                f"COMMON_PERMISSION_DEFAULT invalide: {cls.COMMON_PERMISSION_DEFAULT!r} "
                "(attendu: VIEW | EDIT | MANAGE)"
            )
        if not isinstance(cls.AUDIT_RETENTION_MONTHS, int) or cls.AUDIT_RETENTION_MONTHS < 1:
            raise RuntimeError("AUDIT_RETENTION_MONTHS doit être un entier >= 1")


class TestingConfig(Config):
    TESTING = True
    JWT_SECRET_KEY = 'test-secret-key-with-at-least-32-bytes'
    TCP_ENABLED = False
    # Désactiver le serving frontend en tests : évite que la présence d'un
    # build `xmlforge-react/dist` transforme les 404 attendus en 200 SPA.
    FRONTEND_DIST_FOLDER = "/tmp/xmlforge-tests-no-frontend-dist"


class ProductionConfig(Config):
    ENV = 'production'
    DEBUG = False
    ALLOW_UNSAFE_WERKZEUG = False

    @classmethod
    def validate(cls):
        super().validate()
        if cls.SECRET_KEY.startswith('xmlforge-dev-') or cls.JWT_SECRET_KEY.startswith('xmlforge-dev-'):
            raise RuntimeError('SECRET_KEY et JWT_SECRET_KEY explicites sont obligatoires en production')
