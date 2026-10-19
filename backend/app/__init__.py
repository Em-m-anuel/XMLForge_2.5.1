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

    # Logs fichier (M-6) : actifs en mode gelé ou si XMLFORGE_FILE_LOGS=true.
    if flask_app.config.get('FILE_LOGS_ENABLED'):
        from .runtime import setup_file_logging
        setup_file_logging(flask_app)

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
        _skip_cp_check = "xml-bootstrap" in _sys.argv or "init-app" in _sys.argv
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

    @flask_app.cli.command('init-app')
    @click.option('--email', default=None, help="Email administrateur (ou env XMLFORGE_ADMIN_EMAIL)")
    @click.option('--name', default=None, help="Nom complet (ou env XMLFORGE_ADMIN_NAME)")
    @click.option('--password', default=None, help="Mot de passe (ou env XMLFORGE_ADMIN_PASSWORD)")
    def init_app_command(email, name, password):
        """Initialisation runtime non interactive : dossiers, secrets, bootstrap, admin.

        Destiné au premier lancement de l'application installée (mode automatisé).
        Les commandes interactives `xml-bootstrap` / `create-admin` restent
        inchangées pour le développement.
        """
        import json as _json
        from .runtime import prepare_runtime, bootstrap_if_needed, ensure_admin
        report = prepare_runtime()
        report.update(bootstrap_if_needed(flask_app))
        email = email or os.getenv('XMLFORGE_ADMIN_EMAIL')
        name = name or os.getenv('XMLFORGE_ADMIN_NAME')
        password = password or os.getenv('XMLFORGE_ADMIN_PASSWORD')
        if email and password:
            ok, message = ensure_admin(flask_app, email, name, password)
            if not ok:
                raise click.ClickException(message)
            report['admin'] = message
        else:
            report['admin'] = "aucun administrateur créé (--email/--password requis)"
        click.echo(_json.dumps(report, ensure_ascii=False, default=str))

    @flask_app.route('/health', methods=['GET'])
    @flask_app.route('/api/health', methods=['GET'])
    def health():
        return {"status": "ok", "service": "XMLForge Backend", "version": "5.0.0",
                "storage": "XML"}

    # --- Shutdown propre (Phase Final QA) ------------------------------------
    # Mécanisme sécurisé : admin JWT + local only (127.0.0.1 / ::1)
    # Pas de secret embarqué, pas d'endpoint public sans auth
    flask_app._xmlforge_shutting_down = False

    @flask_app.before_request
    def _check_shutting_down():
        # Pendant shutdown, refuser nouvelles requêtes sauf health et shutdown status
        if flask_app._xmlforge_shutting_down:
            from flask import request
            # Autoriser health pour vérification, et shutdown lui-même
            allowed_paths = ('/health', '/api/health', '/api/shutdown')
            if request.path not in allowed_paths:
                return error_response("Serveur en cours d'arrêt", 503)

    @flask_app.route('/api/shutdown', methods=['POST'])
    def shutdown():
        from flask import request
        from flask_jwt_extended import jwt_required, get_jwt_identity

        # Vérification JWT manuelle car décorateur dans factory doit être appliqué via wrapper
        # On utilise jwt_required en tant que décorateur via appel direct
        @jwt_required()
        def _protected():
            # Vérif admin — utilise PermissionService.is_admin (is_admin() méthode)
            from .control_plane import get_backend
            from .services.permission_service import PermissionService
            user_id = get_jwt_identity()
            try:
                uid = int(user_id)
            except Exception:
                return error_response("Token invalide", 401)
            backend = get_backend()
            user = backend.get_user(uid)
            if not user or not user.is_active:
                return error_response("Utilisateur inactif ou introuvable", 401)
            # is_admin() est une méthode dans UserView
            try:
                is_admin = PermissionService.is_admin(uid)
            except Exception:
                # fallback manuel
                is_admin = False
                try:
                    attr = getattr(user, 'is_admin', None)
                    if callable(attr):
                        is_admin = bool(attr())
                    else:
                        is_admin = bool(attr)
                except Exception:
                    is_admin = False
                if not is_admin:
                    role = backend.get_role(user.role_id) if hasattr(user, 'role_id') else None
                    if role and (role.name or '').lower() == 'admin':
                        is_admin = True
            if not is_admin:
                return error_response("Accès refusé — administrateur requis", 403)

            # Vérif local only : remote_addr doit être loopback
            remote = request.remote_addr or ''
            # Autoriser 127.0.0.0/8 et ::1
            is_local = remote.startswith('127.') or remote == '::1' or remote == '::ffff:127.0.0.1'
            if not is_local:
                # En dev, Werkzeug peut mettre remote None si test client, on autorise test client via header X-Test
                # Pour prod, on bloque non-local
                # On vérifie aussi si on est en TESTING
                if not flask_app.config.get('TESTING'):
                    return error_response("Shutdown autorisé uniquement en local (127.0.0.1)", 403)

            if flask_app._xmlforge_shutting_down:
                return {"status": "already_shutting_down", "message": "Arrêt déjà en cours"}

            flask_app._xmlforge_shutting_down = True
            logger.info("Shutdown demandé par %s (%s) depuis %s", user.email, user_id, remote)

            import threading

            def _do_shutdown():
                import time
                time.sleep(0.8)  # laisser réponse partir
                # 1. Arrêter TCP
                try:
                    tcp_srv = getattr(flask_app, 'tcp_server', None)
                    if tcp_srv:
                        tcp_srv.stop()
                        logger.info("TCPServer arrêté")
                except Exception as e:
                    logger.error("Erreur arrêt TCP: %s", e)
                # 2. Arrêter SocketIO / Flask
                try:
                    from .extensions import socketio
                    try:
                        socketio.stop()
                        logger.info("SocketIO arrêté")
                    except Exception:
                        pass
                except Exception as e:
                    logger.error("Erreur arrêt SocketIO: %s", e)
                # 3. Dernier recours : sortie processus (propre pour packaging Windows)
                # En TESTING, on ne fait pas os._exit pour ne pas tuer pytest/playwright
                if flask_app.config.get('TESTING'):
                    logger.info("TESTING mode — pas de os._exit, serveurs arrêtés seulement")
                    return
                time.sleep(0.5)
                logger.info("Arrêt processus XMLForge (os._exit)")
                import os
                os._exit(0)

            threading.Thread(target=_do_shutdown, daemon=True, name="xmlforge-shutdown").start()
            return {"status": "shutting_down", "message": "Arrêt en cours, TCP :3307 et Flask :5000 vont s'arrêter"}

        return _protected()

    # --- Frontend buildé (M-3) : servi par Flask en production -----------------
    # En développement (sans build), on conserve l'index JSON d'API.
    from . import paths as _paths
    _frontend_dist = flask_app.config.get('FRONTEND_DIST_FOLDER') or _paths.frontend_dist_folder()

    if _frontend_dist and os.path.isdir(_frontend_dist):
        from flask import send_from_directory

        @flask_app.route('/', methods=['GET'])
        def frontend_index():
            return send_from_directory(_frontend_dist, 'index.html')

        @flask_app.route('/<path:path>', methods=['GET'])
        def frontend_assets(path):
            # Les routes d'API inconnues doivent rester des 404 JSON, pas l'index HTML.
            if path.split('/', 1)[0] in ('api', 'socket.io'):
                return error_response("Ressource introuvable", 404)
            # Sécurité : bloquer les tentatives d'accès à des fichiers sensibles
            # même en mode SPA (le test test_security_no_file_exposure l'exige).
            lowered = path.lower()
            sensitive_prefixes = ('data/', 'control/', 'config/', 'logs/', 'tmp/', 'backend/')
            if lowered.startswith(sensitive_prefixes) or '..' in path or '%2e' in lowered:
                return error_response("Ressource introuvable", 404)
            target = os.path.join(_frontend_dist, path)
            if path and os.path.isfile(target):
                return send_from_directory(_frontend_dist, path)
            # Fallback SPA : les routes React profondes renvoient index.html.
            return send_from_directory(_frontend_dist, 'index.html')
    else:
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
