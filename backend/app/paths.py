"""Résolution des chemins XMLForge — séparation ressources applicatives / données.

Objectif (préparation au packaging Windows) : l'application peut être installée
dans un dossier **non inscriptible** (ex. ``C:\\Program Files\\XMLForge``). Les
données runtime doivent alors vivre dans un emplacement utilisateur inscriptible.

Deux catégories de chemins :

- **Ressources applicatives** (code, XSD, frontend buildé) : répertoire du bundle
  en mode gelé, répertoire ``backend/`` en mode source. Jamais écrites.
- **Données runtime** (Control Plane, bases XML, uploads/exports temporaires,
  logs, configuration) :
    * mode gelé  → ``%LOCALAPPDATA%\\XMLForge`` (Windows) ou
      ``$XDG_DATA_HOME/XMLForge`` (sinon) ;
    * mode source → conservées sous ``backend/`` (comportement dev historique).

Surcharges (variables d'environnement, lues **à l'appel**, pas à l'import) :

- ``XMLFORGE_DATA_DIR`` : force la racine de données (layout « installé »).
- ``XMLFORGE_CONFIG_FOLDER`` / ``XMLFORGE_LOG_FOLDER`` : config / logs.
- ``XMLFORGE_FRONTEND_DIST`` : dossier du frontend buildé à servir.
- ``CONTROL_STORAGE_FOLDER`` / ``XML_STORAGE_FOLDER`` / ``UPLOAD_FOLDER`` /
  ``EXPORT_FOLDER`` : emplacements précis (lus par ``app/config.py``, prioritaires).

Aucune donnée persistante ne dépend de ``_MEIPASS`` (zone d'extraction temporaire
du bundler) ni du répertoire courant (CWD).
"""
from __future__ import annotations

import os
import sys

APP_NAME = "XMLForge"


def is_frozen() -> bool:
    """Vrai si l'application tourne depuis un bundle/exécutable (PyInstaller, Nuitka…)."""
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))


def resource_root() -> str:
    """Racine des ressources applicatives (lecture seule)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:  # PyInstaller (onefile : ressources extraites dans _MEIPASS)
        return meipass
    if getattr(sys, "frozen", False):  # Nuitka / cx_Freeze
        return os.path.dirname(os.path.abspath(sys.executable))
    # Mode source : backend/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_root() -> str:
    """Racine des données utilisateur (toujours inscriptible par l'utilisateur).

    ``LOCALAPPDATA`` est prioritaire (défini sur Windows) : cela permet aussi de
    reproduire le layout Windows sur d'autres OS (tests). Sinon, XDG sur POSIX.
    """
    local = os.getenv("LOCALAPPDATA")
    if local:
        return os.path.join(local, APP_NAME)
    if os.name == "nt":
        return os.path.join(os.path.expanduser("~"), APP_NAME)
    base = os.getenv("XDG_DATA_HOME") or os.path.expanduser(
        os.path.join("~", ".local", "share")
    )
    return os.path.join(base, APP_NAME)


def _installed_base():
    """Base du layout « installé » si applicable, sinon ``None`` (mode source dev)."""
    env = os.getenv("XMLFORGE_DATA_DIR")
    if env:
        return env
    if is_frozen():
        return user_data_root()
    return None


def _data_path(installed_subpath, dev_subpath):
    base = _installed_base()
    if base is not None:
        return os.path.join(base, installed_subpath)
    return os.path.join(resource_root(), dev_subpath)


def control_folder() -> str:
    """Dossier du Control Plane XML (security/catalog/history/audit)."""
    return _data_path(os.path.join("data", "control"), os.path.join("data", "control"))


def xml_folder() -> str:
    """Dossier du Data Plane XML (bases utilisateurs)."""
    return _data_path(os.path.join("data", "xml"), os.path.join("data", "xml"))


def uploads_folder() -> str:
    """Dossier temporaire des imports."""
    return _data_path(os.path.join("tmp", "uploads"), "uploads")


def exports_folder() -> str:
    """Dossier temporaire des exports."""
    return _data_path(os.path.join("tmp", "exports"), "exports")


def logs_folder() -> str:
    env = os.getenv("XMLFORGE_LOG_FOLDER")
    if env:
        return env
    return _data_path("logs", "logs")


def config_folder() -> str:
    env = os.getenv("XMLFORGE_CONFIG_FOLDER")
    if env:
        return env
    return _data_path("config", "config")


def secrets_file() -> str:
    """Fichier des secrets persistants (``SECRET_KEY`` / ``JWT_SECRET_KEY``)."""
    return os.path.join(config_folder(), "secrets.env")


def static_dir() -> str:
    """Dossier des ressources statiques (XSD) — source ou gelé."""
    package_dir = os.path.dirname(os.path.abspath(__file__))  # app/
    for candidate in (
        os.path.join(package_dir, "static"),
        os.path.join(resource_root(), "static"),
        os.path.join(resource_root(), "app", "static"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(package_dir, "static")


def frontend_dist_folder():
    """Dossier du frontend buildé à servir, ou ``None`` s'il n'existe pas.

    - ``XMLFORGE_FRONTEND_DIST`` explicite ;
    - ``<resources>/frontend`` (layout attendu dans le bundle) ;
    - ``<resources>/../xmlforge-react/dist`` (commodité développement).
    """
    env = os.getenv("XMLFORGE_FRONTEND_DIST")
    if env:
        return env if os.path.isdir(env) else None
    for candidate in (
        os.path.join(resource_root(), "frontend"),
        os.path.join(resource_root(), "..", "xmlforge-react", "dist"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return None
