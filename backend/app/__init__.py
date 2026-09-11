"""Factory Flask App XMLForge — architecture XML-only (Phase 6J-B).

Aucune dépendance SQLite/SQLAlchemy : le Control Plane et le Data Plane sont
exclusivement en XML.
"""
import os
import logging
from flask import Flask
from .config import Config

logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    from .extensions import jwt, bcrypt, cors, socketio
    from .routes import register_routes

    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)
    if hasattr(config_class, 'validate'):
        config_class.validate()

    os.makedirs(flask_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(flask_app.config['EXPORT_FOLDER'], exist_ok=True)
    os.makedirs(flask_app.config['XML_STORAGE_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'uploads'), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'exports'), exist_ok=True)

    # Control Plane XML : dossier privé 0700, jamais servi en statique.
    from .xml_control import store as _xml_control_store
    _xml_control_store.ensure_dir(flask_app.config['CONTROL_STORAGE_FOLDER'], mode=0o700)

    jwt.init_app(flask_app)
    bcrypt.init_app(flask_app)
    cors.init_app(flask_app, resources={r"/*": {"origins": flask_app.config.get('CORS_ORIGINS', '*')}},
                  supports_credentials=True)
    socketio.init_app(flask_app, cors_allowed_origins=flask_app.config.get('CORS_ORIGINS', []))

    register_routes(flask_app)

    with flask_app.app_context():
        try:
            import app.socket_events  # noqa
        except Exception as e:
            print(f"[Socket] Erreur import socket_events: {e}")

        # Control Plane XML : fichiers requis ET valides (fail-closed).
        # La commande `xml-bootstrap` est l'exception : elle doit pouvoir
        # s'exécuter sur une installation vierge (avant création des fichiers).
        import sys as _sys
        _skip_cp_check = "xml-bootstrap" in _sys.argv
        if not _skip_cp_check:
            from .xml_control import store as _cp_store
            from .xml_control import records as _cp_records
            for name, xsd in (("security", "security.xsd"), ("catalog", "catalog.xsd"),
                              ("history", "history.xsd")):
                path = os.path.join(flask_app.config['CONTROL_STORAGE_FOLDER'], f"{name}.xml")
                if not os.path.exists(path):
                    raise RuntimeError(
                        "Control Plane XML non initialisé. Lancez d'abord "
                        "`flask xml-bootstrap` (installation XML vierge), puis "
                        "`flask create-admin`."
                    )
                _cp_store.read_validated(path, schema=_cp_records.schema_path(xsd))

        if flask_app.config.get('TCP_ENABLED', True):
            from .tcp import TCPServer
            try:
                tcp_server = TCPServer(
                    host=flask_app.config.get('TCP_HOST', '0.0.0.0'),
                    port=flask_app.config.get('TCP_PORT', 3307),
                    flask_app=flask_app,
                )
                tcp_server.start()
                flask_app.tcp_server = tcp_server
                logger.info("Serveur TCP/IP démarré sur le port %s", tcp_server.port)
            except Exception as e:
                logger.error(f"Erreur démarrage serveur TCP: {e}")
                flask_app.tcp_server = None
        else:
            flask_app.tcp_server = None

    from .errors import XMLForgeError
    from .utils.responses import error_response

    @flask_app.errorhandler(XMLForgeError)
    def handle_xmlforge_error(exc):
        return error_response(exc.message, exc.status_code, {"code": exc.code, "details": exc.details})

    @jwt.token_verification_loader
    def verify_active_user(_jwt_header, jwt_payload):
        from .control_plane import get_backend
        from .control_plane import volatile
        try:
            user = get_backend().get_user(int(jwt_payload.get("sub")))
            revoked = volatile.is_revoked(jwt_payload.get("jti"))
            return bool(
                user and user.is_active and not revoked and
                int(jwt_payload.get("token_version", 1)) == int(user.token_version or 1)
            )
        except Exception:
            return False

    @jwt.token_verification_failed_loader
    def inactive_or_invalid(_jwt_header, _jwt_payload):
        return error_response("Token invalide ou utilisateur inactif", 401)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response(f"Authentification requise: {reason}", 401)

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_payload):
        return error_response("Token expiré", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response(f"Token invalide: {reason}", 401)

    import click

    @flask_app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.option('--name', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin_command(email, name, password):
        """Crée/promote explicitement un administrateur (aucun email magique)."""
        from .control_plane import get_backend
        from .services.auth_service import AuthService
        backend = get_backend()
        user = backend.get_user_by_email(email.lower())
        if not user:
            user, error = AuthService.register(name, email, password)
            if error:
                raise click.ClickException(error)
        role = backend.get_role_by_name('admin')
        if role is None:
            role = backend.ensure_role('admin', 'Administrateur XMLForge')
        backend.update_user_fields(user.id, {"role_id": role.id, "is_active": True})
        click.echo(f"Administrateur prêt: {user.email}")

    @flask_app.cli.command('xml-bootstrap')
    def xml_bootstrap_command():
        """Initialise un Control Plane XML vierge (aucune dépendance SQLite)."""
        from .xml_control.service import XmlControlPlaneService
        service = XmlControlPlaneService.from_config(flask_app.config)
        report = service.bootstrap()
        click.echo(
            f"Control Plane XML initialisé dans {report['storage_folder']} "
            f"(rôles={report['roles']}, users={report['users']}, bases={report['databases']}). "
            "Créez ensuite un administrateur avec `flask create-admin`."
        )

    @flask_app.route('/health', methods=['GET'])
    def health():
        return {"status": "ok", "service": "XMLForge Backend", "version": "5.0.0",
                "storage": "XML"}

    @flask_app.route('/', methods=['GET'])
    def index():
        return {
            "service": "XMLForge Backend API (XML-only)",
            "version": "5.0.0",
            "storage": {"control_plane": "XML", "data_plane": "XML", "sqlite": "absent"},
            "endpoints": [
                "POST /register", "POST /login", "GET /me", "POST /logout",
                "GET /databases", "POST /databases", "GET /databases/<id>",
                "PUT /databases/<id>", "DELETE /databases/<id>",
                "GET /tables/<database_id>", "POST /tables", "PUT /tables/<id>", "DELETE /tables/<id>",
                "GET /columns/<table_id>", "POST /columns", "PUT /columns/<id>", "DELETE /columns/<id>",
                "POST /databases/<id>/query", "GET /databases/<id>/schema",
                "GET /tables/<id>/rows", "POST /tables/<id>/rows",
                "PUT /tables/<id>/rows/<row_id>", "DELETE /tables/<id>/rows/<row_id>",
                "POST /databases/<id>/permissions", "POST /tables/<id>/permissions",
                "POST /unlock-table", "POST /import/xml", "POST /import/sql",
                "GET /export/xml/<id>", "GET /export/sql/<id>",
                "POST /convert/xml-to-sql", "POST /convert/sql-to-xml",
                "GET /history (admin)", "GET /audit-logs (admin)",
                "GET /users (admin)", "POST /users (admin)",
                "GET /tcp/credentials", "GET /tcp/status",
            ]
        }

    return flask_app
