"""Test ultime Phase 6J — XMLForge sans SQLite ni SQLAlchemy.

Environnement vierge : aucun fichier SQLite, aucune projection, SQLAlchemy non
initialisé. Le Control Plane XML est amorcé par ``XmlControlPlaneService.bootstrap()``
(pas via un export SQLite). Toute la chaîne REST + TCP + redémarrage est exercée.
"""

import os
import socket
import subprocess
import sys

import pytest

from app import create_app
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_final_app(tmp_path):
    class XC(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'does-not-exist' / 'nope.db'}"
        CONTROL_BACKEND = "xml"
        DATA_BACKEND = "xml"
        QUERY_BACKEND = "xml"
        SYNC_SQLITE_PROJECTION = False
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False

    return create_app(XC)


@pytest.fixture()
def env(tmp_path):
    # Installation vierge : bootstrap XML (aucun SQLite impliqué).
    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    app = make_final_app(tmp_path)
    client = app.test_client()
    return app, client


def register(client, full_name, email, password="secret123"):
    r = client.post('/register', json={"full_name": full_name, "email": email, "password": password})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def login(client, email, password="secret123"):
    return client.post('/login', json={"email": email, "password": password})


def test_full_xmlforge_without_sqlite(env, tmp_path):
    app, client = env
    register(client, "Owner", "owner@final.dev")
    token = login(client, "owner@final.dev").get_json()["data"]["access_token"]
    H = auth(token)
    assert client.get('/me', headers=H).status_code == 200

    # Bases PERSONAL + COMMON
    d = client.post('/databases', json={"name": "shop", "scope": "PERSONAL"}, headers=H).get_json()["data"]
    dbid = d["id"]
    dc = client.post('/databases', json={"name": "common", "scope": "COMMON", "common_permission": "VIEW"},
                     headers=H).get_json()["data"]

    # Table + colonnes (PK/AUTO_INCREMENT, UNIQUE NOT NULL, DEFAULT, FK)
    parent = client.post('/tables', json={"name": "categories", "database_id": dbid}, headers=H).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": parent["id"],
                                  "primary_key": True, "auto_increment": True}, headers=H)
    client.post('/columns', json={"name": "label", "type": "VARCHAR", "table_id": parent["id"],
                                  "nullable": False, "unique": True}, headers=H)

    child = client.post('/tables', json={"name": "products", "database_id": dbid}, headers=H).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": child["id"],
                                  "primary_key": True, "auto_increment": True}, headers=H)
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": child["id"],
                                  "nullable": False, "unique": True}, headers=H)
    client.post('/columns', json={"name": "price", "type": "REAL", "table_id": child["id"],
                                  "default": "0.0"}, headers=H)
    client.post('/columns', json={"name": "category_id", "type": "INT", "table_id": child["id"],
                                  "references": "categories.id"}, headers=H)
    client.post('/columns', json={"name": "note", "type": "VARCHAR", "table_id": child["id"],
                                  "nullable": True}, headers=H)

    # Index
    r = client.post(f'/databases/{dbid}/query', json={"sql": "CREATE INDEX idx_price ON products (price)"}, headers=H)
    assert r.status_code == 200, r.get_json()

    # Contraintes : FK violée, UNIQUE violée, NOT NULL violée
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO products (name, category_id) VALUES ('x', 99)"}, headers=H)
    assert r.status_code in (400, 409), r.get_json()
    client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO categories (label) VALUES ('cat1')"}, headers=H)
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO products (name, category_id) VALUES ('p1', 1)"}, headers=H)
    assert r.status_code == 200, r.get_json()
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO products (name, category_id) VALUES ('p1', 1)"}, headers=H)
    assert r.status_code in (400, 409)  # UNIQUE name violé
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO products (category_id) VALUES (1)"}, headers=H)
    assert r.status_code in (400, 409)  # NOT NULL name violé

    # SELECT / UPDATE / DELETE
    r = client.post(f'/databases/{dbid}/query', json={"sql": "SELECT * FROM products"}, headers=H)
    assert r.get_json()["data"]["result"]["rows"][0]["name"] == "p1"
    client.post(f'/databases/{dbid}/query', json={"sql": "UPDATE products SET price=9.99 WHERE name='p1'"}, headers=H)
    r = client.post(f'/databases/{dbid}/query', json={"sql": "SELECT price FROM products WHERE name='p1'"}, headers=H)
    assert r.get_json()["data"]["result"]["rows"][0]["price"] == 9.99
    client.post(f'/databases/{dbid}/query', json={"sql": "DELETE FROM products WHERE name='p1'"}, headers=H)
    r = client.post(f'/databases/{dbid}/query', json={"sql": "SELECT COUNT(*) AS n FROM products"}, headers=H)
    assert r.get_json()["data"]["result"]["count"] == 0

    # Schéma
    sch = client.get(f'/databases/{dbid}/schema', headers=H).get_json()["data"]
    assert {t["name"] for t in sch["tables"]} == {"categories", "products"}

    # Permissions : COMMON lisible par un actif, PERSONAL non.
    register(client, "Guest", "guest@final.dev")
    gt = login(client, "guest@final.dev").get_json()["data"]["access_token"]
    listed = {x["name"] for x in client.get('/databases', headers=auth(gt)).get_json()["data"]}
    assert "common" in listed and "shop" not in listed

    # History / Audit (admin)
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        admin_role = backend.get_role_by_name("admin")
        owner = backend.get_user_by_email("owner@final.dev")
        backend.update_user_fields(owner.id, {"role_id": admin_role.id})
    assert client.get('/history', headers=H).status_code == 200
    assert client.get('/audit-logs', headers=H).status_code == 200

    # Intégrité
    XmlControlPlaneService(storage_folder=app.config["CONTROL_STORAGE_FOLDER"]).validate_integrity()

    # Aucun fichier SQLite créé.
    sqlite_files = []
    for root, _dirs, files in os.walk(str(tmp_path)):
        for f in files:
            if f.endswith((".sqlite", ".sqlite3", ".db")):
                sqlite_files.append(os.path.join(root, f))
    assert sqlite_files == [], f"fichiers SQLite créés: {sqlite_files}"


def test_tcp_without_sqlite(env, tmp_path):
    app, client = env
    register(client, "Owner", "owner@tcp.dev")
    token = login(client, "owner@tcp.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "tcpdb"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": t["id"],
                                  "nullable": False}, headers=auth(token))
    cred = client.post('/api/tcp/credentials', json={"tcp_username": "owner-tcp", "tcp_password": "tcp-pass"},
                       headers=auth(token)).get_json()["data"]

    from app.tcp.tcp_server import TCPServer
    from app.tcp.xmlforge_client import XMLForgeClient
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
    server = TCPServer('127.0.0.1', port, app); server.start()
    try:
        c = XMLForgeClient('127.0.0.1', port, timeout=5)
        assert c.connect("owner-tcp", "tcp-pass", str(d["id"]))
        assert c.insert('items', {"name": "x"}) == 1
        assert c.select('items')[0]["name"] == "x"
        assert c.update('items', {"name": "y"}, "id=1") == 1
        assert c.delete('items', "id=1") == 1
        c.disconnect()
    finally:
        server.stop()


def test_restart_without_sqlite(env, tmp_path):
    app, client = env
    register(client, "Owner", "owner@restart.dev")
    token = login(client, "owner@restart.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "persist"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post(f'/databases/{d["id"]}/query', json={"sql": "INSERT INTO items (id) VALUES (42)"},
                headers=auth(token))

    app2 = make_final_app(tmp_path)  # redémarrage, mêmes dossiers XML
    client2 = app2.test_client()
    assert login(client2, "owner@restart.dev").status_code == 200
    token2 = login(client2, "owner@restart.dev").get_json()["data"]["access_token"]
    r = client2.post(f'/databases/{d["id"]}/query', json={"sql": "SELECT * FROM items"}, headers=auth(token2))
    assert r.get_json()["data"]["result"]["rows"][0]["id"] == 42


def test_xml_modules_import_without_sqlalchemy():
    code = (
        "import sys; "
        "import app.control_plane.xml_backend; "
        "import app.xml_control.service; "
        "import app.data_plane.xml_backend; "
        "bad = [k for k in sys.modules if 'sqlalchemy' in k.lower() "
        "or k in ('app.extensions', 'app.models')]; "
        "assert not bad, bad; print('CLEAN')"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND_ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "CLEAN" in r.stdout


def test_internal_id_stability_no_reuse(env):
    app, client = env
    register(client, "Owner", "owner@ids.dev")
    token = login(client, "owner@ids.dev").get_json()["data"]["access_token"]
    H = auth(token)
    d = client.post('/databases', json={"name": "ids"}, headers=H).get_json()["data"]
    dbid = d["id"]

    t1 = client.post('/tables', json={"name": "t", "database_id": dbid}, headers=H).get_json()["data"]
    id1 = t1["id"]
    client.delete(f'/tables/{id1}', headers=H)
    t2 = client.post('/tables', json={"name": "t2", "database_id": dbid}, headers=H).get_json()["data"]
    assert t2["id"] > id1  # aucun ID réutilisé

    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t2["id"],
                                  "primary_key": True, "auto_increment": True}, headers=H)
    client.post('/columns', json={"name": "v", "type": "INT", "table_id": t2["id"]}, headers=H)
    client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO t2 (v) VALUES (1)"}, headers=H)
    client.post(f'/databases/{dbid}/query', json={"sql": "DELETE FROM t2 WHERE v=1"}, headers=H)
    client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO t2 (v) VALUES (2)"}, headers=H)
    r = client.post(f'/databases/{dbid}/query', json={"sql": "SELECT * FROM t2"}, headers=H)
    row = r.get_json()["data"]["result"]["rows"][0]
    assert row["id"] == 2  # AUTO_INCREMENT jamais réutilisé après DELETE


def test_security_no_file_exposure_and_no_password_leak(env):
    """6K-Q : les fichiers XML ne sont pas servis en HTTP, aucun secret exposé."""
    app, client = env
    register(client, "Owner", "owner@sec.dev")
    token = login(client, "owner@sec.dev").get_json()["data"]["access_token"]
    H = auth(token)

    # Les fichiers du Control Plane ne sont pas accessibles via HTTP.
    for path in ("/data/control/security.xml", "/control/security.xml",
                 "/data/xml/1.xml", "/../etc/passwd", "/%2e%2e/etc/passwd"):
        r = client.get(path)
        assert r.status_code == 404, f"{path} -> {r.status_code}"

    # Aucun password_hash / secret n'est renvoyé par les endpoints.
    me = client.get('/me', headers=H).get_json()["data"]
    assert "password_hash" not in me
    assert "password" not in me
    # /users (admin requis) ne renvoie pas de hash non plus.
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        backend.update_user_fields(me["id"], {"role_id": backend.get_role_by_name("admin").id})
    users = client.get('/users', headers=H).get_json()["data"]
    for u in users:
        assert "password_hash" not in u and "password" not in u


def test_rest_errors_are_structured_no_traceback(env):
    """6K-T : les erreurs REST sont structurées JSON, sans traceback Python."""
    app, client = env
    register(client, "Owner", "owner@err.dev")
    token = login(client, "owner@err.dev").get_json()["data"]["access_token"]
    H = auth(token)
    # Requête SQL invalide -> erreur structurée (pas de traceback).
    d = client.post('/databases', json={"name": "err"}, headers=H).get_json()["data"]
    r = client.post(f'/databases/{d["id"]}/query', json={"sql": "SELECT * FROM"}, headers=H)
    assert r.status_code in (400, 422, 500)
    body = r.get_json()
    assert "Traceback" not in str(body) and "File \"" not in str(body)
    # 401 non authentifié structuré.
    assert client.get('/databases').get_json()["success"] is False
    # 403 permission refusée structurée.
    register(client, "Guest", "guest@err.dev")
    gt = login(client, "guest@err.dev").get_json()["data"]["access_token"]
    r = client.post('/tables', json={"name": "x", "database_id": d["id"]}, headers=auth(gt))
    assert r.status_code == 403 and r.get_json()["success"] is False
