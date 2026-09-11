"""Infrastructure du Control Plane XML — Phase 6A.

Couche unique de gestion des fichiers du Control Plane XML :
lecture, validation (XSD, fail-closed), écriture atomique, verrou,
version optimiste, checksum SHA-256, snapshot/restore.

Les primitives de bas niveau (``atomic_write``, ``database_lock``,
``safe_unlink``) sont **réutilisées** depuis ``app.xml_engine.storage`` —
aucune réimplémentation concurrente. La validation reprend les protections
XXE du Data Plane (``resolve_entities=False``, ``no_network=True``,
``huge_tree=False``).

Règles « fail closed » :
- un fichier absent ou corrompu est une erreur explicite, jamais une
  régénération silencieuse ;
- une mutation avec ``expected_version`` obsolète est refusée (``ConflictError``) ;
- un document non conforme au XSD est refusé **avant** toute écriture.
"""

from __future__ import annotations

import copy
import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache

from lxml import etree

from ..errors import ConflictError, StorageError, XmlValidationError
from ..xml_engine.storage import atomic_write, database_lock, safe_unlink


def _read_bytes(path):
    with open(path, "rb") as stream:
        return stream.read()


def parse_safely(xml_bytes):
    """Parse XXE-safe : mêmes protections que le Data Plane XML."""
    try:
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            remove_blank_text=True,
            huge_tree=False,
        )
        return etree.fromstring(xml_bytes, parser=parser)
    except Exception as exc:
        raise XmlValidationError(f"XML mal formé: {exc}") from exc


@lru_cache(maxsize=None)
def cached_schema(xsd_path):
    """Charge et met en cache un XSD (compilation lxml coûteuse)."""
    try:
        return etree.XMLSchema(etree.parse(str(xsd_path)))
    except Exception as exc:
        raise StorageError(f"Impossible de charger le XSD {xsd_path}: {exc}") from exc


def validate_bytes(xml_bytes, schema):
    """Valide des octets XML contre un schéma ; retourne la racine parsée."""
    root = parse_safely(xml_bytes)
    if not schema.validate(root):
        errors = [e.message for e in schema.error_log]
        raise XmlValidationError(
            "XML non conforme au schéma du Control Plane", details=errors
        )
    return root


def _coerce_schema(schema):
    if isinstance(schema, (str, os.PathLike)):
        return cached_schema(schema)
    return schema


# --------------------------------------------------------------------------
# Répertoire et permissions
# --------------------------------------------------------------------------

def ensure_dir(path, mode=0o700):
    """Crée le répertoire (et ses parents) avec des permissions restreintes.

    Sur Windows, ``os.chmod`` est limité : les bits POSIX sont ignorés sans
    erreur. Le répertoire du Control Plane n'est jamais servi en statique.
    """
    os.makedirs(path, mode=mode, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(path, mode)
        except OSError:
            pass
    return path


def _apply_mode(path, mode):
    if mode is None or os.name != "posix":
        return
    try:
        os.chmod(path, mode)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Lecture / validation
# --------------------------------------------------------------------------

def read(path):
    """Lit les octets bruts ; échoue explicitement si le fichier est absent."""
    if not os.path.exists(path):
        raise StorageError(
            f"Fichier Control Plane introuvable (fail-closed, aucune régénération): {path}"
        )
    return _read_bytes(path)


def read_validated(path, schema=None):
    """Lit et (optionnellement) valide un fichier Control Plane.

    - fichier absent -> ``StorageError`` (fail-closed) ;
    - XML mal formé -> ``XmlValidationError`` ;
    - non conforme au XSD (si fourni) -> ``XmlValidationError`` ;
    - retourne la racine ``etree`` parsée.
    """
    if not os.path.exists(path):
        raise StorageError(
            f"Fichier Control Plane introuvable (fail-closed, aucune régénération): {path}"
        )
    root = parse_safely(_read_bytes(path))
    if schema is not None:
        validate_bytes(etree.tostring(root, encoding="UTF-8"), _coerce_schema(schema))
    return root


# --------------------------------------------------------------------------
# Écriture / mutation
# --------------------------------------------------------------------------

def write(path, content, *, chmod_mode=0o600):
    """Écrit atomiquement (tempfile + fsync + os.replace) puis restreint les droits."""
    atomic_write(path, content)
    _apply_mode(path, chmod_mode)
    return path


def get_version(path):
    """Lit l'attribut ``version`` de la racine (défaut 1)."""
    root = parse_safely(read(path))
    try:
        return int(root.get("version", "1") or 1)
    except (TypeError, ValueError):
        return 1


def mutate(path, mutator, *, expected_version=None, schema=None, chmod_mode=0o600):
    """Mutation versionnée et atomique d'un fichier Control Plane.

    Séquence : verrou -> lecture -> vérification de version -> application du
    ``mutator`` (sur une copie profonde de la racine ``etree``) -> incrément de
    ``version`` -> validation XSD (si fournie, avant écriture) -> écriture
    atomique -> libération du verrou.

    Le ``mutator`` reçoit la racine ``etree`` et la modifie en place ; sa
    valeur de retour est transmise à l'appelant. Une exception du mutator
    n'écrit rien.
    """
    lock_path = os.fspath(path) + ".lock"
    with database_lock(lock_path):
        if not os.path.exists(path):
            raise StorageError(
                f"Fichier Control Plane introuvable (fail-closed, aucune régénération silencieuse): {path}"
            )
        root = parse_safely(_read_bytes(path))
        current_version = int(root.get("version", "1") or 1)
        if expected_version is not None and int(expected_version) != current_version:
            raise ConflictError(
                f"Conflit de version Control Plane: attendu {expected_version}, "
                f"version courante {current_version}",
                details={"current_version": current_version},
            )
        working = copy.deepcopy(root)
        result = mutator(working)
        working.set("version", str(current_version + 1))
        new_bytes = etree.tostring(
            working, encoding="UTF-8", xml_declaration=True, pretty_print=True
        )
        if schema is not None:
            validate_bytes(new_bytes, _coerce_schema(schema))  # fail-closed avant écriture
        atomic_write(path, new_bytes)
        _apply_mode(path, chmod_mode)
        return working, result


# --------------------------------------------------------------------------
# Checksum
# --------------------------------------------------------------------------

def checksum_bytes(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def checksum(path):
    """SHA-256 hexadécimal du contenu ; échoue si le fichier est absent."""
    return checksum_bytes(read(path))


def verify_checksum(path, expected):
    """Vérifie le checksum ; ``False`` en cas d'incohérence, erreur si absent."""
    if not os.path.exists(path):
        raise StorageError(f"Fichier Control Plane introuvable: {path}")
    return checksum(path) == expected


# --------------------------------------------------------------------------
# Snapshot / restore (mono-fichier)
# --------------------------------------------------------------------------

@dataclass
class ControlSnapshot:
    """Instant mémoire d'un fichier Control Plane (octets bruts)."""

    exists: bool
    data: bytes | None


def snapshot(path):
    """Capture l'état courant d'un fichier Control Plane."""
    if os.path.exists(path):
        return ControlSnapshot(exists=True, data=_read_bytes(path))
    return ControlSnapshot(exists=False, data=None)


def restore(path, snap, *, chmod_mode=0o600):
    """Restaure un snapshot : réécriture atomique ou suppression si absent avant."""
    if snap.exists:
        atomic_write(path, snap.data)
        _apply_mode(path, chmod_mode)
    else:
        safe_unlink(path, missing_ok=True)
    return path
