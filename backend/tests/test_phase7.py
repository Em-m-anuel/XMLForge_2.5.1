"""Tests Phase 7 — XMLForge serveur de base de données (TCP, sessions,
transactions, client Python, LEFT JOIN, erreurs métier, concurrence).
"""

import os
import socket
import sys
import threading

import pytest

from app import create_app
from app.config import TestingConfig
from app.query.sql_parser import parse_sql_statement
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService
from app.xml_engine.xml_native import XmlNativeEngine

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------
# Parser / moteur
# --------------------------------------------------------------------------

def test_parser_use_transactions_and_drop_database():
    assert parse_sql_statement("USE Bibliotheque") == {"operation": "use", "database": "Bibliotheque"}
    assert parse_sql_statement("BEGIN") == {"operation": "begin"}
    assert parse_sql_statement("START TRANSACTION") == {"operation": "begin"}
    assert parse_sql_statement("COMMIT") == {"operation": "commit"}
    assert parse_sql_statement("ROLLBACK") == {"operation": "rollback"}
    st = parse_sql_statement("DROP DATABASE foo")
    assert st == {"operation": "drop_database", "name": "foo"}


def test_parser_left_join():
    st = parse_sql_statement("SELECT a.id, b.name FROM a LEFT JOIN b ON a.id = b.a_id")
    assert st["joins"] == [{"type": "LEFT", "table": "b", "alias": None,
                            "on": {"op": "=", "column": {"column": "a.id"}, "value": {"column": "b.a_id"}}}]
    st = parse_sql_statement("SELECT * FROM a LEFT OUTER JOIN b ON a.id = b.a_id")
    assert st["joins"][0]["type"] == "LEFT"
    with pytest.raises(Exception):
        parse_sql_statement("SELECT * FROM a RIGHT JOIN b ON a.id = b.a_id")


def test_engine_left_join_nulls():
    doc = {
        "name": "x", "description": "", "comment": "", "status": "ACTIVE",
        "scope": "PERSONAL", "version": 1, "generator": "XMLForge", "author": "",
        "created_at": "2026-09-09T00:00:00",
        "tables": [
            {"name": "authors", "description": "", "comment": "", "protected": False,
             "file_identifier": None, "status": "ACTIVE", "constraints": [], "indexes": [],
             "columns": [
                 {"name": "id", "type": "INT", "length": "-", "nullable": False,
                  "primary_key": True, "foreign_key": False, "unique": False,
                  "auto_increment": True, "index": False, "status": "ACTIVE"},
                 {"name": "name", "type": "VARCHAR", "length": "100", "nullable": False,
                  "primary_key": False, "foreign_key": False, "unique": False,
                  "auto_increment": False, "index": False, "status": "ACTIVE"},
             ],
             "rows": [{"uuid": "r1", "data": {"id": 1, "name": "Hugo"}},
                      {"uuid": "r2", "data": {"id": 2, "name": "Emma"}}]},
            {"name": "books", "description": "", "comment": "", "protected": False,
             "file_identifier": None, "status": "ACTIVE", "constraints": [], "indexes": [],
             "columns": [
                 {"name": "id", "type": "INT", "length": "-", "nullable": False,
                  "primary_key": True, "foreign_key": False, "unique": False,
                  "auto_increment": True, "index": False, "status": "ACTIVE"},
                 {"name": "author_id", "type": "INT", "length": "-", "nullable": True,
                  "primary_key": False, "foreign_key": True, "unique": False,
                  "auto_increment": False, "index": False, "status": "ACTIVE",
                  "references": "authors.id"},
                 {"name": "title", "type": "VARCHAR", "length": "200", "nullable": False,
                  "primary_key": False, "foreign_key": False, "unique": False,
                  "auto_increment": False, "index": False, "status": "ACTIVE"},
             ],
             "rows": [{"uuid": "b1", "data": {"id": 1, "author_id": 1, "title": "Les Misérables"}},
                      {"uuid": "b2", "data": {"id": 2, "author_id": None, "title": "Sans auteur"}}]},
        ],
    }
    engine = XmlNativeEngine(document=doc)
    result = engine.select_statement(parse_sql_statement(
        "SELECT a.name AS auteur, b.title FROM authors a LEFT JOIN books b ON a.id = b.author_id ORDER BY a.id"))
    rows = result["rows"]
    # authors (2) LEFT JOIN books : Hugo correspond au livre 1, Emma sans livre
    # est conservée avec NULL ; le livre sans auteur (côté droit) est ignoré.
    assert len(rows) == 2
    assert rows[0]["auteur"] == "Hugo" and rows[0]["title"] == "Les Misérables"
    assert rows[1]["auteur"] == "Emma" and rows[1]["title"] is None


# --------------------------------------------------------------------------
# Serveur TCP : sessions, transactions, erreurs, client Python
# --------------------------------------------------------------------------

def free_port():
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    return port


@pytest.fixture()
def env(tmp_path):
    class Cfg(TestingConfig):
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False

    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    app = create_app(Cfg)
    client = app.test_client()

    # Utilisateur + credentials TCP + base + table + colonnes (via REST).
    client.post('/register', json={"full_name": "Owner", "email": "owner@tcp.dev", "password": "secret123"})
    token = client.post('/login', json={"email": "owner@tcp.dev", "password": "secret123"}).get_json()["data"]["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    db = client.post('/databases', json={"name": "bank", "scope": "PERSONAL"}, headers=H).get_json()["data"]
    t = client.post('/tables', json={"name": "accounts", "database_id": db["id"]}, headers=H).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=H)
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": t["id"],
                                  "nullable": False}, headers=H)
    client.post('/columns', json={"name": "balance", "type": "INT", "table_id": t["id"],
                                  "default": "0"}, headers=H)
    client.post(f'/databases/{db["id"]}/query', json={"sql": "INSERT INTO accounts (name, balance) VALUES ('A', 100), ('B', 100)"}, headers=H)
    cred = client.post('/api/tcp/credentials', json={"tcp_username": "owner-tcp", "tcp_password": "tcp-secret"}, headers=H).get_json()["data"]
    yield app, db["id"], "owner-tcp", "tcp-secret"


def _start_server(app):
    from app.tcp.tcp_server import TCPServer
    port = free_port()
    server = TCPServer("127.0.0.1", port, app)
    server.start()
    return server, port


def test_tcp_session_full_flow_and_transactions(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    try:
        from xmlforge import connect
        from xmlforge.errors import XmlforgeError

        conn = connect(host="127.0.0.1", port=port, user=username, password=password)
        assert conn.user_id is not None
        conn.use("bank")
        assert conn.database_name == "bank"

        # SELECT initial : 2 comptes.
        r = conn.query("SELECT * FROM accounts ORDER BY id")
        assert r.row_count == 2 and r.columns == ["id", "name", "balance"]

        # INSERT hors transaction (persistant).
        conn.execute("INSERT INTO accounts (name, balance) VALUES ('C', 0)")
        assert conn.query("SELECT COUNT(*) FROM accounts").rows[0]["count"] == 3

        # Transaction avec ROLLBACK : les modifications disparaissent.
        conn.execute("BEGIN")
        conn.execute("INSERT INTO accounts (name, balance) VALUES ('D', 999)")
        conn.execute("UPDATE accounts SET balance = 0 WHERE name = 'A'")
        assert conn.query("SELECT COUNT(*) FROM accounts").rows[0]["count"] == 4
        conn.execute("ROLLBACK")
        r = conn.query("SELECT * FROM accounts ORDER BY id")
        assert r.row_count == 3  # C conservé, D supprimé, A restauré
        names = {row["name"] for row in r.rows}
        assert names == {"A", "B", "C"}

        # Transaction avec COMMIT : les modifications persistent.
        conn.execute("BEGIN")
        conn.execute("UPDATE accounts SET balance = 777 WHERE name = 'B'")
        conn.execute("COMMIT")
        r = conn.query("SELECT balance FROM accounts WHERE name = 'B'")
        assert r.rows[0]["balance"] == 777

        # Erreurs de transaction.
        with pytest.raises(XmlforgeError) as exc:
            conn.execute("COMMIT")  # pas de transaction active
        assert exc.value.code == "TRANSACTION_NOT_ACTIVE"
        conn.execute("BEGIN")
        with pytest.raises(XmlforgeError) as exc:
            conn.execute("BEGIN")  # déjà active
        assert exc.value.code == "TRANSACTION_ACTIVE"
        conn.execute("ROLLBACK")

        conn.close()
    finally:
        server.stop()


def test_tcp_errors_have_business_codes(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    try:
        from xmlforge import connect
        from xmlforge.errors import XmlforgeError

        # Mauvais mot de passe -> AUTH_FAILED (ConnectionError du client).
        with pytest.raises(XmlforgeError) as exc:
            connect(host="127.0.0.1", port=port, user=username, password="wrong")
        assert exc.value.code == "AUTH_FAILED"

        conn = connect(host="127.0.0.1", port=port, user=username, password=password)
        # Base inconnue via USE -> erreur métier.
        with pytest.raises(XmlforgeError) as exc:
            conn.use("inexistante")
        assert "introuvable" in exc.value.message.lower() or "non autorisée" in exc.value.message.lower()

        conn.use("bank")
        # Table inconnue.
        with pytest.raises(XmlforgeError) as exc:
            conn.execute("SELECT * FROM ghost")
        assert exc.value.code in ("TABLE_NOT_FOUND", "NOT_FOUND", "INTERNAL_ERROR")

        # Requête invalide.
        with pytest.raises(XmlforgeError) as exc:
            conn.execute("SELECT * FROM")
        assert exc.value.code in ("SYNTAX_ERROR", "INVALID_QUERY", "VALIDATION_FAILED", "INTERNAL_ERROR")

        # Contrainte NOT NULL violée.
        with pytest.raises(XmlforgeError) as exc:
            conn.execute("INSERT INTO accounts (id) VALUES (50)")
        assert exc.value.code in ("CONSTRAINT_VIOLATION", "DATA_INVALID", "VALIDATION_FAILED", "INTERNAL_ERROR")
        conn.close()
    finally:
        server.stop()


def test_tcp_sessions_are_isolated(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    try:
        from xmlforge import connect
        c1 = connect(host="127.0.0.1", port=port, user=username, password=password)
        c2 = connect(host="127.0.0.1", port=port, user=username, password=password)
        c1.use("bank"); c2.use("bank")
        # c1 ouvre une transaction ; c2 n'en a pas.
        c1.execute("BEGIN")
        c1.execute("UPDATE accounts SET balance = 1 WHERE name = 'A'")
        # c2 voit le changement (write immediat, pas d'isolation multi-version)…
        assert c2.query("SELECT balance FROM accounts WHERE name = 'A'").rows[0]["balance"] == 1
        # …mais c2 n'a PAS de transaction active (isolation de session).
        from xmlforge.errors import XmlforgeError
        with pytest.raises(XmlforgeError) as exc:
            c2.execute("COMMIT")
        assert exc.value.code == "TRANSACTION_NOT_ACTIVE"
        c1.execute("ROLLBACK")
        assert c2.query("SELECT balance FROM accounts WHERE name = 'A'").rows[0]["balance"] == 100
        c1.close(); c2.close()
        # La fermeture est asynchrone côté serveur : attente bornée.
        import time as _time
        deadline = _time.monotonic() + 2
        while _time.monotonic() < deadline:
            if len(server.get_sessions_info()) == 0:
                break
            _time.sleep(0.02)
        assert len(server.get_sessions_info()) == 0
    finally:
        server.stop()


def test_tcp_drop_database(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    try:
        from xmlforge import connect
        conn = connect(host="127.0.0.1", port=port, user=username, password=password)
        conn.use("bank")
        # Créer puis supprimer une base via SQL.
        r = conn.execute("CREATE DATABASE tempdb")
        assert r.metadata.get("created") == "tempdb"
        r = conn.execute("DROP DATABASE tempdb")
        assert r.metadata.get("dropped") == "tempdb"
        conn.close()
    finally:
        server.stop()


def test_tcp_concurrent_clients(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    errors = []

    def worker(i):
        try:
            from xmlforge import connect
            conn = connect(host="127.0.0.1", port=port, user=username, password=password)
            conn.use("bank")
            for j in range(5):
                conn.execute(f"INSERT INTO accounts (name, balance) VALUES ('w{i}-{j}', {i})")
            conn.close()
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []

    from xmlforge import connect
    conn = connect(host="127.0.0.1", port=port, user=username, password=password)
    conn.use("bank")
    total = conn.query("SELECT COUNT(*) FROM accounts").rows[0]["count"]
    assert total == 2 + 8 * 5  # 2 initiaux + 40 concurrents, aucune perte
    conn.close()
    server.stop()


def test_client_context_manager_and_result_fields(env):
    app, dbid, username, password = env
    server, port = _start_server(app)
    try:
        from xmlforge import connect
        with connect(host="127.0.0.1", port=port, user=username, password=password) as db:
            db.use("bank")
            r = db.query("SELECT * FROM accounts ORDER BY id LIMIT 1")
            assert r.columns == ["id", "name", "balance"]
            assert r.row_count == 2  # total sans LIMIT
            assert len(r.rows) == 1
            ins = db.execute("INSERT INTO accounts (name, balance) VALUES ('Z', 5)")
            assert ins.affected_rows == 1
            assert ins.last_insert_id is not None
            upd = db.execute("UPDATE accounts SET balance = 6 WHERE name = 'Z'")
            assert upd.affected_rows == 1
            dele = db.execute("DELETE FROM accounts WHERE name = 'Z'")
            assert dele.affected_rows == 1
        # Contexte fermé proprement.
        assert db.session_token is None
    finally:
        server.stop()
