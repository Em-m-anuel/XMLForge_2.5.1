"""Fixtures E2E : vrais serveurs HTTP/TCP et vrais fichiers XML (XML-only)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from werkzeug.serving import make_server

from app import create_app
from app.config import TestingConfig
from app.tcp.tcp_server import TCPServer
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService


@dataclass
class ApiResponse:
    status_code: int
    json: dict | None
    body: bytes
    headers: object


class ApiClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def request(self, method, path, *, payload=None, token=None, headers=None, timeout=10):
        request_headers = {"Accept": "application/json"}
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        request_headers.update(headers or {})
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(self.base_url + path, data=data, headers=request_headers, method=method.upper())
        try:
            response = urlopen(request, timeout=timeout)
            body = response.read()
            status = response.status
            response_headers = response.headers
        except HTTPError as exc:
            body = exc.read()
            status = exc.code
            response_headers = exc.headers
        parsed = json.loads(body.decode("utf-8")) if body and "json" in response_headers.get_content_type() else None
        return ApiResponse(status, parsed, body, response_headers)

    def register(self, name, email, password="secret123"):
        response = self.request("POST", "/api/register", payload={
            "full_name": name, "email": email, "password": password,
        })
        assert response.status_code == 201, response.json
        return response.json["data"]

    def login(self, email, password="secret123"):
        response = self.request("POST", "/api/login", payload={"email": email, "password": password})
        assert response.status_code == 200, response.json
        return response.json["data"]["access_token"], response.json["data"]["user"]


@dataclass
class E2EEnvironment:
    app: object
    api: ApiClient
    http_server: object
    tcp_server: TCPServer
    root: object
    xml_dir: object
    control_dir: object


@pytest.fixture()
def e2e_environment(tmp_path):
    """Une installation XMLForge XML-only isolée pour chaque test."""
    xml_dir = tmp_path / "xml"
    control_dir = tmp_path / "control"
    store.ensure_dir(str(control_dir), mode=0o700)
    XmlControlPlaneService(storage_folder=str(control_dir)).bootstrap()

    class RealE2EConfig(TestingConfig):
        XML_STORAGE_FOLDER = str(xml_dir)
        CONTROL_STORAGE_FOLDER = str(control_dir)
        TCP_ENABLED = False
        TESTING = False  # Les erreurs traversent le vrai cycle HTTP.

    application = create_app(RealE2EConfig)

    http_server = make_server("127.0.0.1", 0, application, threaded=True)
    assert http_server.multithread is True
    http_server.daemon_threads = True
    http_thread = threading.Thread(target=http_server.serve_forever, daemon=True, name="xmlforge-e2e-http")
    http_thread.start()
    api = ApiClient(f"http://127.0.0.1:{http_server.server_port}")

    tcp_server = TCPServer("127.0.0.1", 0, application)
    tcp_server.start()
    application.tcp_server = tcp_server

    environment = E2EEnvironment(
        app=application, api=api, http_server=http_server, tcp_server=tcp_server,
        root=tmp_path, xml_dir=xml_dir, control_dir=control_dir,
    )
    try:
        yield environment
    finally:
        tcp_server.stop()
        http_server.shutdown()
        http_server.server_close()
        http_thread.join(timeout=5)
