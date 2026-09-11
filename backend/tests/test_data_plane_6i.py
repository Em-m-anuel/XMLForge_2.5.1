"""Tests Phase 6I — Data Plane XML sans SQLite.

Le fichier SQLite est **absent** (chemin inexistant), SQLAlchemy n'est pas
initialisé, la projection est désactivée : toutes les opérations Data Plane
passent par XML (XmlNativeEngine + fichiers XML).
"""

import os
import socket
import threading

import pytest

from app import create_app
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService


def seed_control(tmp_path, control_dir):
    """Bootstrap XML (installation vierge, aucun SQLite)."""
    store.ensure_dir(control_dir, mode=0o700)
    XmlControlPlaneService(storage_folder=control_dir).bootstrap()


def make_xml_app(tmp_path, control_dir):
    class XC(TestingConfig):
        CONTROL_STORAGE_FOLDER = control_dir
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False

    return create_app(XC)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def env(tmp_path):
    control_dir = str(tmp_path / "control")
    seed_control(tmp_path, control_dir)
    app = make_xml_app(tmp_path, control_dir)
    client = app.test_client()
    return app, client


def register(client, full_name, email, password="secret123"):
    r = client.post('/register', json={"full_name": full_name, "email": email, "password": password})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def login(client, email, password="secret123"):
    return client.post('/login', json={"email": email, "password": password})


# --------------------------------------------------------------------------
# Test ultime : application complète sans SQLite
# --------------------------------------------------------------------------

def test_full_application_without_sqlite(env):
    app, client = env
    # 1. utilisateur + login (+ promotion admin pour /history)
    register(client, "Owner", "owner@6i.dev")
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        admin_role = backend.get_role_by_name("admin")
        user = backend.get_user_by_email("owner@6i.dev")
        backend.update_user_fields(user.id, {"role_id": admin_role.id})
    token = login(client, "owner@6i.dev").get_json()["data"]["access_token"]
    H = auth(token)
    assert client.get('/me', headers=H).status_code == 200

    # 2. base PERSONAL + COMMON
    d = client.post('/databases', json={"name": "shop", "scope": "PERSONAL"}, headers=H).get_json()["data"]
    dbid = d["id"]
    dc = client.post('/databases', json={"name": "catalog", "scope": "COMMON", "common_permission": "VIEW"},
                     headers=H).get_json()["data"]
    assert [x["name"] for x in client.get('/databases', headers=H).get_json()["data"]] == ["catalog", "shop"]

    # 3. table + colonnes + index via REST
    t = client.post('/tables', json={"name": "products", "database_id": dbid}, headers=H).get_json()["data"]
    tid = t["id"]
    c = client.post('/columns', json={"name": "id", "type": "INT", "table_id": tid,
                                      "primary_key": True, "auto_increment": True}, headers=H)
    assert c.status_code == 201
    c = client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": tid,
                                      "nullable": False, "unique": True}, headers=H)
    assert c.status_code == 201
    r = client.post(f'/databases/{dbid}/query', json={"sql": "CREATE INDEX idx_name ON products (name)"}, headers=H)
    assert r.status_code == 200, r.get_json()

    # 4. INSERT / SELECT / UPDATE / DELETE via SQL (engine xml)
    for name in ("apple", "banana", "cherry"):
        r = client.post(f'/databases/{dbid}/query', json={"sql": f"INSERT INTO products (name) VALUES ('{name}')"},
                        headers=H)
        assert r.status_code == 200, r.get_json()
    r = client.post(f'/databases/{dbid}/query', json={"sql": "SELECT * FROM products ORDER BY id"}, headers=H)
    rows = r.get_json()["data"]["result"]["rows"]
    assert [x["name"] for x in rows] == ["apple", "banana", "cherry"]
    r = client.post(f'/databases/{dbid}/query', json={"sql": "UPDATE products SET name='avocado' WHERE name='apple'"},
                    headers=H)
    assert r.status_code == 200
    r = client.post(f'/databases/{dbid}/query', json={"sql": "DELETE FROM products WHERE name='cherry'"}, headers=H)
    assert r.status_code == 200

    # 5. contraintes : UNIQUE violé + FK inexistante -> refus
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO products (name) VALUES ('banana')"},
                    headers=H)
    assert r.status_code in (400, 409)

    # 6. lignes via REST
    r = client.get(f'/tables/{tid}/rows', headers=H)
    row_list = r.get_json()["data"]["rows"]
    assert len(row_list) == 2  # avocado + banana

    # 7. schéma (aucun SQLAlchemy)
    sch = client.get(f'/databases/{dbid}/schema', headers=H)
    tables = sch.get_json()["data"]["tables"]
    assert tables[0]["name"] == "products"
    assert tables[0]["columns"][0]["primary_key"] is True

    # 8. history / audit
    assert client.get('/history', headers=H).status_code == 200

    # 9. permissions : COMMON lisible par un autre utilisateur actif
    register(client, "Guest", "guest@6i.dev")
    gt = login(client, "guest@6i.dev").get_json()["data"]["access_token"]
    listed = {x["name"] for x in client.get('/databases', headers=auth(gt)).get_json()["data"]}
    assert "catalog" in listed
    assert "shop" not in listed

    # 10. intégrité XML
    svc = XmlControlPlaneService(storage_folder=app.config["CONTROL_STORAGE_FOLDER"])
    svc.validate_integrity()


def test_import_then_delete_after_restart(env, tmp_path):
    """Régression 6K : la suppression d'une base importée (avec lignes) devait
    fonctionner après redémarrage (bug : catalogue supprimé avant le Data Plane)."""
    app, client = env
    register(client, "Owner", "owner@impdel.dev")
    token = login(client, "owner@impdel.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "src"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": t["id"],
                                  "nullable": False}, headers=auth(token))
    client.post(f'/databases/{d["id"]}/query', json={"sql": "INSERT INTO items (name) VALUES ('x')"},
                headers=auth(token))
    xml = client.get(f'/export/xml/{d["id"]}', headers=auth(token)).get_json()["data"]["xml"]
    copid = client.post('/import/xml', json={"xml": xml, "database_name": "src_copy"},
                        headers=auth(token)).get_json()["data"]["id"]

    # Redémarrage (nouvelle instance, mêmes dossiers).
    app2 = make_xml_app(tmp_path, str(tmp_path / "control"))
    client2 = app2.test_client()
    token2 = login(client2, "owner@impdel.dev").get_json()["data"]["access_token"]
    assert client2.delete(f'/databases/{copid}', headers=auth(token2)).status_code == 200
    listed = [x["id"] for x in client2.get('/databases', headers=auth(token2)).get_json()["data"]]
    assert copid not in listed


def test_restart_persistence_without_sqlite(tmp_path):
    control_dir = str(tmp_path / "control")
    seed_control(tmp_path, control_dir)
    app = make_xml_app(tmp_path, control_dir)
    client = app.test_client()
    register(client, "Owner", "owner@restart.dev")
    token = login(client, "owner@restart.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "persist"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post(f'/databases/{d["id"]}/query', json={"sql": "INSERT INTO items (id) VALUES (7)"},
                headers=auth(token))

    # Redémarrage XML-only (nouvelle instance, même dossiers).
    app2 = make_xml_app(tmp_path, control_dir)
    client2 = app2.test_client()
    assert login(client2, "owner@restart.dev").status_code == 200
    token2 = login(client2, "owner@restart.dev").get_json()["data"]["access_token"]
    dbs = client2.get('/databases', headers=auth(token2)).get_json()["data"]
    assert [x["name"] for x in dbs] == ["persist"]
    r = client2.post(f'/databases/{d["id"]}/query', json={"sql": "SELECT * FROM items"}, headers=auth(token2))
    assert r.get_json()["data"]["result"]["rows"][0]["id"] == 7


def test_constraints_without_sqlite(env):
    app, client = env
    register(client, "Owner", "owner@fk.dev")
    token = login(client, "owner@fk.dev").get_json()["data"]["access_token"]
    H = auth(token)
    d = client.post('/databases', json={"name": "fkdb"}, headers=H).get_json()["data"]
    dbid = d["id"]
    parent = client.post('/tables', json={"name": "parent", "database_id": dbid}, headers=H).get_json()["data"]
    child = client.post('/tables', json={"name": "child", "database_id": dbid}, headers=H).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": parent["id"],
                                  "primary_key": True}, headers=H)
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": child["id"],
                                  "primary_key": True}, headers=H)
    client.post('/columns', json={"name": "parent_id", "type": "INT", "table_id": child["id"],
                                  "references": "parent.id"}, headers=H)

    # FK violée : enfant référençant un parent inexistant -> refus.
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO child (id, parent_id) VALUES (1, 99)"},
                    headers=H)
    assert r.status_code in (400, 409)
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO parent (id) VALUES (1)"}, headers=H)
    assert r.status_code == 200
    r = client.post(f'/databases/{dbid}/query', json={"sql": "INSERT INTO child (id, parent_id) VALUES (1, 1)"},
                    headers=H)
    assert r.status_code == 200


def test_concurrency_without_sqlite(env):
    app, client = env
    register(client, "Owner", "owner@conc.dev")
    token = login(client, "owner@conc.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "conc"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": t["id"],
                                  "nullable": False}, headers=auth(token))

    def worker(i):
        with app.app_context():
            r = client.post(f'/databases/{d["id"]}/query',
                            json={"sql": f"INSERT INTO items (name) VALUES ('n{i}')"},
                            headers=auth(token))
            assert r.status_code == 200, r.get_json()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    r = client.post(f'/databases/{d["id"]}/query', json={"sql": "SELECT COUNT(*) AS n FROM items"},
                    headers=auth(token))
    count = r.get_json()["data"]["result"]["count"]
    assert count == 8


def test_tcp_without_sqlite(tmp_path):
    control_dir = str(tmp_path / "control")
    seed_control(tmp_path, control_dir)
    app = make_xml_app(tmp_path, control_dir)
    client = app.test_client()
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


def test_schema_endpoint_no_sqlalchemy(env):
    app, client = env
    register(client, "Owner", "owner@sch.dev")
    token = login(client, "owner@sch.dev").get_json()["data"]["access_token"]
    d = client.post('/databases', json={"name": "sch"}, headers=auth(token)).get_json()["data"]
    t = client.post('/tables', json={"name": "items", "database_id": d["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": t["id"],
                                  "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "code", "type": "VARCHAR", "table_id": t["id"],
                                  "unique": True, "index": True}, headers=auth(token))
    sch = client.get(f'/databases/{d["id"]}/schema', headers=auth(token)).get_json()["data"]
    cols = sch["tables"][0]["columns"]
    assert {c["name"] for c in cols} == {"id", "code"}
    assert any(c["name"] == "id" and c["primary_key"] and c["auto_increment"] for c in cols)
    assert any(c["name"] == "code" and c["unique"] for c in cols)
