"""E2E réel TCP : framing, credentials, ACL, protection et CRUD."""
from __future__ import annotations

import socket
import time

import pytest

from app.services.access_service import AccessService
from app.tcp.tcp_protocol import TCPProtocol
from app.tcp.xmlforge_client import XMLForgeClient
from .helpers import create_user, create_database, create_table, create_column


def receive_message(sock):
    buffer = b""
    while len(buffer) < 5:
        chunk = sock.recv(65536)
        assert chunk
        buffer += chunk
    length = int.from_bytes(buffer[1:5], "big")
    while len(buffer) < 5 + length:
        chunk = sock.recv(65536)
        assert chunk
        buffer += chunk
    return TCPProtocol.unpack_message(buffer)


def raw_auth(host, port, username, password, database):
    sock = socket.create_connection((host, port), timeout=5)
    sock.sendall(TCPProtocol.create_auth_request(username, password, str(database)))
    return sock, receive_message(sock)


def test_tcp_auth_scopes_permissions_protection_and_structured_errors(e2e_environment):
    env, api = e2e_environment, e2e_environment.api
    owner, owner_token = create_user(api, "TCP Owner", "tcp-owner@example.com")
    guest, guest_token = create_user(api, "TCP Guest", "tcp-guest@example.com")

    personal = create_database(api, owner_token, "private_tcp", scope="PERSONAL")
    common = create_database(api, owner_token, "common_tcp", scope="COMMON", common_permission="EDIT")
    protected = create_table(
        api, owner_token, common["id"], "protected_items",
        protected=True, file_identifier="TCP-TABLE-SECRET",
    )
    create_column(
        api, owner_token, protected["id"], "id", "INTEGER",
        primary_key=True, auto_increment=True, nullable=False,
        key_identifier="TCP-TABLE-SECRET",
    )
    create_column(
        api, owner_token, protected["id"], "name", "VARCHAR",
        nullable=False, unique=True, key_identifier="TCP-TABLE-SECRET",
    )

    # COMMON + EDIT : accès collectif lecture/écriture, sans ACL individuelle.
    # Les grants individuels sur une base COMMON sont refusés.
    denied_grant = api.request(
        "POST", f"/api/databases/{common['id']}/permissions", token=owner_token,
        payload={"user_id": guest["id"], "can_read": True, "can_write": True},
    )
    assert denied_grant.status_code in (400, 403)

    tcp_credentials = api.request(
        "POST", "/api/tcp/credentials", token=guest_token,
        payload={"tcp_username": "guest-tcp", "tcp_password": "guest-tcp-password"},
    )
    assert tcp_credentials.status_code == 200

    with env.app.app_context():
        from app.control_plane import get_backend
        from app.data_plane import get_table
        guest_model = get_backend().get_user(guest["id"])
        protected_model = get_table(protected["id"])
        assert not AccessService.can_database(guest_model, personal["id"], "read")
        assert AccessService.can_database(guest_model, common["id"], "read")
        assert AccessService.can_table(guest_model, protected["id"], "write")
        assert not AccessService.can_table(guest_model, protected["id"], "ddl")

    # Auth sur PERSONAL non partagé : MSG_ERROR structuré AUTH_FAILED.
    denied_socket, denied = raw_auth(
        "127.0.0.1", env.tcp_server.port, "guest-tcp", "guest-tcp-password", personal["id"]
    )
    try:
        msg_type, payload, _ = denied
        assert msg_type == TCPProtocol.MSG_ERROR
        assert set(payload) == {"code", "message"}
        assert payload["code"] == TCPProtocol.AUTH_FAILED
        assert "non autorisée" in payload["message"]
    finally:
        denied_socket.close()

    # Auth valide puis write protégé sans unlock : erreur QUERY_ERROR structurée.
    raw_socket, auth_response = raw_auth(
        "127.0.0.1", env.tcp_server.port, "guest-tcp", "guest-tcp-password", common["id"]
    )
    try:
        msg_type, auth_payload, _ = auth_response
        assert msg_type == TCPProtocol.MSG_RESPONSE
        assert auth_payload["status"] == TCPProtocol.AUTH_SUCCESS
        token = auth_payload["session_token"]
        raw_socket.sendall(TCPProtocol.create_query_request(
            "INSERT INTO protected_items (name) VALUES ('blocked')", token
        ))
        error_type, error_payload, _ = receive_message(raw_socket)
        assert error_type == TCPProtocol.MSG_ERROR
        # Phase 7 : le message d'erreur porte désormais un code métier.
        assert set(error_payload) == {"code", "message", "error_code"}
        assert error_payload["code"] == TCPProtocol.QUERY_ERROR
        assert error_payload["error_code"] == "ACCESS_DENIED"
        assert "protégée" in error_payload["message"] or "clé" in error_payload["message"].lower()
        raw_socket.sendall(TCPProtocol.create_close(token))
        close_type, close_payload, _ = receive_message(raw_socket)
        assert close_type == TCPProtocol.MSG_RESPONSE
        assert close_payload["closed"] is True
    finally:
        raw_socket.close()

    # Client officiel : unlock individuel puis CRUD réel.
    client = XMLForgeClient("127.0.0.1", env.tcp_server.port, timeout=5)
    assert client.connect("guest-tcp", "guest-tcp-password", str(common["id"]))
    with pytest.raises(RuntimeError):
        client.insert("protected_items", {"name": "still-blocked"})
    with pytest.raises(RuntimeError):
        client.unlock_table("protected_items", "wrong")
    assert client.unlock_table("protected_items", "TCP-TABLE-SECRET")
    assert client.insert("protected_items", {"name": "created-over-tcp"}) == 1
    selected = client.select("protected_items", where="name='created-over-tcp'")
    assert selected == [{"id": 1, "name": "created-over-tcp"}]
    assert client.update("protected_items", {"name": "updated-over-tcp"}, "id=1") == 1
    assert client.delete("protected_items", "id=1") == 1

    # Un changement de scope (COMMON -> PERSONAL) retire l'accès collectif dans
    # une session déjà connectée.
    revoked = api.request(
        "PUT", f"/api/databases/{common['id']}", token=owner_token,
        payload={"scope": "PERSONAL"},
    )
    assert revoked.status_code == 200
    with pytest.raises(RuntimeError, match="Permission"):
        client.select("protected_items")
    client.disconnect()

    # La fermeture propre retire la session côté serveur (attente bornée réseau).
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if all(session["user_id"] != guest["id"] for session in env.tcp_server.get_sessions_info()):
            break
        time.sleep(0.02)
    assert all(session["user_id"] != guest["id"] for session in env.tcp_server.get_sessions_info())
