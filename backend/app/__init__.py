"""
Factory Flask App XMLForge V4
- V2 métadonnées
- V3 XML source de vérité
- V4 admin, rows, unlocks personnels, Monaco, project export
"""
import os
import logging
from flask import Flask
from .config import Config
from .extensions import db, jwt, bcrypt, cors, socketio
from .routes import register_routes
from .tcp import TCPServer

logger = logging.getLogger(__name__)

def create_app(config_class=Config):
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)

    os.makedirs(flask_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(flask_app.config['EXPORT_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'exports'), exist_ok=True)

    # Extensions
    db.init_app(flask_app)
    jwt.init_app(flask_app)
    bcrypt.init_app(flask_app)
    cors.init_app(flask_app, resources={r"/*": {"origins": flask_app.config.get('CORS_ORIGINS', '*')}}, supports_credentials=True)
    socketio.init_app(flask_app, cors_allowed_origins="*")

    # Blueprints
    register_routes(flask_app)

    # Socket events
    with flask_app.app_context():
        try:
            import app.socket_events  # noqa
        except Exception as e:
            print(f"[Socket] Erreur import socket_events: {e}")

    # Créer tables
    with flask_app.app_context():
        db.create_all()
        try:
            _migrate_v2(flask_app)
        except Exception as e:
            print(f"[Migration V2] Note: {e}")
        try:
            _migrate_v4(flask_app)
        except Exception as e:
            print(f"[Migration V4] Note: {e}")
        
        # Initialiser le serveur TCP/IP
        try:
            tcp_server = TCPServer(host='0.0.0.0', port=3307, flask_app=flask_app)
            tcp_server.start()
            flask_app.tcp_server = tcp_server
            logger.info("Serveur TCP/IP démarré sur le port 3307")
        except Exception as e:
            logger.error(f"Erreur démarrage serveur TCP: {e}")
            flask_app.tcp_server = None

    @flask_app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok", "service": "XMLForge Backend V4", "version": "4.0.0"}

    @flask_app.route('/', methods=['GET'])
    def index():
        return {
            "service": "XMLForge Backend API V4",
            "version": "4.0.0",
            "features": [
                "UUID", "Comments (legacy)", "Status ACTIVE/ARCHIVED", "Last user",
                "History V2 IP+before/after", "AuditLog", "SocketIO", "Converters",
                "Admin only nyx@xmlforge.io", "Users management",
                "Table rows / data", "Monaco Editor", "Personal unlocks",
                "Project export/import with rows", "TCP/IP Server"
            ],
            "endpoints": [
                "POST /register", "POST /login", "GET /me", "POST /logout",
                "GET /databases", "POST /databases", "GET /databases/<id>", "PUT /databases/<id>", "DELETE /databases/<id>",
                "POST /databases/<id>/archive", "POST /databases/<id>/restore",
                "GET /tables/<database_id>", "POST /tables", "PUT /tables/<id>", "DELETE /tables/<id>",
                "POST /tables/<id>/archive", "POST /tables/<id>/restore",
                "GET /columns/<table_id>", "POST /columns", "PUT /columns/<id>", "DELETE /columns/<id>",
                "POST /import/xml", "POST /import/sql",
                "GET /export/xml/<id>", "GET /export/sql/<id>",
                "GET /export/table-xml/<id>", "GET /export/table-sql/<id>",
                "POST /convert/xml-to-sql", "POST /convert/sql-to-xml",
                "POST /database/create", "POST /unlock-table",
                "GET /history (admin)", "GET /audit-logs (admin)",
                "GET /users (admin)", "POST /users (admin)", "PUT /users/<id> (admin)", "DELETE /users/<id> (admin)", "POST /users/<id>/reset-password (admin)", "POST /users/<id>/toggle-active (admin)",
                "GET /tables/<id>/rows", "POST /tables/<id>/rows", "PUT /tables/<id>/rows/<row_id>", "DELETE /tables/<id>/rows/<row_id>",
                "GET /export/project/<id>", "POST /import/project",
                "GET /tcp/credentials", "POST /tcp/credentials/show-password", "GET /tcp/sessions", "GET /tcp/status",
                "WebSocket events: new_database, new_table, new_column, modification, suppression, import_xml, export_sql, xmlforge_event"
            ]
        }

    return flask_app

def _migrate_v2(flask_app):
    from sqlalchemy import text
    checks = [
        ("databases", "uuid", "VARCHAR(36)"),
        ("databases", "comment", "TEXT"),
        ("databases", "status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
        ("databases", "last_modified_by_id", "INTEGER"),
        ("databases", "last_modified_by_name", "VARCHAR(120)"),
        ("tables", "uuid", "VARCHAR(36)"),
        ("tables", "comment", "TEXT"),
        ("tables", "status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
        ("tables", "last_modified_by_id", "INTEGER"),
        ("tables", "last_modified_by_name", "VARCHAR(120)"),
        ("tables", "file_identifier", "VARCHAR(64)"),
        ("columns", "uuid", "VARCHAR(36)"),
        ("columns", "comment", "TEXT"),
        ("columns", "status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
        ("columns", "last_modified_by_id", "INTEGER"),
        ("columns", "last_modified_by_name", "VARCHAR(120)"),
        ("columns", "updated_at", "DATETIME"),
        ("history", "uuid", "VARCHAR(36)"),
        ("history", "ip_address", "VARCHAR(45)"),
        ("history", "before_data", "TEXT"),
        ("history", "after_data", "TEXT"),
    ]
    with flask_app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        for table, column, coltype in checks:
            try:
                if table not in inspector.get_table_names():
                    continue
                cols = [c['name'] for c in inspector.get_columns(table)]
                if column not in cols:
                    sql = f'ALTER TABLE {table} ADD COLUMN {column} {coltype}'
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"[Migration V2] Ajouté {table}.{column}")
            except Exception as e:
                print(f"[Migration V2] Skip {table}.{column}: {e}")
                try:
                    db.session.rollback()
                except:
                    pass

def _migrate_v4(flask_app):
    from sqlalchemy import text, inspect
    checks = [
        ("users", "is_active", "BOOLEAN DEFAULT 1"),
        ("users", "last_login", "DATETIME"),
        ("users", "updated_at", "DATETIME"),
        ("table_rows", "id", "INTEGER"),  # dummy check, create_all will handle
        ("table_unlocks", "id", "INTEGER"),
    ]
    # For users table, add missing columns
    user_checks = [
        ("users", "is_active", "BOOLEAN DEFAULT 1"),
        ("users", "last_login", "DATETIME"),
        ("users", "updated_at", "DATETIME"),
    ]
    with flask_app.app_context():
        inspector = inspect(db.engine)
        if "users" in inspector.get_table_names():
            cols = [c['name'] for c in inspector.get_columns("users")]
            for table, column, coltype in user_checks:
                if column not in cols:
                    try:
                        if "BOOLEAN" in coltype:
                            # SQLite BOOLEAN is INTEGER
                            sql = f'ALTER TABLE {table} ADD COLUMN {column} INTEGER DEFAULT 1'
                        else:
                            sql = f'ALTER TABLE {table} ADD COLUMN {column} {coltype}'
                        db.session.execute(text(sql))
                        db.session.commit()
                        print(f"[Migration V4] Ajouté {table}.{column}")
                    except Exception as e:
                        print(f"[Migration V4] Skip {table}.{column}: {e}")
                        try:
                            db.session.rollback()
                        except:
                            pass
        # Ensure new tables exist (create_all already called, but just in case)
        try:
            db.create_all()
        except Exception as e:
            print(f"[Migration V4] create_all error: {e}")
