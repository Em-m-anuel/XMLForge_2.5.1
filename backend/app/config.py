"""Configuration centralisée XMLForge Backend — architecture XML-only (6J-B).

Plus de base SQLite/SQLAlchemy : les plans de contrôle et de données sont en XML.
"""

import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'xmlforge-dev-secret-key-please-change-40chars')

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'xmlforge-dev-jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('JWT_EXPIRES_HOURS', '24')))

    # Uploads et stockage persistant XMLForge
    BACKEND_ROOT = os.path.dirname(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BACKEND_ROOT, 'uploads')
    EXPORT_FOLDER = os.path.join(BACKEND_ROOT, 'exports')
    XML_STORAGE_FOLDER = os.getenv('XML_STORAGE_FOLDER') or os.path.join(BACKEND_ROOT, 'data', 'xml')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

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

    # Dossier privé des fichiers du Control Plane XML.
    CONTROL_STORAGE_FOLDER = os.getenv('CONTROL_STORAGE_FOLDER') or os.path.join(BACKEND_ROOT, 'data', 'control')
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


class ProductionConfig(Config):
    ENV = 'production'
    DEBUG = False
    ALLOW_UNSAFE_WERKZEUG = False

    @classmethod
    def validate(cls):
        super().validate()
        if cls.SECRET_KEY.startswith('xmlforge-dev-') or cls.JWT_SECRET_KEY.startswith('xmlforge-dev-'):
            raise RuntimeError('SECRET_KEY et JWT_SECRET_KEY explicites sont obligatoires en production')
