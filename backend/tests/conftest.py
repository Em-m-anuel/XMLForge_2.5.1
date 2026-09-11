"""Fixtures pytest — architecture XML-only (Phase 6J-B).

Chaque test dispose d'un Control Plane XML vierge (bootstrap) dans un répertoire
temporaire : aucune base SQLite n'est créée ni requise.
"""

import pytest

from app import create_app
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService


@pytest.fixture()
def app(tmp_path):
    class Config(TestingConfig):
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False

    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    application = create_app(Config)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client, name, email, password="secret123"):
    response = client.post('/register', json={"full_name": name, "email": email, "password": password})
    assert response.status_code == 201, response.get_json()
    response = client.post('/login', json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    return data["user"], data["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}
