"""Serveur TCP/IP XMLForge, transport du même moteur que REST."""
from __future__ import annotations
import logging
import socket
import threading
import uuid
from datetime import datetime, timedelta
from .tcp_protocol import TCPProtocol

logger = logging.getLogger(__name__)


class ClientSession:
    def __init__(self, address, timeout_minutes=30):
        self.address = address
        self.token = str(uuid.uuid4())
        self.user_id = None
        self.username = None
        self.database_id = None
        self.database_name = None
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.authenticated = False
        self.timeout_minutes = timeout_minutes
        # Transaction (Phase 7) : snapshot du document XML de la base courante.
        self.transaction_active = False
        self.transaction_snapshot = None
        self.transaction_path = None

    def is_expired(self):
        return datetime.utcnow() - self.last_activity > timedelta(minutes=self.timeout_minutes)

    def update_activity(self):
        self.last_activity = datetime.utcnow()


class TCPServer:
    def __init__(self, host="0.0.0.0", port=3307, flask_app=None):
        self.host, self.port, self.flask_app = host, port, flask_app
        self.running = False
        self.socket = None
        self.sessions = {}
        self.thread = None
        self.lock = threading.RLock()

    def start(self):
        if self.running:
            return
        # Le bind est synchrone : /status ne peut pas annoncer un faux succès.
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.port = self.socket.getsockname()[1]
        self.socket.listen(64)
        self.socket.settimeout(1)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True, name="xmlforge-tcp")
        self.thread.start()

    def stop(self):
        self.running = False
        # Rollback implicite de toutes les transactions actives avant arrêt
        # — garantit que BEGIN + INSERT + SHUTDOWN sans COMMIT ne laisse pas de données
        try:
            with self.lock:
                sessions_copy = list(self.sessions.values())
            for sess in sessions_copy:
                if not getattr(sess, 'transaction_active', False):
                    continue
                try:
                    from ..xml_control import store as _store
                    tp = getattr(sess, 'transaction_path', None)
                    ts = getattr(sess, 'transaction_snapshot', None)
                    if not isinstance(tp, dict) or not isinstance(ts, dict):
                        continue
                    xml_path = tp.get("xml")
                    catalog_path = tp.get("catalog")
                    xml_snap = ts.get("xml")
                    catalog_snap = ts.get("catalog")
                    if xml_path and xml_snap and hasattr(xml_snap, 'exists'):
                        _store.restore(xml_path, xml_snap)
                    if catalog_path and catalog_snap and hasattr(catalog_snap, 'exists'):
                        _store.restore(catalog_path, catalog_snap)
                    logger.info("Rollback implicite transaction session %s (%s)", getattr(sess, 'token', '?')[:8], getattr(sess, 'username', '?'))
                except Exception as e:
                    logger.error("Erreur rollback implicite session %s: %s", getattr(sess, 'token', '?')[:8], e)
                finally:
                    sess.transaction_active = False
                    sess.transaction_snapshot = None
                    sess.transaction_path = None
        except Exception as e:
            logger.error("Erreur rollback global shutdown: %s", e)

        if self.socket:
            try: self.socket.close()
            except OSError: pass
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=5)
        with self.lock:
            self.sessions.clear()

    def _run(self):
        while self.running:
            try:
                client, address = self.socket.accept()
                threading.Thread(target=self._handle_client, args=(client, address), daemon=True).start()
            except socket.timeout:
                self._purge_expired()
            except OSError:
                if self.running: logger.exception("Erreur accept TCP")
                break

    def _handle_client(self, client, address):
        client.settimeout(2)
        buffer = b""
        connection_tokens = set()
        try:
            while self.running:
                try:
                    chunk = client.recv(65536)
                    if not chunk: break
                    buffer += chunk
                    # Limite de 8 MiB par connexion/buffer.
                    if len(buffer) > 8 * 1024 * 1024:
                        client.sendall(TCPProtocol.create_error(TCPProtocol.INVALID_REQUEST, "Message trop volumineux"))
                        break
                    while len(buffer) >= 5:
                        try:
                            msg_type, data, consumed = TCPProtocol.unpack_message(buffer)
                        except ValueError as exc:
                            if "incomplet" in str(exc): break
                            raise
                        buffer = buffer[consumed:]
                        response, session, close = self._process_message(msg_type, data, address)
                        if session: connection_tokens.add(session.token)
                        if response: client.sendall(response)
                        if close: return
                except socket.timeout:
                    continue
        except Exception:
            logger.exception("Erreur client TCP %s", address)
        finally:
            try: client.close()
            except OSError: pass
            with self.lock:
                for token in connection_tokens:
                    sess = self.sessions.get(token)
                    if sess and getattr(sess, 'transaction_active', False):
                        try:
                            from ..xml_control import store as _store
                            tp = getattr(sess, 'transaction_path', None)
                            ts = getattr(sess, 'transaction_snapshot', None)
                            if isinstance(tp, dict) and isinstance(ts, dict):
                                xml_path = tp.get("xml")
                                catalog_path = tp.get("catalog")
                                xml_snap = ts.get("xml")
                                catalog_snap = ts.get("catalog")
                                if xml_path and xml_snap and hasattr(xml_snap, 'exists'):
                                    _store.restore(xml_path, xml_snap)
                                if catalog_path and catalog_snap and hasattr(catalog_snap, 'exists'):
                                    _store.restore(catalog_path, catalog_snap)
                                logger.info("Rollback implicite à la déconnexion session %s", token[:8])
                        except Exception as e:
                            logger.error("Erreur rollback déconnexion %s: %s", token[:8], e)
                    self.sessions.pop(token, None)

    def _session(self, data):
        token = data.get("session_token")
        with self.lock:
            session = self.sessions.get(token)
            if session and session.is_expired():
                self.sessions.pop(token, None); session = None
        return session

    def _process_message(self, msg_type, data, address):
        if msg_type == TCPProtocol.MSG_PING:
            return TCPProtocol.create_pong(), None, False
        if msg_type == TCPProtocol.MSG_AUTH:
            response, session = self._handle_auth(data, address)
            return response, session, False
        session = self._session(data)
        if not session or not session.authenticated:
            return TCPProtocol.create_error(TCPProtocol.SESSION_EXPIRED, "Session absente ou expirée"), None, False
        session.update_activity()
        if msg_type == TCPProtocol.MSG_QUERY:
            return self._handle_query(data, session), session, False
        if msg_type == TCPProtocol.MSG_SELECT_DATABASE:
            return self._handle_select_database(data, session), session, False
        if msg_type == TCPProtocol.MSG_UNLOCK_TABLE:
            return self._handle_unlock(data, session), session, False
        if msg_type == TCPProtocol.MSG_CLOSE:
            if getattr(session, 'transaction_active', False):
                try:
                    from ..xml_control import store as _store
                    tp = getattr(session, 'transaction_path', None)
                    ts = getattr(session, 'transaction_snapshot', None)
                    if isinstance(tp, dict) and isinstance(ts, dict):
                        xml_path = tp.get("xml")
                        catalog_path = tp.get("catalog")
                        xml_snap = ts.get("xml")
                        catalog_snap = ts.get("catalog")
                        if xml_path and xml_snap and hasattr(xml_snap, 'exists'):
                            _store.restore(xml_path, xml_snap)
                        if catalog_path and catalog_snap and hasattr(catalog_snap, 'exists'):
                            _store.restore(catalog_path, catalog_snap)
                        logger.info("Rollback implicite à la fermeture CLOSE session %s", session.token[:8])
                except Exception as e:
                    logger.error("Erreur rollback CLOSE %s: %s", session.token[:8], e)
                finally:
                    session.transaction_active = False
                    session.transaction_snapshot = None
                    session.transaction_path = None
            with self.lock: self.sessions.pop(session.token, None)
            return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS, {"closed": True}), session, True
        return TCPProtocol.create_error(TCPProtocol.INVALID_REQUEST, "Type de message inconnu"), session, False

    def _handle_auth(self, data, address):
        username, password = data.get("username"), data.get("password")
        if not username or not password:
            return TCPProtocol.create_error(TCPProtocol.AUTH_FAILED, "Username et password TCP requis"), None
        with self.flask_app.app_context():
            from ..services.tcp_credential_service import TcpCredentialService
            from ..services.unlock_service import UnlockService
            user = TcpCredentialService.authenticate(username, password)
            if not user:
                return TCPProtocol.create_error(TCPProtocol.AUTH_FAILED, "Credentials TCP invalides"), None
            # Reconnexion = nouvelle session de protection.
            UnlockService.clear_user_unlocks(user.id)
            timeout = self.flask_app.config.get("TCP_SESSION_TIMEOUT_MINUTES", 30)
            session = ClientSession(address, timeout)
            session.user_id, session.username, session.authenticated = user.id, user.email, True
            with self.lock: self.sessions[session.token] = session
            if data.get("database") is not None:
                error = self._select_database_for_session(session, data.get("database"))
                if error:
                    with self.lock: self.sessions.pop(session.token, None)
                    return TCPProtocol.create_error(TCPProtocol.AUTH_FAILED, error), None
            payload = {
                "session_token": session.token, "user_id": user.id,
                "username": user.email, "full_name": user.full_name,
                "expires_in_seconds": timeout * 60,
            }
            if session.database_id:
                payload.update({"database_id": session.database_id, "database_name": session.database_name})
            return TCPProtocol.create_response(TCPProtocol.AUTH_SUCCESS, payload), session

    def _select_database_for_session(self, session, selector):
        from ..services.permission_service import PermissionService
        if isinstance(selector, int) or str(selector).isdigit():
            candidates = [PermissionService._database(int(selector))]
        else:
            candidates = [d for d in PermissionService.accessible_databases(session.user_id, include_archived=False)
                          if d.name == str(selector)]
        candidates = [d for d in candidates if d and PermissionService.can_database(session.user_id, d, "read")]
        if not candidates: return "Base introuvable ou non autorisée"
        if len(candidates) > 1: return "Nom de base ambigu; utilisez database_id"
        session.database_id, session.database_name = candidates[0].id, candidates[0].name
        return None

    def _handle_select_database(self, data, session):
        with self.flask_app.app_context():
            error = self._select_database_for_session(session, data.get("database"))
            if error: return TCPProtocol.create_error(TCPProtocol.QUERY_ERROR, error)
            return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS, {
                "database_id": session.database_id, "database_name": session.database_name
            })

    def _business_error_code(self, exc):
        """Code métier XMLForge exposé dans les erreurs TCP (champ error_code)."""
        from ..errors import (
            ConstraintViolation, DataValidationError, NotFoundError, PermissionDenied,
            ValidationFailed, XmlValidationError, ConflictError, StorageError,
        )
        message = str(exc)
        if isinstance(exc, PermissionDenied):
            return "ACCESS_DENIED"
        if isinstance(exc, ConflictError):
            return "CONFLICT"
        if isinstance(exc, ConstraintViolation):
            return "CONSTRAINT_VIOLATION"
        if isinstance(exc, DataValidationError):
            return "DATA_INVALID"
        if isinstance(exc, NotFoundError):
            if "Colonne" in message or "colonne" in message:
                return "COLUMN_NOT_FOUND"
            if "Table" in message or "table" in message:
                return "TABLE_NOT_FOUND"
            return "DATABASE_NOT_FOUND"
        if isinstance(exc, XmlValidationError):
            return "INVALID_QUERY"
        if isinstance(exc, ValidationFailed):
            return "SYNTAX_ERROR"
        if isinstance(exc, StorageError):
            return "INTERNAL_ERROR"
        return "INTERNAL_ERROR"

    def _error(self, numeric, message, exc=None, error_code=None):
        code = error_code or (self._business_error_code(exc) if exc is not None else None)
        return TCPProtocol.create_error(numeric, message, error_code=code)

    def _handle_query(self, data, session):
        try:
            with self.flask_app.app_context():
                from ..query.sql_parser import parse_sql_statement
                from ..query.xml_query_service import XmlQueryService
                from ..services.audit_service import AuditService
                query = data.get("query", "")
                provided_key = data.get("table_key")
                expected_version = data.get("expected_version")

                statement = parse_sql_statement(query)
                operation = statement["operation"]

                # Énoncés de session (Phase 7) : traités au niveau connexion.
                if operation == "use":
                    error = self._select_database_for_session(session, statement["database"])
                    if error:
                        return self._error(TCPProtocol.QUERY_ERROR, error)
                    return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS, {
                        "engine": "xml",
                        "result": {"database_id": session.database_id,
                                   "database_name": session.database_name},
                    })
                if operation == "begin":
                    return self._tx_begin(session)
                if operation == "commit":
                    return self._tx_commit(session)
                if operation == "rollback":
                    return self._tx_rollback(session)

                if not session.database_id:
                    return self._error(TCPProtocol.QUERY_ERROR,
                                       "Aucune base sélectionnée (utilisez USE)",
                                       error_code="DATABASE_NOT_SELECTED")

                payload = {"engine": "xml"}
                xml_payload = XmlQueryService.execute_sql(
                    session.database_id, session.user_id, query,
                    provided_key=provided_key, expected_version=expected_version,
                )
                payload["result"] = xml_payload["result"]
                payload["metrics"] = xml_payload["metrics"]

                if operation == "drop_database" and statement.get("name") == session.database_name:
                    session.database_id = None
                    session.database_name = None

                AuditService.log(user_id=session.user_id, user_name=session.username,
                                 ip_address=session.address[0] if session.address else None,
                                 action="TCP_QUERY", element_type="base",
                                 element_name=session.database_name or "-",
                                 meta={"operation": operation, "engine": "xml"})
                return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS, payload)
        except Exception as exc:
            return self._error(TCPProtocol.QUERY_ERROR, str(exc), exc)

    # ------------------------------------------------------------------ transactions
    def _tx_begin(self, session):
        if not session.database_id:
            return self._error(TCPProtocol.QUERY_ERROR, "Aucune base sélectionnée (utilisez USE)")
        if session.transaction_active:
            return self._error(TCPProtocol.QUERY_ERROR, "Une transaction est déjà active",
                               error_code="TRANSACTION_ACTIVE")
        from ..data_plane import get_data_plane
        from ..xml_control import store
        dp = get_data_plane()
        database = dp.get_database(session.database_id)
        xml_path = dp.xml_path(database)
        catalog_path = dp.cp_service.catalog_path()
        # Snapshot des deux artefacts : le document XML de la base ET le miroir
        # catalog.xml (document_version / checksum) — cohérence au ROLLBACK.
        session.transaction_snapshot = {
            "xml": store.snapshot(xml_path),
            "catalog": store.snapshot(catalog_path),
        }
        session.transaction_path = {"xml": xml_path, "catalog": catalog_path}
        session.transaction_active = True
        return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS,
                                           {"engine": "xml", "result": {"transaction": "BEGIN"}})

    def _tx_commit(self, session):
        if not session.transaction_active:
            return self._error(TCPProtocol.QUERY_ERROR, "Aucune transaction active",
                               error_code="TRANSACTION_NOT_ACTIVE")
        session.transaction_active = False
        session.transaction_snapshot = None
        session.transaction_path = None
        from ..services.audit_service import AuditService
        AuditService.log(user_id=session.user_id, user_name=session.username,
                         action="TRANSACTION_COMMIT", element_type="base",
                         element_name=session.database_name)
        return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS,
                                           {"engine": "xml", "result": {"transaction": "COMMIT"}})

    def _tx_rollback(self, session):
        if not session.transaction_active:
            return self._error(TCPProtocol.QUERY_ERROR, "Aucune transaction active",
                               error_code="TRANSACTION_NOT_ACTIVE")
        from ..xml_control import store
        try:
            store.restore(session.transaction_path["xml"], session.transaction_snapshot["xml"])
            store.restore(session.transaction_path["catalog"], session.transaction_snapshot["catalog"])
        except Exception as exc:
            return self._error(TCPProtocol.QUERY_ERROR, f"ROLLBACK impossible: {exc}", exc,
                               error_code="TRANSACTION_ERROR")
        session.transaction_active = False
        session.transaction_snapshot = None
        session.transaction_path = None
        from ..services.audit_service import AuditService
        AuditService.log(user_id=session.user_id, user_name=session.username,
                         action="TRANSACTION_ROLLBACK", element_type="base",
                         element_name=session.database_name)
        return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS,
                                           {"engine": "xml", "result": {"transaction": "ROLLBACK"}})

    def _handle_unlock(self, data, session):
        try:
            with self.flask_app.app_context():
                from ..data_plane import resolve_table
                from ..services.table_service import TableService
                selector = data.get("table")
                table = resolve_table(session.database_id, selector)
                if not table or table.database_id != session.database_id:
                    raise ValueError("Table introuvable")
                ok, message = TableService.unlock(table.id, data.get("key"), user_id=session.user_id)
                if not ok: return TCPProtocol.create_error(TCPProtocol.QUERY_ERROR, message)
                return TCPProtocol.create_response(TCPProtocol.QUERY_SUCCESS, {"unlocked": True, "table_id": table.id})
        except Exception as exc:
            return TCPProtocol.create_error(TCPProtocol.QUERY_ERROR, str(exc))

    def _purge_expired(self):
        with self.lock:
            for token, session in list(self.sessions.items()):
                if session.is_expired():
                    if getattr(session, 'transaction_active', False):
                        try:
                            from ..xml_control import store as _store
                            tp = getattr(session, 'transaction_path', None)
                            ts = getattr(session, 'transaction_snapshot', None)
                            if isinstance(tp, dict) and isinstance(ts, dict):
                                xml_path = tp.get("xml")
                                catalog_path = tp.get("catalog")
                                xml_snap = ts.get("xml")
                                catalog_snap = ts.get("catalog")
                                if xml_path and xml_snap and hasattr(xml_snap, 'exists'):
                                    _store.restore(xml_path, xml_snap)
                                if catalog_path and catalog_snap and hasattr(catalog_snap, 'exists'):
                                    _store.restore(catalog_path, catalog_snap)
                                logger.info("Rollback implicite expiration session %s", token[:8])
                        except Exception as e:
                            logger.error("Erreur rollback expiration %s: %s", token[:8], e)
                    self.sessions.pop(token, None)

    def get_sessions_info(self):
        self._purge_expired()
        with self.lock:
            return [{
                "token": token[:8] + "...", "user_id": s.user_id, "user": s.username,
                "database_id": s.database_id, "database": s.database_name,
                "connected_at": s.created_at.isoformat(), "last_activity": s.last_activity.isoformat(),
            } for token, s in self.sessions.items()]
