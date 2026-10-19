"""Initialisation runtime pour application installée (préparation packaging Windows).

Ces fonctions sont destinées au futur launcher (EXE) : elles préparent les
répertoires de données, garantissent des secrets **persistants**, effectuent le
bootstrap XML et la création d'administrateur de façon **non interactive** et
**idempotente**. Aucun identifiant n'est codé en dur.

Rien ici n'est appelé automatiquement en mode développement (seule exception :
``ensure_secrets`` en mode gelé, déclenché par ``app/config.py``).
"""
from __future__ import annotations

import logging
import os
import secrets as _secrets
import tempfile

from . import paths

_SECRET_KEYS = ("SECRET_KEY", "JWT_SECRET_KEY")

logger = logging.getLogger("xmlforge.runtime")


def _read_env_file(path):
    data = {}
    if not os.path.isfile(path):
        return data
    with open(path, "r", encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()
    return data


def _write_env_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = "".join(f"{key}={value}\n" for key, value in sorted(data.items()))
    fd, temporary = tempfile.mkstemp(prefix=".xmlforge-secrets-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def ensure_secrets():
    """Garantit des secrets persistants (``SECRET_KEY`` / ``JWT_SECRET_KEY``).

    Priorités :
    1. variable d'environnement déjà définie (source externe, non persistée ici) ;
    2. fichier ``config/secrets.env`` existant (réutilisé) ;
    3. sinon génération aléatoire + persistance (mode 0600 sur POSIX).

    Idempotent : les mêmes valeurs sont réutilisées aux lancements suivants.
    Aucune valeur n'est journalisée.
    """
    path = paths.secrets_file()
    existing = _read_env_file(path)
    changed = False
    for key in _SECRET_KEYS:
        if not os.getenv(key) and key not in existing:
            existing[key] = _secrets.token_urlsafe(48)
            changed = True
    if changed:
        _write_env_file(path, existing)
    for key in _SECRET_KEYS:
        if key in existing:
            os.environ.setdefault(key, existing[key])
    return path


def prepare_runtime():
    """Crée les répertoires runtime + garantit les secrets. Retourne un rapport."""
    directories = [
        paths.control_folder(),
        paths.xml_folder(),
        paths.uploads_folder(),
        paths.exports_folder(),
        paths.logs_folder(),
        paths.config_folder(),
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    if os.name == "posix":
        for directory in (paths.control_folder(), paths.config_folder()):
            try:
                os.chmod(directory, 0o700)
            except OSError:
                pass
    secrets_path = ensure_secrets()
    return {"directories": directories, "secrets_file": secrets_path}


def bootstrap_if_needed(app):
    """Bootstrap XML idempotent (aucune écriture si déjà initialisé)."""
    from .xml_control.service import XmlControlPlaneService

    service = XmlControlPlaneService.from_config(app.config)
    present = [
        path
        for path in (service.security_path(), service.catalog_path(), service.history_path())
        if os.path.exists(path)
    ]
    if present:
        return {"bootstrap": "skipped", "reason": "already-initialized"}
    report = service.bootstrap()
    return {"bootstrap": "created", "storage_folder": report.get("storage_folder")}


def ensure_admin(app, email, name, password):
    """Crée ou promeut un administrateur (idempotent, aucun identifiant codé en dur).

    Retourne ``(ok, message)``.
    """
    from .control_plane import get_backend
    from .services.auth_service import AuthService

    email = (email or "").strip().lower()
    if not email or not password:
        return False, "Email et mot de passe requis pour créer l'administrateur"
    backend = get_backend()
    user = backend.get_user_by_email(email)
    created = False
    if user is None:
        user, error = AuthService.register(name or email.split("@")[0], email, password)
        if error:
            return False, error
        created = True
    role = backend.get_role_by_name("admin")
    if role is None:
        role = backend.ensure_role("admin", "Administrateur XMLForge")
    backend.update_user_fields(user.id, {"role_id": role.id, "is_active": True})
    suffix = "Administrateur créé" if created else "Administrateur mis à jour"
    return True, f"{suffix}: {email}"


def setup_file_logging(app):
    """Logs fichier rotatifs vers ``logs/xmlforge.log`` (aucun secret journalisé).

    - handler unique (idempotent) ;
    - rotation 5 Mio × 3 sauvegardes ;
    - les logs console (développement) restent inchangés.
    """
    from logging.handlers import RotatingFileHandler

    if getattr(app, "_xmlforge_file_logging", False):
        return
    app._xmlforge_file_logging = True

    log_dir = paths.logs_folder()
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "xmlforge.log")

    handler = RotatingFileHandler(
        path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    handler.setLevel(logging.INFO)
    for name in (None, "app", "xmlforge", "werkzeug"):
        target = logging.getLogger(name) if name else logging.getLogger()
        target.addHandler(handler)
        if not target.isEnabledFor(logging.INFO):
            target.setLevel(logging.INFO)
    app.logger.info("Logs fichier initialisés : %s", path)
    return path
