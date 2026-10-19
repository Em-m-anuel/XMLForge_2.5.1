"""Tests de préparation au packaging Windows (aucun EXE créé).

Vérifient : résolution des chemins runtime (source / gelé / surcharge), création
automatique des répertoires, persistance des secrets, chargement des XSD, service
du frontend buildé, initialisation non interactive, indépendance au CWD.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from lxml import etree

from app import create_app, paths
from app.config import TestingConfig
from app.xml_control import store
from app.xml_control.service import XmlControlPlaneService

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_app(tmp_path, *, frontend_dist=None):
    """Application de test avec Control Plane bootstrapé dans tmp_path."""

    class Config(TestingConfig):
        CONTROL_STORAGE_FOLDER = str(tmp_path / "control")
        XML_STORAGE_FOLDER = str(tmp_path / "xml")
        TCP_ENABLED = False
        FRONTEND_DIST_FOLDER = frontend_dist

    store.ensure_dir(str(tmp_path / "control"), mode=0o700)
    XmlControlPlaneService(storage_folder=str(tmp_path / "control")).bootstrap()
    return create_app(Config)


# --------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------

def test_source_defaults_keep_dev_layout():
    # Aucune surcharge : le layout de développement historique est conservé.
    root = paths.resource_root()
    assert paths.control_folder() == os.path.join(root, "data", "control")
    assert paths.xml_folder() == os.path.join(root, "data", "xml")
    assert paths.uploads_folder() == os.path.join(root, "uploads")
    assert paths.exports_folder() == os.path.join(root, "exports")


def test_installed_layout_under_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path))
    assert paths.control_folder() == os.path.join(str(tmp_path), "data", "control")
    assert paths.xml_folder() == os.path.join(str(tmp_path), "data", "xml")
    assert paths.uploads_folder() == os.path.join(str(tmp_path), "tmp", "uploads")
    assert paths.exports_folder() == os.path.join(str(tmp_path), "tmp", "exports")
    assert paths.logs_folder() == os.path.join(str(tmp_path), "logs")
    assert paths.config_folder() == os.path.join(str(tmp_path), "config")


def test_frozen_posix_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.control_folder() == os.path.join(str(tmp_path), "XMLForge", "data", "control")
    assert paths.control_folder().startswith(str(tmp_path))


def test_frozen_windows_uses_localappdata_subprocess():
    code = (
        "import os, sys\n"
        "sys.frozen = True\n"
        "sys._MEIPASS = '/tmp/xf-fake-bundle'\n"
        "os.environ['LOCALAPPDATA'] = '/tmp/xf-fake-localappdata'\n"
        f"sys.path.insert(0, {BACKEND_ROOT!r})\n"
        "from app import paths\n"
        "print(paths.resource_root())\n"
        "print(paths.control_folder())\n"
        "print(paths.uploads_folder())\n"
        "print(paths.config_folder())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert lines[0] == "/tmp/xf-fake-bundle"  # ressources = bundle (lecture seule)
    assert lines[1] == "/tmp/xf-fake-localappdata/XMLForge/data/control"
    assert lines[2] == "/tmp/xf-fake-localappdata/XMLForge/tmp/uploads"
    assert lines[3] == "/tmp/xf-fake-localappdata/XMLForge/config"
    # Aucune donnée runtime sous le bundle.
    assert "/tmp/xf-fake-bundle" not in lines[1]


def test_cwd_independent_subprocess(tmp_path):
    data_dir = tmp_path / "data"
    cwd_dir = tmp_path / "cwd"
    cwd_dir.mkdir()
    code = (
        "import os, sys\n"
        f"os.chdir({str(cwd_dir)!r})\n"
        f"os.environ['XMLFORGE_DATA_DIR'] = {str(data_dir)!r}\n"
        f"sys.path.insert(0, {BACKEND_ROOT!r})\n"
        "from app import paths\n"
        "print(paths.control_folder())\n"
        "print(os.getcwd())\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=str(cwd_dir), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert lines[0] == os.path.join(str(data_dir), "data", "control")
    assert str(cwd_dir) not in lines[0]  # aucune dépendance au CWD
    assert lines[1] == str(cwd_dir)


# --------------------------------------------------------------------------
# Répertoires + secrets
# --------------------------------------------------------------------------

def test_prepare_runtime_creates_dirs_and_persists_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path))
    try:
        from app.runtime import prepare_runtime, ensure_secrets
        report = prepare_runtime()
        for directory in report["directories"]:
            assert os.path.isdir(directory), directory

        secrets_path = report["secrets_file"]
        assert os.path.isfile(secrets_path)

        first = {}
        with open(secrets_path, "r", encoding="utf-8") as stream:
            for line in stream:
                if "=" in line:
                    key, _, value = line.partition("=")
                    first[key.strip()] = value.strip()
        assert "SECRET_KEY" in first and "JWT_SECRET_KEY" in first
        for value in first.values():
            assert len(value) > 40
            assert "xmlforge-dev" not in value  # jamais les défauts de dev

        # Idempotence : mêmes valeurs au second appel.
        ensure_secrets()
        second = {}
        with open(secrets_path, "r", encoding="utf-8") as stream:
            for line in stream:
                if "=" in line:
                    key, _, value = line.partition("=")
                    second[key.strip()] = value.strip()
        assert second == first

        # Permissions restreintes sur POSIX.
        if os.name == "posix":
            assert (os.stat(secrets_path).st_mode & 0o077) == 0
    finally:
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("JWT_SECRET_KEY", None)


def test_ensure_secrets_env_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "env-provided-secret-value")
    try:
        from app.runtime import ensure_secrets
        path = ensure_secrets()
        with open(path, "r", encoding="utf-8") as stream:
            content = stream.read()
        # La valeur d'env n'est pas persistée ; seul le manquant est généré.
        assert not any(line.startswith("SECRET_KEY=") for line in content.splitlines())
        assert any(line.startswith("JWT_SECRET_KEY=") for line in content.splitlines())
        assert os.environ["SECRET_KEY"] == "env-provided-secret-value"
    finally:
        os.environ.pop("JWT_SECRET_KEY", None)


def test_secrets_never_contain_dev_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path))
    try:
        from app.runtime import ensure_secrets
        path = ensure_secrets()
        with open(path, "r", encoding="utf-8") as stream:
            content = stream.read()
        assert "xmlforge-dev-secret-key" not in content
        assert "xmlforge-dev-jwt-secret-key" not in content
    finally:
        os.environ.pop("SECRET_KEY", None)
        os.environ.pop("JWT_SECRET_KEY", None)


# --------------------------------------------------------------------------
# XSD
# --------------------------------------------------------------------------

def test_xsd_are_loadable():
    from app.xml_control import records
    from app.xml_engine import document
    for name in ("security.xsd", "catalog.xsd", "history.xsd", "audit.xsd"):
        path = records.schema_path(name)
        assert os.path.isfile(path), path
        etree.XMLSchema(etree.parse(path))  # lève si XSD invalide
    schema = document._xsd_schema()
    assert schema is not None


# --------------------------------------------------------------------------
# Frontend buildé
# --------------------------------------------------------------------------

def test_frontend_dist_is_served(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><html><body>XMLFORGE-UI</body></html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('xmlforge')", encoding="utf-8")

    app = _make_app(tmp_path, frontend_dist=str(dist))
    client = app.test_client()

    resp = client.get("/")
    assert resp.status_code == 200 and b"XMLFORGE-UI" in resp.data

    resp = client.get("/assets/app.js")
    assert resp.status_code == 200 and b"console.log" in resp.data

    # Fallback SPA : route React profonde.
    resp = client.get("/workspace/deep/link")
    assert resp.status_code == 200 and b"XMLFORGE-UI" in resp.data

    # Les routes d'API inconnues restent des 404 JSON (pas l'index HTML).
    resp = client.get("/api/nonexistent")
    assert resp.status_code == 404
    assert b"XMLFORGE-UI" not in resp.data

    # /health et l'API réelle restent fonctionnels.
    assert client.get("/health").status_code == 200


def test_index_json_without_frontend(tmp_path, monkeypatch):
    # Force l'absence de frontend (même si un dist/ traîne sur le disque).
    monkeypatch.setenv("XMLFORGE_FRONTEND_DIST", "/chemin/inexistant")
    app = _make_app(tmp_path)
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert b"XML-only" in resp.data  # index JSON d'API conservé sans build


# --------------------------------------------------------------------------
# Initialisation non interactive
# --------------------------------------------------------------------------

def test_bootstrap_if_needed_is_idempotent(tmp_path, monkeypatch):
    from app.runtime import bootstrap_if_needed
    app = _make_app(tmp_path)
    with app.app_context():
        assert bootstrap_if_needed(app)["bootstrap"] == "skipped"

    # Application vierge : le bootstrap crée les documents (on neutralise le
    # contrôle fail-closed du démarrage, comme le ferait la commande bootstrap).
    fresh = tmp_path / "fresh"
    monkeypatch.setattr(sys, "argv", ["run.py", "xml-bootstrap"])

    class Config(TestingConfig):
        CONTROL_STORAGE_FOLDER = str(fresh / "control")
        XML_STORAGE_FOLDER = str(fresh / "xml")
        TCP_ENABLED = False

    store.ensure_dir(str(fresh / "control"), mode=0o700)
    app2 = create_app(Config)
    with app2.app_context():
        assert bootstrap_if_needed(app2)["bootstrap"] == "created"
        assert bootstrap_if_needed(app2)["bootstrap"] == "skipped"


def test_ensure_admin_is_idempotent(tmp_path):
    from app.runtime import ensure_admin
    app = _make_app(tmp_path)
    with app.app_context():
        ok, _ = ensure_admin(app, "pkgadmin@example.com", "Pkg Admin", "pw-pkg-123456")
        assert ok
        ok2, _ = ensure_admin(app, "pkgadmin@example.com", "Pkg Admin", "pw-pkg-123456")
        assert ok2
        from app.control_plane import get_backend
        user = get_backend().get_user_by_email("pkgadmin@example.com")
        assert user is not None and user.is_admin()


def test_has_active_admin(tmp_path):
    """Check de démarrage : un seul chargement de security.xml, O(users)."""
    app = _make_app(tmp_path)
    with app.app_context():
        from app.control_plane import get_backend
        backend = get_backend()
        dummy_hash = "$2b$12$" + "A" * 53

        # Bootstrap : rôles admin/user créés mais aucun utilisateur.
        assert backend.has_active_admin() is False

        role = backend.get_role_by_name("admin")
        assert role is not None and role.id is not None

        # Admin inactif : ne compte pas.
        backend.insert_user("Inactive Admin", "inactive@example.com", dummy_hash,
                            role_id=role.id, is_active=False)
        assert backend.has_active_admin() is False

        # Admin actif : True.
        backend.insert_user("Active Admin", "active@example.com", dummy_hash,
                            role_id=role.id, is_active=True)
        assert backend.has_active_admin() is True


def test_init_app_cli_command(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path / "runtime"))
    app = _make_app(tmp_path)
    runner = app.test_cli_runner()
    result = runner.invoke(args=[
        "init-app",
        "--email", "cli-admin@example.com",
        "--name", "CLI Admin",
        "--password", "pw-cli-123456",
    ])
    assert result.exit_code == 0, result.output
    assert "secrets_file" in result.output
    with app.app_context():
        from app.control_plane import get_backend
        user = get_backend().get_user_by_email("cli-admin@example.com")
        assert user is not None and user.is_admin()


# --------------------------------------------------------------------------
# Logs fichier
# --------------------------------------------------------------------------

def test_file_logging(monkeypatch, tmp_path):
    monkeypatch.setenv("XMLFORGE_DATA_DIR", str(tmp_path))
    from app.runtime import setup_file_logging
    app = _make_app(tmp_path)
    setup_file_logging(app)
    log_path = os.path.join(str(tmp_path), "logs", "xmlforge.log")
    assert os.path.isfile(log_path)
    # Idempotent : un second appel ne duplique pas les handlers.
    import logging
    before = len(logging.getLogger("xmlforge").handlers)
    setup_file_logging(app)
    assert len(logging.getLogger("xmlforge").handlers) == before
