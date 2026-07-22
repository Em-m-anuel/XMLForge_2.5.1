"""
Configuration centralisée XMLForge Backend
Supporte .env pour MySQL et JWT
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'xmlforge-secret-dev-key-change-in-prod')
    # Database - SQLite par défaut pour dev/tests, MySQL pour prod si configuré
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'xmlforge.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'xmlforge-jwt-secret-dev')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('JWT_EXPIRES_HOURS', '24')))

    # MySQL pour création réelle de bases
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306'))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', '')  # optionnel, si vide on crée dynamiquement

    # Uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    EXPORT_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # CORS
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    JWT_SECRET_KEY = 'test-secret'

class ProductionConfig(Config):
    ENV = 'production'
    # En prod, forcer MySQL si DATABASE_URL non défini via .env
    # Ex: mysql+mysqlconnector://user:pass@host:port/dbname
    pass
