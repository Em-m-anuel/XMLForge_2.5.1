"""Tests mode XML principal (Phase 6J-B) : CRUD/DDL/index/pagination/schéma,
permissions, versionning et TCP — exclusivement sur le moteur XML.
"""

import os
import socket

import pytest

from app import create_app
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService
from .conftest import register_and_login, auth


@pytest.fixture()
def xml_app(tmp_path):
    class Config(TestingConfig):
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False

    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    return create_app(Config)


@pytest.fixture()
def xml_client(xml_app):
    return xml_app.test_client()


def _setup_base(client, token, name="xmlmode_db"):
    database = client.post('/databases', json={"name": name}, headers=auth(token)).get_json()["data"]
    cats = client.post('/tables', json={"name": "categories", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": cats["id"], "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "name", "type": "VARCHAR", "table_id": cats["id"], "nullable": False, "unique": True}, headers=auth(token))
    books = client.post('/tables', json={"name": "books", "database_id": database["id"]}, headers=auth(token)).get_json()["data"]
    client.post('/columns', json={"name": "id", "type": "INT", "table_id": books["id"], "primary_key": True, "auto_increment": True}, headers=auth(token))
    client.post('/columns', json={"name": "title", "type": "VARCHAR", "table_id": books["id"], "nullable": False}, headers=auth(token))
    client.post('/columns', json={"name": "category_id", "type": "INT", "table_id": books["id"], "references": "categories.id"}, headers=auth(token))
    client.post('/columns', json={"name": "price", "type": "REAL", "table_id": books["id"], "nullable": True}, headers=auth(token))
    return database


def _q(client, token, database, sql):
    resp = client.post(f"/databases/{database['id']}/query", json={"sql": sql}, headers=auth(token))
    return resp.status_code, resp.get_json()


class TestBackendXml:
    def test_select_is_xml(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode", "xmlmode@example.com")
        database = _setup_base(xml_client, token)
        _q(xml_client, token, database, "INSERT INTO categories (name) VALUES ('SF'), ('Policier')")
        status, payload = _q(xml_client, token, database, "SELECT * FROM categories ORDER BY name")
        assert status == 200
        data = payload["data"]
        assert data["metrics"]["engine"] == "xml"
        assert data["result"]["rows"] == [{"id": 2, "name": "Policier"}, {"id": 1, "name": "SF"}]

    def test_xml_mode_writes_no_sqlite_file(self, xml_client, xml_app, tmp_path):
        user, token = register_and_login(xml_client, "XmlMode2", "xmlmode2@example.com")
        database = _setup_base(xml_client, token)
        _q(xml_client, token, database, "INSERT INTO books (title, price) VALUES ('Fondation', 9.5)")
        _q(xml_client, token, database, "CREATE TABLE extra (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL)")
        _q(xml_client, token, database, "CREATE INDEX idx_t ON books (title)")
        sqlite_files = [f for root, _, files in os.walk(str(tmp_path))
                        for f in files if f.endswith((".sqlite", ".sqlite3", ".db"))]
        assert sqlite_files == []

    def test_xml_mode_crud_roundtrip(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode3", "xmlmode3@example.com")
        database = _setup_base(xml_client, token)
        assert _q(xml_client, token, database, "INSERT INTO books (title, price) VALUES ('Dune', 11.0)")[0] == 200
        assert _q(xml_client, token, database, "UPDATE books SET price = 13.0 WHERE title = 'Dune'")[0] == 200
        _, payload = _q(xml_client, token, database, "SELECT title, price FROM books WHERE title = 'Dune'")
        assert payload["data"]["result"]["rows"] == [{"title": "Dune", "price": 13.0}]
        assert _q(xml_client, token, database, "DELETE FROM books WHERE title = 'Dune'")[0] == 200
        _, payload = _q(xml_client, token, database, "SELECT COUNT(*) FROM books")
        assert payload["data"]["result"]["count"] == 0

    def test_xml_mode_ddl_index_pagination(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode4", "xmlmode4@example.com")
        database = _setup_base(xml_client, token)
        for i in range(1, 8):
            _q(xml_client, token, database, f"INSERT INTO books (title, price) VALUES ('L{i}', {i}.0)")
        status, payload = _q(xml_client, token, database,
                             "SELECT title FROM books ORDER BY price DESC LIMIT 3 OFFSET 2")
        rows = payload["data"]["result"]["rows"]
        assert [r["title"] for r in rows] == ["L5", "L4", "L3"]
        pagination = payload["data"]["result"]["pagination"]
        assert pagination["total"] == 7 and pagination["total_pages"] == 3

        _q(xml_client, token, database, "ALTER TABLE books ADD COLUMN year INT DEFAULT 2024")
        _q(xml_client, token, database, "ALTER TABLE books MODIFY COLUMN title VARCHAR(50)")
        _q(xml_client, token, database, "CREATE INDEX idx_price ON books (price)")
        _q(xml_client, token, database, "DROP INDEX idx_price ON books")
        _q(xml_client, token, database, "ALTER TABLE books RENAME TO livres")
        status, payload = _q(xml_client, token, database, "SELECT COUNT(*) FROM livres")
        assert payload["data"]["result"]["count"] == 7
        _q(xml_client, token, database, "ALTER TABLE livres RENAME TO books")
        _q(xml_client, token, database, "DROP TABLE books")
        status, payload = _q(xml_client, token, database, "SELECT COUNT(*) FROM books")
        assert status != 200  # table supprimée

    def test_schema_introspection_from_xml(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode5", "xmlmode5@example.com")
        database = _setup_base(xml_client, token)
        _q(xml_client, token, database, "INSERT INTO books (title, price) VALUES ('X', 1.0)")
        resp = xml_client.get(f"/databases/{database['id']}/schema", headers=auth(token))
        assert resp.status_code == 200
        schema = resp.get_json()["data"]
        books = next(t for t in schema["tables"] if t["name"] == "books")
        assert books["row_count"] == 1
        cols = {c["name"]: c for c in books["columns"]}
        assert cols["category_id"]["references"] == "categories.id"
        assert books["foreign_keys"][0]["column"] == "category_id"

    def test_rows_facade_reads_xml(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode7", "xmlmode7@example.com")
        database = _setup_base(xml_client, token)
        _q(xml_client, token, database, "INSERT INTO books (title, price) VALUES ('A', 1.0), ('B', 2.0)")
        books = xml_client.get(f"/tables/{database['id']}", headers=auth(token)).get_json()["data"]
        table = next(t for t in books if t["name"] == "books")
        resp = xml_client.get(f"/tables/{table['id']}/rows", headers=auth(token))
        assert resp.status_code == 200
        rows = resp.get_json()["data"]["rows"]
        assert len(rows) == 2
        assert rows[0]["data"]["title"] in {"A", "B"}

    def test_permissions_not_bypassed(self, xml_client, xml_app):
        owner, token = register_and_login(xml_client, "Owner X", "owner-x@example.com")
        database = _setup_base(xml_client, token)
        _q(xml_client, token, database, "INSERT INTO books (title, price) VALUES ('X', 1.0)")
        viewer, viewer_token = register_and_login(xml_client, "Viewer X", "viewer-x@example.com")
        xml_client.post(f"/databases/{database['id']}/permissions", json={
            "email": "viewer-x@example.com",
            "can_read": True, "can_write": False, "can_ddl": False, "can_admin": False,
        }, headers=auth(token))
        status, payload = _q(xml_client, viewer_token, database, "SELECT * FROM books")
        assert status == 200
        status, payload = _q(xml_client, viewer_token, database, "INSERT INTO books (title) VALUES ('interdit')")
        assert status == 403
        resp = xml_client.get(f"/databases/{database['id']}/schema", headers=auth(viewer_token))
        assert resp.status_code == 200

    def test_expected_version_conflict(self, xml_client, xml_app):
        user, token = register_and_login(xml_client, "XmlMode8", "xmlmode8@example.com")
        database = _setup_base(xml_client, token)
        version = xml_client.get(f"/databases/{database['id']}", headers=auth(token)).get_json()["data"]["document_version"]
        status, _ = _q(xml_client, token, database, "INSERT INTO books (title) VALUES ('concurrent')")
        assert status == 200
        resp = xml_client.post(f"/databases/{database['id']}/query", json={
            "sql": "INSERT INTO books (title) VALUES ('stale')",
            "expected_version": version,
        }, headers=auth(token))
        assert resp.status_code == 409
        assert resp.get_json()["errors"]["code"] == "SYNC_CONFLICT"


class TestTcpXmlBackend:
    def test_tcp_engine_xml_crud(self, xml_app):
        app = xml_app
        client = app.test_client()
        user, token = register_and_login(client, "TCP X", "tcp-x@example.com")
        database = _setup_base(client, token, name="tcp_xml_db")
        _q(client, token, database, "INSERT INTO categories (name) VALUES ('SF')")
        tcp = client.post('/api/tcp/credentials', json={"tcp_password": "tcp-xml-secret"}, headers=auth(token)).get_json()["data"]

        from app.tcp.tcp_server import TCPServer
        from app.tcp.xmlforge_client import XMLForgeClient

        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]; sock.close()
        server = TCPServer('127.0.0.1', port, app)
        server.start()
        try:
            external = XMLForgeClient('127.0.0.1', port, timeout=5)
            assert external.connect(tcp["credential"]["tcp_username"], "tcp-xml-secret", str(database["id"]))
            rows = external.execute("SELECT * FROM categories ORDER BY name", engine="xml")
            assert rows["rows"] == [{"id": 1, "name": "SF"}]
            external.execute("INSERT INTO books (title, price) VALUES ('TCP', 3.0)", engine="xml")
            external.execute("UPDATE books SET price = 4.0 WHERE title = 'TCP'", engine="xml")
            back = external.select('books', where="title='TCP'")
            assert back[0]["price"] == 4.0
            external.execute("DELETE FROM books WHERE title = 'TCP'", engine="xml")
            external.execute("CREATE TABLE scratch (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL)", engine="xml")
            external.execute("DROP TABLE scratch", engine="xml")
            external.disconnect()
        finally:
            server.stop()
