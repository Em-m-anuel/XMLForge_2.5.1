"""Connexion TCP XMLForge (Phase 7) — client officiel."""

import socket

from . import protocol
from .errors import XmlforgeError
from .result import Result

SESSION_EXPIRED = protocol.SESSION_EXPIRED


class Connection:
    """Une connexion authentifiée au serveur TCP XMLForge (:3307)."""

    def __init__(self, host="localhost", port=3307, timeout=10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self.session_token = None
        self.user_id = None
        self.username = None
        self.database_id = None
        self.database_name = None

    # ------------------------------------------------------------------ I/O
    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise XmlforgeError("Connexion fermée par le serveur", code="CONNECTION_ERROR")
            buf += chunk
        return buf

    def _recv_frame(self):
        header = self._recv_exact(5)
        try:
            msg_type, data, _ = protocol.unpack_message(header + self._recv_exact(
                int.from_bytes(header[1:5], "big")))
        except Exception as exc:
            raise XmlforgeError(f"Réponse malformée: {exc}", code="CONNECTION_ERROR")
        return msg_type, data

    def _send(self, frame):
        self._sock.sendall(frame)

    @staticmethod
    def _numeric_code_name(numeric):
        if numeric == protocol.AUTH_FAILED:
            return "AUTH_FAILED"
        if numeric == protocol.SESSION_EXPIRED:
            return "SESSION_ERROR"
        if numeric == protocol.INVALID_REQUEST:
            return "INVALID_QUERY"
        if numeric == protocol.QUERY_ERROR:
            return "INTERNAL_ERROR"
        return "INTERNAL_ERROR"

    def _request(self, frame):
        self._send(frame)
        msg_type, data = self._recv_frame()
        if msg_type == protocol.MSG_ERROR:
            numeric = data.get("code")
            if numeric == SESSION_EXPIRED:
                self.session_token = None
            raise XmlforgeError(data.get("message", "Erreur serveur"),
                                code=data.get("error_code") or self._numeric_code_name(numeric),
                                numeric_code=numeric)
        if msg_type != protocol.MSG_RESPONSE:
            raise XmlforgeError("Réponse inattendue du serveur", code="CONNECTION_ERROR")
        return data

    # ------------------------------------------------------------------ lifecycle
    def connect(self):
        """Ouvre la socket TCP (sans authentifier)."""
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock.settimeout(self.timeout)
        return self

    def authenticate(self, username, password, database=None):
        """Authentifie la connexion ; sélectionne éventuellement une base."""
        if self._sock is None:
            self.connect()
        data = self._request(protocol.auth_request(username, password, database))
        if data.get("status") != protocol.AUTH_SUCCESS:
            raise XmlforgeError("Authentification échouée", code="AUTH_FAILED")
        self.session_token = data.get("session_token")
        self.user_id = data.get("user_id")
        self.username = data.get("username")
        self.database_id = data.get("database_id")
        self.database_name = data.get("database_name")
        return self

    def use(self, database):
        """Sélectionne la base courante (équivaut à ``USE database``)."""
        result = self.execute(f"USE {database}")
        self.database_id = result.metadata.get("database_id")
        self.database_name = result.metadata.get("database_name")
        return self

    def execute(self, sql, expected_version=None, table_key=None):
        """Exécute une instruction SQL (SELECT, INSERT, UPDATE, DELETE, DDL, USE,
        BEGIN, COMMIT, ROLLBACK). Retourne un ``Result``."""
        if self.session_token is None:
            raise XmlforgeError("Connexion non authentifiée", code="AUTH_REQUIRED")
        data = self._request(protocol.query_request(
            sql, self.session_token, expected_version=expected_version, table_key=table_key))
        operation = sql.strip().split(" ", 1)[0].upper() if sql.strip() else ""
        result = Result(raw=data.get("result"), operation=operation)
        # Synchronise la base courante après USE (y compris via execute("USE …")).
        if result.metadata.get("database_id") is not None:
            self.database_id = result.metadata.get("database_id")
            self.database_name = result.metadata.get("database_name")
        return result

    def query(self, sql, expected_version=None, table_key=None):
        """Alias de ``execute`` pour les SELECT (retourne un ``Result``)."""
        return self.execute(sql, expected_version=expected_version, table_key=table_key)

    def close(self):
        """Ferme proprement la session et la socket."""
        if self._sock is not None:
            try:
                if self.session_token:
                    self._send(protocol.close_request(self.session_token))
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self.session_token = None

    # ------------------------------------------------------------------ context manager
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
