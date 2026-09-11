import socket
import pytest
from app.tcp.tcp_server import TCPServer, ClientSession
from app.tcp.xmlforge_client import XMLForgeClient
from .conftest import register_and_login, auth


def free_port():
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close(); return port


def test_tcp_crud_permissions_multiple_clients_and_timeout(app, client):
    alice, token = register_and_login(client, "Alice", "alice@example.com")
    database = client.post('/databases', json={"name": "tcp_db"}, headers=auth(token)).get_json()["data"]
    table = client.post('/tables', json={"name": "items", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INTEGER", "table_id": table["id"], "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": table["id"], "nullable": False}, headers=auth(token))
    tcp = client.post('/api/tcp/credentials', json={"tcp_password": "tcp-secret"}, headers=auth(token)).get_json()["data"]

    bob, bob_token = register_and_login(client, "Bob", "bob@example.com")
    client.post('/api/tcp/credentials', json={"tcp_password": "bob-secret"}, headers=auth(bob_token))

    port = free_port(); server = TCPServer('127.0.0.1', port, app); server.start()
    try:
        external = XMLForgeClient('127.0.0.1', port, timeout=5)
        assert external.connect(tcp["credential"]["tcp_username"], "tcp-secret", str(database["id"]))
        assert external.insert('items', {"name": "one"}) == 1
        assert external.select('items', where="id=1")[0]["name"] == "one"
        assert external.update('items', {"name": "updated"}, "id=1") == 1
        assert external.delete('items', "id=1") == 1

        second = XMLForgeClient('127.0.0.1', port, timeout=5)
        assert second.connect(tcp["credential"]["tcp_username"], "tcp-secret", str(database["id"]))
        assert len(server.get_sessions_info()) == 2
        second.disconnect()
        external.disconnect()

        forbidden = XMLForgeClient('127.0.0.1', port, timeout=5)
        with pytest.raises(ConnectionError):
            forbidden.connect("bob@example.com", "bob-secret", str(database["id"]))
    finally:
        server.stop()
    assert ClientSession(('127.0.0.1', 1), timeout_minutes=-1).is_expired()
