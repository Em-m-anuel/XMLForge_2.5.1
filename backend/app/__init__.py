"""
Factory Flask App XMLForge V2
- Ajout SocketIO
- Création tables avec nouvelles métadonnées V2
"""
import os
from flask import Flask
from .config import Config
from .extensions import db, jwt, bcrypt, cors, socketio
from .routes import register_routes

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

    @flask_app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok", "service": "XMLForge Backend V2", "version": "2.0.0"}

    @flask_app.route('/', methods=['GET'])
    def index():
        return {
            "service": "XMLForge Backend API V2",
            "version": "2.0.0",
            "features": ["UUID", "Comments", "Status ACTIVE/ARCHIVED", "Last user", "History V2 IP+before/after", "AuditLog", "SocketIO", "Converters"],
            "endpoints": [
                "POST /register", "POST /login", "GET /me", "POST /logout",
                "GET /databases", "POST /databases", "GET /databases/<id>", "PUT /databases/<id>", "DELETE /databases/<id>",
                "POST /databases/<id>/archive", "POST /databases/<id>/restore",
                "GET /databases/<id>/comment", "PUT /databases/<id>/comment",
                "GET /tables/<database_id>", "POST /tables", "PUT /tables/<id>", "DELETE /tables/<id>",
                "POST /tables/<id>/archive", "POST /tables/<id>/restore",
                "GET /tables/<id>/comment", "PUT /tables/<id>/comment",
                "GET /columns/<table_id>", "POST /columns", "PUT /columns/<id>", "DELETE /columns/<id>",
                "POST /columns/<id>/archive", "POST /columns/<id>/restore",
                "GET /columns/<id>/comment", "PUT /columns/<id>/comment",
                "POST /import/xml", "POST /import/sql",
                "GET /export/xml/<id>", "GET /export/sql/<id>",
                "POST /convert/xml-to-sql", "POST /convert/sql-to-xml",
                "POST /database/create", "POST /unlock-table",
                "GET /history", "GET /audit-logs",
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
