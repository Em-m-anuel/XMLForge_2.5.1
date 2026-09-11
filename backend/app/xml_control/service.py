"""XmlControlPlaneService — couche d'accès au Control Plane XML (Phase 6D).

Centralise lecture, validation, vérifications d'intégrité et mutations des
documents du plan de contrôle : ``security.xml``, ``catalog.xml``,
``history.xml`` et ``audit/audit-YYYY-MM.xml``.

Principes :
- repose sur ``store.py`` (parsing XXE-safe, verrous, écriture atomique,
  version optimiste, checksum, snapshot/restore) et sur ``records.py`` ;
- **fail-closed** : fichier absent/corrompu/invalide ou référence cassée →
  erreur explicite, jamais de régénération silencieuse, jamais de fallback
  SQLite ;
- indépendant de Flask et de SQLAlchemy : fonctionne avec un simple répertoire
  de stockage (facilement instanciable dans les tests) ;
- pas un ORM : les records sont de simples structures de données.

Ce service est l'unique source de vérité du plan de contrôle, consommé par les
services métier REST et TCP (résolution des permissions incluse).
"""

from __future__ import annotations

import copy
import gzip
import json
import os
import re
from contextlib import ExitStack
from datetime import datetime

from lxml import etree

from ..errors import (
    ConflictError,
    ControlPlaneIntegrityError,
    ControlPlaneNotFoundError,
    StorageError,
)
from . import records as R
from . import store

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

# Ordre de verrouillage déterministe (évite les deadlocks entre transactions
# multi-documents). L'audit (fichiers mensuels) est toujours verrouillé après
# les documents principaux, par nom de fichier trié.
LOCK_ORDER = ["security.xml", "catalog.xml", "history.xml"]

DOCS = {
    "security": ("security.xml", "security.xsd"),
    "catalog": ("catalog.xml", "catalog.xsd"),
    "history": ("history.xml", "history.xsd"),
}


def permission_level(can_read=False, can_write=False, can_ddl=False, can_admin=False):
    """Niveau logique dérivé des 4 booléens (identique à PermissionService)."""
    if can_admin:
        return "MANAGE"
    if can_write or can_ddl:
        return "EDIT"
    if can_read:
        return "VIEW"
    return "NONE"


class XmlControlPlaneService:
    def __init__(self, storage_folder=None, *, security_path=None, catalog_path=None,
                 history_path=None, audit_dir=None, xsd_dir=None,
                 common_permission_default="VIEW"):
        self.storage_folder = storage_folder
        self.xsd_dir = xsd_dir or R.XSD_DIR
        self._security_path = security_path or (
            os.path.join(storage_folder, "security.xml") if storage_folder else None)
        self._catalog_path = catalog_path or (
            os.path.join(storage_folder, "catalog.xml") if storage_folder else None)
        self._history_path = history_path or (
            os.path.join(storage_folder, "history.xml") if storage_folder else None)
        self._audit_dir = audit_dir or (
            os.path.join(storage_folder, "audit") if storage_folder else None)
        # Niveau collectif effectif d'une base COMMON sans common_permission
        # (compatibilité avec les bases historiques). Explicitement configurable.
        self.common_permission_default = R._to_common_permission(common_permission_default or "VIEW")

    @classmethod
    def from_config(cls, config):
        """Construit le service à partir d'une configuration (dict-like)."""
        return cls(
            storage_folder=config.get("CONTROL_STORAGE_FOLDER"),
            common_permission_default=config.get("COMMON_PERMISSION_DEFAULT", "VIEW"),
        )

    def bootstrap(self, *, force=False):
        """Initialisation explicite d'un Control Plane XML vierge (sans SQLite).

        Crée ``security.xml`` (rôles admin/user), ``catalog.xml`` (vide,
        ``next_object_id=1``) et ``history.xml`` (vide) si absents. N'écrase
        **jamais** un fichier existant sauf ``force=True``. Fail-closed : si un
        des fichiers existe (et ``force=False``), aucune écriture.
        """
        store.ensure_dir(self.storage_folder, mode=0o700)
        paths = {
            "security": self.security_path(),
            "catalog": self.catalog_path(),
            "history": self.history_path(),
        }
        existing = [name for name, path in paths.items() if os.path.exists(path)]
        if existing and not force:
            raise ControlPlaneIntegrityError(
                f"Control Plane déjà présent ({', '.join(existing)}). "
                "Utilisez force=True pour réinitialiser explicitement.")
        store.ensure_dir(self._audit_dir, mode=0o700)

        security = R.SecurityDocument(
            version=1,
            roles=[R.RoleRecord(1, "admin", description="Administrateur XMLForge"),
                   R.RoleRecord(2, "user", description="Utilisateur XMLForge")],
            users=[], tcp_credentials=[])
        catalog = R.CatalogDocument(version=1, databases=[],
                                    database_permissions=[], table_permissions=[],
                                    next_object_id=1)
        history = R.HistoryDocument(version=1, entries=[])

        store.write(paths["security"], security.to_xml_bytes(validate=True), chmod_mode=0o600)
        store.write(paths["catalog"], catalog.to_xml_bytes(validate=True), chmod_mode=0o600)
        store.write(paths["history"], history.to_xml_bytes(validate=True), chmod_mode=0o600)
        return {"storage_folder": self.storage_folder, "roles": ["admin", "user"],
                "users": 0, "databases": 0}

    # ------------------------------------------------------------------ paths
    def _schema(self, name):
        return store.cached_schema(os.path.join(self.xsd_dir, name))

    def security_path(self):
        if not self._security_path:
            raise StorageError("Chemin security.xml non configuré pour le Control Plane")
        return self._security_path

    def catalog_path(self):
        if not self._catalog_path:
            raise StorageError("Chemin catalog.xml non configuré pour le Control Plane")
        return self._catalog_path

    def history_path(self):
        if not self._history_path:
            raise StorageError("Chemin history.xml non configuré pour le Control Plane")
        return self._history_path

    def audit_path(self, month):
        if not MONTH_RE.fullmatch(month):
            raise ControlPlaneIntegrityError(f"Mois d'audit invalide: {month!r} (attendu YYYY-MM)")
        if not self._audit_dir:
            raise StorageError("Dossier audit non configuré pour le Control Plane")
        return os.path.join(self._audit_dir, f"audit-{month}.xml")

    # ------------------------------------------------------------------ load
    def _load_security(self):
        root = store.read_validated(self.security_path(), schema=self._schema("security.xsd"))
        doc = R.SecurityDocument.from_root(root)
        self._check_security_relations(doc)
        return doc

    def _load_catalog(self):
        root = store.read_validated(self.catalog_path(), schema=self._schema("catalog.xsd"))
        doc = R.CatalogDocument.from_root(root)
        self._check_catalog_internal_relations(doc)
        return doc

    def _load_history(self):
        root = store.read_validated(self.history_path(), schema=self._schema("history.xsd"))
        return R.HistoryDocument.from_root(root)

    @staticmethod
    def _check_security_relations(doc):
        role_ids = {r.internal_id for r in doc.roles}
        problems = []
        for user in doc.users:
            if user.role_id not in role_ids:
                problems.append(f"user {user.internal_id}: role_id {user.role_id} inexistant")
        user_ids = {u.internal_id for u in doc.users}
        for cred in doc.tcp_credentials:
            if cred.user_id not in user_ids:
                problems.append(f"tcp_credential {cred.internal_id}: user_id {cred.user_id} inexistant")
        if problems:
            raise ControlPlaneIntegrityError("; ".join(problems))

    @staticmethod
    def _check_catalog_internal_relations(doc):
        db_ids = {d.internal_id for d in doc.databases}
        problems = []
        for perm in doc.database_permissions:
            if perm.database_id not in db_ids:
                problems.append(
                    f"database_permission {perm.internal_id}: database_id {perm.database_id} inexistant")
        for perm in doc.table_permissions:
            if perm.database_id is not None and perm.database_id not in db_ids:
                problems.append(
                    f"table_permission {perm.internal_id}: database_id {perm.database_id} inexistant")
        if problems:
            raise ControlPlaneIntegrityError("; ".join(problems))

    # ---------------------------------------------------------------- SECURITY reads
    def get_user(self, user_id):
        return next((u for u in self._load_security().users if u.internal_id == user_id), None)

    def get_user_by_email(self, email):
        needle = (email or "").strip().lower()
        return next((u for u in self._load_security().users
                     if (u.email or "").strip().lower() == needle), None)

    def list_users(self):
        return list(self._load_security().users)

    def get_role(self, role_id):
        return next((r for r in self._load_security().roles if r.internal_id == role_id), None)

    def get_role_by_name(self, name):
        needle = (name or "").strip().lower()
        return next((r for r in self._load_security().roles
                     if (r.name or "").strip().lower() == needle), None)

    def list_roles(self):
        return list(self._load_security().roles)

    def get_tcp_credential(self, credential_id):
        return next((c for c in self._load_security().tcp_credentials
                     if c.internal_id == credential_id), None)

    def get_tcp_credential_by_username(self, tcp_username):
        return next((c for c in self._load_security().tcp_credentials
                     if c.tcp_username == tcp_username), None)

    def list_tcp_credentials(self):
        return list(self._load_security().tcp_credentials)

    def get_user_role(self, user_id):
        user = self.get_user(user_id)
        if user is None:
            return None
        return self.get_role(user.role_id)

    # ---------------------------------------------------------------- CATALOG reads
    def get_database(self, database_id):
        return next((d for d in self._load_catalog().databases if d.internal_id == database_id), None)

    def get_database_by_uuid(self, uuid):
        return next((d for d in self._load_catalog().databases if d.uuid == uuid), None)

    def get_database_by_name(self, name):
        return next((d for d in self._load_catalog().databases if d.name == name), None)

    def list_databases(self):
        return list(self._load_catalog().databases)

    def get_database_permission(self, permission_id):
        return next((p for p in self._load_catalog().database_permissions
                     if p.internal_id == permission_id), None)

    def list_database_permissions(self, database_id=None, user_id=None):
        items = self._load_catalog().database_permissions
        if database_id is not None:
            items = [p for p in items if p.database_id == database_id]
        if user_id is not None:
            items = [p for p in items if p.user_id == user_id]
        return items

    def get_table_permission(self, permission_id):
        return next((p for p in self._load_catalog().table_permissions
                     if p.internal_id == permission_id), None)

    def list_table_permissions(self, database_id=None, table_id=None, user_id=None):
        items = self._load_catalog().table_permissions
        if database_id is not None:
            items = [p for p in items if p.database_id == database_id]
        if table_id is not None:
            items = [p for p in items if p.table_id == table_id]
        if user_id is not None:
            items = [p for p in items if p.user_id == user_id]
        return items

    def get_owner_databases(self, user_id):
        return [d for d in self._load_catalog().databases
                if (d.owner_id or d.creator_id) == user_id]

    # ---------------------------------------------------------------- permissions primitives
    def is_admin(self, user_id):
        role = self.get_user_role(user_id)
        return bool(role and role.name.lower() == "admin")

    def is_database_owner(self, user_id, database_id):
        database = self.get_database(database_id)
        return bool(database and (database.owner_id or database.creator_id) == user_id)

    def effective_common_permission(self, database):
        """Niveau collectif effectif d'une base COMMON.

        ``common_permission`` explicite s'il existe, sinon le défaut configuré
        (``COMMON_PERMISSION_DEFAULT``, VIEW). Le défaut n'est appliqué qu'en
        **lecture** : aucune valeur n'est inventée ni réécrite dans le fichier.
        """
        if database.common_permission is not None:
            return database.common_permission
        return self.common_permission_default

    def resolve_database_access(self, user_id, database_id):
        """Primitive de résolution d'accès base (lecture XML seule, pour 6F).

        Ordre identique à PermissionService : absent/inactif → NONE ; admin →
        MANAGE (source "role") ; owner → MANAGE (source "owner") ; COMMON →
        niveau collectif (source "common") ; PERSONAL → grants individuels
        (source "shared" ou "none"). DELETE reste régi par ``can_admin``.

        **Ne remplace pas PermissionService** : c'est une primitive de lecture
        du XML, non encore branchée sur les services métier.
        """
        denied = {"can_read": False, "can_write": False, "can_ddl": False,
                  "can_admin": False, "level": "NONE", "source": "none"}
        user = self.get_user(user_id)
        if user is None or not user.is_active:
            return dict(denied)
        database = self.get_database(database_id)
        if database is None:
            return dict(denied)
        if self.is_admin(user_id):
            return {"can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "role"}
        if self.is_database_owner(user_id, database_id):
            return {"can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "owner"}
        if database.scope == R.Scope.COMMON:
            return self._common_access(self.effective_common_permission(database))
        permission = next((p for p in self._load_catalog().database_permissions
                           if p.database_id == database_id and p.user_id == user_id), None)
        if permission is None:
            return dict(denied)
        access = {
            "can_read": bool(permission.can_read),
            "can_write": bool(permission.can_write),
            "can_ddl": bool(permission.can_ddl),
            "can_admin": bool(permission.can_admin),
            "source": "shared",
        }
        access["level"] = permission_level(
            access["can_read"], access["can_write"], access["can_ddl"], access["can_admin"])
        return access

    @staticmethod
    def _common_access(common_permission):
        if common_permission == R.CommonPermission.MANAGE:
            return {"can_read": True, "can_write": True, "can_ddl": True,
                    "can_admin": True, "level": "MANAGE", "source": "common"}
        if common_permission == R.CommonPermission.EDIT:
            return {"can_read": True, "can_write": True, "can_ddl": False,
                    "can_admin": False, "level": "EDIT", "source": "common"}
        return {"can_read": True, "can_write": False, "can_ddl": False,
                "can_admin": False, "level": "VIEW", "source": "common"}

    # ---------------------------------------------------------------- HISTORY reads
    def get_history(self, history_id):
        return next((e for e in self._load_history().entries if e.internal_id == history_id), None)

    def list_history(self, user_id=None, database_id=None, table_id=None, action=None):
        entries = self._load_history().entries
        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        if database_id is not None:
            entries = [e for e in entries if e.database_id == database_id]
        if table_id is not None:
            entries = [e for e in entries if e.table_id == table_id]
        if action is not None:
            entries = [e for e in entries if e.action_type == action]
        return entries

    # ---------------------------------------------------------------- AUDIT reads
    def list_audit_months(self):
        """Mois d'audit présents (fichiers .xml ou .xml.gz), triés."""
        if not self._audit_dir or not os.path.isdir(self._audit_dir):
            return []
        months = set()
        for name in os.listdir(self._audit_dir):
            m = re.fullmatch(r"audit-(\d{4}-\d{2})\.xml(?:\.gz)?", name)
            if m:
                months.add(m.group(1))
        return sorted(months)

    def _audit_file(self, month):
        """Chemin existant du mois (format .xml ou .xml.gz compressé)."""
        xml_path = self.audit_path(month)
        if os.path.exists(xml_path):
            return xml_path
        gz_path = xml_path + ".gz"
        if os.path.exists(gz_path):
            return gz_path
        return None

    def _load_audit_document(self, month):
        """Charge un mois d'audit (.xml ou .xml.gz). None si absent."""
        path = self._audit_file(month)
        if path is None:
            return None
        if path.endswith(".gz"):
            with gzip.open(path, "rb") as stream:
                return R.AuditDocument.from_xml_bytes(stream.read(), validate=True)
        return R.AuditDocument.from_root(
            store.read_validated(path, schema=self._schema("audit.xsd")))

    def _meta_json(self, entry):
        if not entry.meta_data:
            return {}
        try:
            value = json.loads(entry.meta_data)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def list_audit(self, month=None, user_id=None, database_id=None, table_id=None,
                   action=None, success=None):
        """Lecture d'audit.

        - ``month`` absent : parcourt tous les mois existants (triés).
        - mois absent du disque : résultat vide (état vide contrôlé) — contrairement
          à security.xml/catalog.xml qui sont fail-closed.
        - ``database_id``/``table_id`` sont cherchés (au mieux) dans le JSON de
          ``meta_data`` : ils ne font pas partie du modèle AuditLog réel.
        - ``success`` n'existe pas dans le modèle d'audit actuel (décision 6B) :
          fournir une valeur non-None lève ``ControlPlaneIntegrityError``.
        """
        if success is not None:
            raise ControlPlaneIntegrityError(
                "Le champ 'success' n'existe pas dans le modèle d'audit actuel (cf. 6B).")
        months = [month] if month is not None else self.list_audit_months()
        entries = []
        for m in months:
            doc = self._load_audit_document(m)
            if doc is not None:
                entries.extend(doc.entries)
        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        if action is not None:
            entries = [e for e in entries if e.action == action]
        if database_id is not None:
            entries = [e for e in entries if self._meta_json(e).get("database_id") == database_id]
        if table_id is not None:
            entries = [e for e in entries if self._meta_json(e).get("table_id") == table_id]
        return entries

    def get_audit_entry(self, audit_id, month=None):
        months = [month] if month is not None else reversed(self.list_audit_months())
        for m in months:
            doc = self._load_audit_document(m)
            if doc is None:
                continue
            entry = next((e for e in doc.entries if e.internal_id == audit_id), None)
            if entry is not None:
                return entry
        return None

    # ---------------------------------------------------------------- INTEGRITY
    def validate_integrity(self):
        """Vérifie l'intégrité intra- et inter-documents. Lève une erreur détaillée."""
        security = self._load_security()
        catalog = self._load_catalog()
        problems = []

        user_ids = {u.internal_id for u in security.users}
        role_ids = {r.internal_id for r in security.roles}
        db_ids = {d.internal_id for d in catalog.databases}
        db_by_id = {d.internal_id: d for d in catalog.databases}

        for user in security.users:
            if user.role_id not in role_ids:
                problems.append(f"user {user.internal_id}: role_id {user.role_id} inexistant")
        for cred in security.tcp_credentials:
            if cred.user_id not in user_ids:
                problems.append(f"tcp_credential {cred.internal_id}: user_id {cred.user_id} inexistant")

        for database in catalog.databases:
            if database.creator_id not in user_ids:
                problems.append(f"database {database.internal_id}: creator_id {database.creator_id} inexistant")
            if database.owner_id is not None and database.owner_id not in user_ids:
                problems.append(f"database {database.internal_id}: owner_id {database.owner_id} inexistant")
            if database.scope == R.Scope.PERSONAL and database.common_permission is not None:
                problems.append(f"database {database.internal_id}: PERSONAL avec common_permission")

        # Unicité (owner effectif, name) — identique à la règle SQLite
        # (DatabaseService : filter_by(owner_id, name)). Une base COMMON sans
        # common_permission est un état historique valide : le niveau collectif
        # effectif est le défaut configuré (COMMON_PERMISSION_DEFAULT).
        seen_owner_name = {}
        for database in catalog.databases:
            owner = database.owner_id or database.creator_id
            key = (owner, database.name)
            if key in seen_owner_name:
                problems.append(
                    f"databases {seen_owner_name[key]} et {database.internal_id}: "
                    f"même couple (owner_id={owner}, name={database.name!r})")
            else:
                seen_owner_name[key] = database.internal_id

        for perm in catalog.database_permissions:
            if perm.database_id not in db_ids:
                problems.append(f"database_permission {perm.internal_id}: database_id {perm.database_id} inexistant")
            if perm.user_id not in user_ids:
                problems.append(f"database_permission {perm.internal_id}: user_id {perm.user_id} inexistant")
            if perm.database_id in db_by_id and db_by_id[perm.database_id].scope == R.Scope.COMMON:
                problems.append(
                    f"database_permission {perm.internal_id}: grant individuel sur une base "
                    f"COMMON (database_id {perm.database_id})")

        for perm in catalog.table_permissions:
            if perm.database_id is not None and perm.database_id not in db_ids:
                problems.append(f"table_permission {perm.internal_id}: database_id {perm.database_id} inexistant")
            if perm.user_id not in user_ids:
                problems.append(f"table_permission {perm.internal_id}: user_id {perm.user_id} inexistant")
            if perm.database_id is not None:
                db = db_by_id.get(perm.database_id)
                if db is not None and db.scope == R.Scope.COMMON:
                    problems.append(
                        f"table_permission {perm.internal_id}: grant individuel sur une base COMMON "
                        f"(database_id {perm.database_id})")

        if problems:
            raise ControlPlaneIntegrityError("; ".join(problems))
        return {"security": security, "catalog": catalog}

    def validate_data_plane_references(self, xml_storage_folder=None):
        """Vérifie ``table_permission.table_id`` contre les Data Plane XML.

        Ne recopie aucune table : vérifie seulement qu'une table dont
        ``internal_id == table_id`` existe dans le document XML de la base
        référencée. Toute base/table introuvable → erreur explicite.
        """
        from ..xml_engine.document import parse_document

        catalog = self._load_catalog()
        db_by_id = {d.internal_id: d for d in catalog.databases}
        problems = []
        checked = 0
        for perm in catalog.table_permissions:
            if perm.database_id is None:
                continue
            database = db_by_id.get(perm.database_id)
            if database is None:
                problems.append(f"table_permission {perm.internal_id}: database_id {perm.database_id} inexistant")
                continue
            xml_path = database.xml_file_path
            if not xml_path:
                problems.append(f"database {database.internal_id}: xml_file_path absent")
                continue
            if not os.path.isabs(xml_path):
                if not xml_storage_folder:
                    problems.append(
                        f"database {database.internal_id}: chemin relatif sans dossier Data Plane fourni")
                    continue
                xml_path = os.path.join(xml_storage_folder, xml_path)
            if not os.path.exists(xml_path):
                problems.append(f"database {database.internal_id}: fichier Data Plane introuvable {xml_path}")
                continue
            with open(xml_path, "rb") as stream:
                document = parse_document(stream.read(), validate=True)
            table_ids = {t.get("internal_id") for t in document.get("tables", [])}
            if perm.table_id not in table_ids:
                problems.append(
                    f"table_permission {perm.internal_id}: table_id {perm.table_id} absent du Data Plane "
                    f"de la base {database.internal_id}")
            else:
                checked += 1
        if problems:
            raise ControlPlaneIntegrityError("; ".join(problems))
        return {"checked": checked}

    # ---------------------------------------------------------------- MUTATIONS (helpers)
    def _mutate(self, doc_name, mutator, expected_version=None):
        filename, xsd = DOCS[doc_name]
        path = self._path_for(doc_name)
        return store.mutate(
            path, mutator, expected_version=expected_version,
            schema=self._schema(xsd), chmod_mode=0o600,
        )

    def _path_for(self, doc_name):
        return {
            "security": self.security_path(),
            "catalog": self.catalog_path(),
            "history": self.history_path(),
        }[doc_name]

    def _control_plane_transaction(self, ops, expected_versions=None):
        """Transaction multi-documents : verrous ordonnés + snapshot/rollback.

        ``ops`` : liste de tuples ``(doc_name, mutator)``. Chaque mutateur reçoit
        la racine ``etree`` du document et la modifie en place. Un mutateur qui
        retourne ``False`` signifie « aucune modification » : le document n'est
        alors ni versionné ni réécrit (il sert uniquement de garde cohérente,
        verrou tenu pendant toute la transaction). Les versions sont incrémentées
        indépendamment par document modifié ; tout échec restaure les snapshots
        (aucune transaction ACID SQL — voir rapport).
        """
        expected_versions = expected_versions or {}
        # Tri par ordre de verrouillage déterministe pour éviter les deadlocks.
        ordered = sorted(ops, key=lambda o: self._lock_rank(o[0]))
        roots = {}
        snapshots = {}
        try:
            with ExitStack() as stack:
                for doc_name, _ in ordered:
                    stack.enter_context(store.database_lock(self._path_for(doc_name) + ".lock"))

                # Lecture + vérification de version pour chaque document.
                for doc_name, _ in ordered:
                    path = self._path_for(doc_name)
                    if not os.path.exists(path):
                        raise StorageError(
                            f"Fichier Control Plane introuvable (fail-closed): {path}")
                    root = store.parse_safely(store.read(path))
                    current = int(root.get("version", "1") or 1)
                    exp = expected_versions.get(doc_name)
                    if exp is not None and int(exp) != current:
                        raise ConflictError(
                            f"Conflit de version Control Plane sur {doc_name}: attendu {exp}, "
                            f"courant {current}", details={"current_version": current})
                    roots[doc_name] = root

                # Application des mutateurs sur des copies profondes + validation XSD.
                changed = set()
                for doc_name, mutator in ordered:
                    _, xsd = DOCS[doc_name]
                    working = copy.deepcopy(roots[doc_name])
                    result = mutator(working)
                    if result is False:
                        continue  # garde cohérente uniquement : pas d'écriture
                    current = int(roots[doc_name].get("version", "1") or 1)
                    working.set("version", str(current + 1))
                    store.validate_bytes(etree.tostring(working, encoding="UTF-8"), self._schema(xsd))
                    roots[doc_name] = working
                    changed.add(doc_name)

                # Snapshot puis écriture atomique des documents modifiés.
                for doc_name in changed:
                    snapshots[doc_name] = store.snapshot(self._path_for(doc_name))
                for doc_name in changed:
                    store.write(
                        self._path_for(doc_name),
                        etree.tostring(roots[doc_name], encoding="UTF-8",
                                       xml_declaration=True, pretty_print=True),
                        chmod_mode=0o600,
                    )
        except Exception:
            for doc_name, snap in snapshots.items():
                store.restore(self._path_for(doc_name), snap)
            raise
        return {doc_name: roots[doc_name] for doc_name in changed}

    @staticmethod
    def _lock_rank(doc_name):
        filename = DOCS[doc_name][0]
        try:
            return LOCK_ORDER.index(filename)
        except ValueError:
            return len(LOCK_ORDER)

    # ---------------------------------------------------------------- SECURITY mutations
    @staticmethod
    def _next_id(items, attr="internal_id"):
        ids = [getattr(i, attr) for i in items if getattr(i, attr) is not None]
        return (max(ids) + 1) if ids else 1

    @staticmethod
    def _assert_unique(values, label):
        duplicates = {v for v in values if values.count(v) > 1}
        if duplicates:
            raise ControlPlaneIntegrityError(f"{label} en double: {sorted(duplicates)}")

    def _validate_user(self, record, doc, exclude_internal_id=None):
        if not record.password_hash:
            raise ControlPlaneIntegrityError(
                f"user {record.internal_id}: password_hash obligatoire")
        if not record.full_name:
            raise ControlPlaneIntegrityError(f"user {record.internal_id}: full_name obligatoire")
        if not record.email:
            raise ControlPlaneIntegrityError(f"user {record.internal_id}: email obligatoire")
        # Cohérence avec le modèle SQLAlchemy : token_version est INTEGER avec
        # default=1, sans contrainte CHECK ; la valeur 0 y est donc stockable
        # (et coercée en 1 au moment de la comparaison JWT via `or 1`). Le XML
        # autorise donc 0 et rejette uniquement les valeurs négatives.
        if record.token_version < 0:
            raise ControlPlaneIntegrityError(
                f"user {record.internal_id}: token_version ne peut pas être négatif")
        if record.role_id not in {r.internal_id for r in doc.roles}:
            raise ControlPlaneIntegrityError(
                f"user {record.internal_id}: role_id {record.role_id} inexistant")
        for other in doc.users:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            if (other.email or "").strip().lower() == (record.email or "").strip().lower():
                raise ControlPlaneIntegrityError(f"email déjà utilisé: {record.email}")
            if record.uuid and other.uuid == record.uuid:
                raise ControlPlaneIntegrityError(f"uuid déjà utilisé: {record.uuid}")

    def create_user(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.users)
            if any(u.internal_id == record.internal_id for u in doc.users):
                raise ControlPlaneIntegrityError(f"user internal_id déjà utilisé: {record.internal_id}")
            self._validate_user(record, doc)
            root.find("users").append(record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def update_user(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            target = next((u for u in doc.users if u.internal_id == record.internal_id), None)
            if target is None:
                raise ControlPlaneNotFoundError(f"user {record.internal_id} introuvable")
            self._validate_user(record, doc, exclude_internal_id=record.internal_id)
            users = root.find("users")
            elem = next(e for e in users.findall("user")
                        if int(e.get("internal_id")) == record.internal_id)
            users.replace(elem, record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def delete_user(self, user_id, expected_versions=None):
        """Suppression avec politique RESTRICT : échec si l'utilisateur est
        référencé (credentials TCP, grants, bases possédées/créées).

        ``expected_versions`` : dict ``{"security": v, "catalog": v}`` optionnel.
        La garde sur ``catalog.xml`` est vérifiée sous verrou sans réécriture.
        """
        def sec_mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if any(c.user_id == user_id for c in doc.tcp_credentials):
                raise ControlPlaneIntegrityError(
                    f"user {user_id} possède des credentials TCP (RESTRICT)")
            users = root.find("users")
            elem = next((e for e in users.findall("user")
                         if int(e.get("internal_id")) == user_id), None)
            if elem is None:
                raise ControlPlaneNotFoundError(f"user {user_id} introuvable")
            users.remove(elem)

        def cat_mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if any(p.user_id == user_id for p in doc.database_permissions):
                raise ControlPlaneIntegrityError(
                    f"user {user_id} référencé par un database_permission (RESTRICT)")
            if any(p.user_id == user_id for p in doc.table_permissions):
                raise ControlPlaneIntegrityError(
                    f"user {user_id} référencé par un table_permission (RESTRICT)")
            if any((d.owner_id or d.creator_id) == user_id for d in doc.databases):
                raise ControlPlaneIntegrityError(
                    f"user {user_id} possède des bases (RESTRICT)")
            return False  # garde cohérente uniquement

        self._control_plane_transaction(
            [("security", sec_mutator), ("catalog", cat_mutator)],
            expected_versions=expected_versions,
        )
        return True

    def _validate_role(self, record, doc, exclude_internal_id=None):
        if not record.name:
            raise ControlPlaneIntegrityError(f"role {record.internal_id}: name obligatoire")
        for other in doc.roles:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            if (other.name or "").strip().lower() == (record.name or "").strip().lower():
                raise ControlPlaneIntegrityError(f"nom de rôle déjà utilisé: {record.name}")

    def create_role(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.roles)
            if any(r.internal_id == record.internal_id for r in doc.roles):
                raise ControlPlaneIntegrityError(f"role internal_id déjà utilisé: {record.internal_id}")
            self._validate_role(record, doc)
            root.find("roles").append(record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def update_role(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if not any(r.internal_id == record.internal_id for r in doc.roles):
                raise ControlPlaneNotFoundError(f"role {record.internal_id} introuvable")
            self._validate_role(record, doc, exclude_internal_id=record.internal_id)
            roles = root.find("roles")
            elem = next(e for e in roles.findall("role")
                        if int(e.get("internal_id")) == record.internal_id)
            roles.replace(elem, record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def _validate_tcp_credential(self, record, doc, exclude_internal_id=None):
        if not record.tcp_password:
            raise ControlPlaneIntegrityError(
                f"tcp_credential {record.internal_id}: password_hash obligatoire")
        if not record.tcp_username:
            raise ControlPlaneIntegrityError(
                f"tcp_credential {record.internal_id}: tcp_username obligatoire")
        if not (1 <= record.tcp_port <= 65535):
            raise ControlPlaneIntegrityError(
                f"tcp_credential {record.internal_id}: tcp_port hors bornes ({record.tcp_port})")
        if record.user_id not in {u.internal_id for u in doc.users}:
            raise ControlPlaneIntegrityError(
                f"tcp_credential {record.internal_id}: user_id {record.user_id} inexistant")
        for other in doc.tcp_credentials:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            if other.tcp_username == record.tcp_username:
                raise ControlPlaneIntegrityError(f"tcp_username déjà utilisé: {record.tcp_username}")
            if other.user_id == record.user_id:
                raise ControlPlaneIntegrityError(
                    f"un credential TCP existe déjà pour user_id {record.user_id}")

    def create_tcp_credential(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.tcp_credentials)
            if any(c.internal_id == record.internal_id for c in doc.tcp_credentials):
                raise ControlPlaneIntegrityError(
                    f"tcp_credential internal_id déjà utilisé: {record.internal_id}")
            self._validate_tcp_credential(record, doc)
            root.find("tcp_credentials").append(record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def update_tcp_credential(self, record, expected_version=None):
        def mutator(root):
            doc = R.SecurityDocument.from_root(root)
            if not any(c.internal_id == record.internal_id for c in doc.tcp_credentials):
                raise ControlPlaneNotFoundError(f"tcp_credential {record.internal_id} introuvable")
            self._validate_tcp_credential(record, doc, exclude_internal_id=record.internal_id)
            container = root.find("tcp_credentials")
            elem = next(e for e in container.findall("credential")
                        if int(e.get("internal_id")) == record.internal_id)
            container.replace(elem, record.to_element())
        self._mutate("security", mutator, expected_version)
        return record

    def delete_tcp_credential(self, credential_id, expected_version=None):
        def mutator(root):
            container = root.find("tcp_credentials")
            elem = next((e for e in container.findall("credential")
                         if int(e.get("internal_id")) == credential_id), None)
            if elem is None:
                raise ControlPlaneNotFoundError(f"tcp_credential {credential_id} introuvable")
            container.remove(elem)
        self._mutate("security", mutator, expected_version)
        return True

    # ---------------------------------------------------------------- CATALOG mutations
    def _validate_database(self, record, doc, security_users, exclude_internal_id=None):
        # Règle réelle (DatabaseService, SQLite) : l'unicité du nom est
        # **par propriétaire** (owner_id effectif = owner_id ou creator_id),
        # pas globale. Deux propriétaires peuvent avoir une base homonyme.
        if record.scope == R.Scope.PERSONAL and record.common_permission is not None:
            raise ControlPlaneIntegrityError(
                f"database {record.internal_id}: scope PERSONAL ne doit pas porter common_permission")
        if record.creator_id not in security_users:
            raise ControlPlaneIntegrityError(
                f"database {record.internal_id}: creator_id {record.creator_id} inexistant")
        if record.owner_id is not None and record.owner_id not in security_users:
            raise ControlPlaneIntegrityError(
                f"database {record.internal_id}: owner_id {record.owner_id} inexistant")
        owner = record.owner_id or record.creator_id
        for other in doc.databases:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            other_owner = other.owner_id or other.creator_id
            if other.name == record.name and other_owner == owner:
                raise ControlPlaneIntegrityError(
                    f"nom de base déjà utilisé par ce propriétaire (owner_id={owner}): {record.name}")
            if record.uuid and other.uuid == record.uuid:
                raise ControlPlaneIntegrityError(f"uuid de base déjà utilisé: {record.uuid}")
            if other.key_identifier == record.key_identifier:
                raise ControlPlaneIntegrityError(
                    f"key_identifier déjà utilisé: {record.key_identifier}")

    def create_database(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.databases)
            if any(d.internal_id == record.internal_id for d in doc.databases):
                raise ControlPlaneIntegrityError(
                    f"database internal_id déjà utilisé: {record.internal_id}")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_database(record, doc, security_users)
            root.find("databases").append(record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def update_database(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if not any(d.internal_id == record.internal_id for d in doc.databases):
                raise ControlPlaneNotFoundError(f"database {record.internal_id} introuvable")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_database(record, doc, security_users, exclude_internal_id=record.internal_id)
            databases = root.find("databases")
            elem = next(e for e in databases.findall("database")
                        if int(e.get("internal_id")) == record.internal_id)
            databases.replace(elem, record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def delete_database(self, database_id, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if any(p.database_id == database_id for p in doc.database_permissions):
                raise ControlPlaneIntegrityError(
                    f"database {database_id} référencée par un database_permission (RESTRICT)")
            if any(p.database_id == database_id for p in doc.table_permissions):
                raise ControlPlaneIntegrityError(
                    f"database {database_id} référencée par un table_permission (RESTRICT)")
            databases = root.find("databases")
            elem = next((e for e in databases.findall("database")
                         if int(e.get("internal_id")) == database_id), None)
            if elem is None:
                raise ControlPlaneNotFoundError(f"database {database_id} introuvable")
            databases.remove(elem)
        self._mutate("catalog", mutator, expected_version)
        return True

    def _validate_database_permission(self, record, doc, security_users, exclude_internal_id=None):
        database = next((d for d in doc.databases if d.internal_id == record.database_id), None)
        if database is None:
            raise ControlPlaneIntegrityError(
                f"database_permission {record.internal_id}: database_id {record.database_id} inexistant")
        if database.scope == R.Scope.COMMON:
            raise ControlPlaneIntegrityError(
                f"database_permission {record.internal_id}: les bases COMMON utilisent un "
                "accès collectif (common_permission), pas de grants individuels")
        if record.user_id not in security_users:
            raise ControlPlaneIntegrityError(
                f"database_permission {record.internal_id}: user_id {record.user_id} inexistant")
        for other in doc.database_permissions:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            if other.database_id == record.database_id and other.user_id == record.user_id:
                raise ControlPlaneIntegrityError(
                    f"database_permission déjà présent pour (database_id={record.database_id}, "
                    f"user_id={record.user_id})")

    def create_database_permission(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.database_permissions)
            if any(p.internal_id == record.internal_id for p in doc.database_permissions):
                raise ControlPlaneIntegrityError(
                    f"database_permission internal_id déjà utilisé: {record.internal_id}")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_database_permission(record, doc, security_users)
            root.find("database_permissions").append(record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def update_database_permission(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if not any(p.internal_id == record.internal_id for p in doc.database_permissions):
                raise ControlPlaneNotFoundError(
                    f"database_permission {record.internal_id} introuvable")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_database_permission(record, doc, security_users,
                                               exclude_internal_id=record.internal_id)
            container = root.find("database_permissions")
            elem = next(e for e in container.findall("database_permission")
                        if int(e.get("internal_id")) == record.internal_id)
            container.replace(elem, record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def delete_database_permission(self, permission_id, expected_version=None):
        def mutator(root):
            container = root.find("database_permissions")
            elem = next((e for e in container.findall("database_permission")
                         if int(e.get("internal_id")) == permission_id), None)
            if elem is None:
                raise ControlPlaneNotFoundError(
                    f"database_permission {permission_id} introuvable")
            container.remove(elem)
        self._mutate("catalog", mutator, expected_version)
        return True

    def _validate_table_permission(self, record, doc, security_users, exclude_internal_id=None):
        if record.user_id not in security_users:
            raise ControlPlaneIntegrityError(
                f"table_permission {record.internal_id}: user_id {record.user_id} inexistant")
        if record.database_id is not None and record.database_id not in {d.internal_id for d in doc.databases}:
            raise ControlPlaneIntegrityError(
                f"table_permission {record.internal_id}: database_id {record.database_id} inexistant")
        for other in doc.table_permissions:
            if exclude_internal_id is not None and other.internal_id == exclude_internal_id:
                continue
            if other.table_id == record.table_id and other.user_id == record.user_id:
                raise ControlPlaneIntegrityError(
                    f"table_permission déjà présent pour (table_id={record.table_id}, "
                    f"user_id={record.user_id})")

    def create_table_permission(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if record.internal_id is None:
                record.internal_id = self._next_id(doc.table_permissions)
            if any(p.internal_id == record.internal_id for p in doc.table_permissions):
                raise ControlPlaneIntegrityError(
                    f"table_permission internal_id déjà utilisé: {record.internal_id}")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_table_permission(record, doc, security_users)
            root.find("table_permissions").append(record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def update_table_permission(self, record, expected_version=None):
        def mutator(root):
            doc = R.CatalogDocument.from_root(root)
            if not any(p.internal_id == record.internal_id for p in doc.table_permissions):
                raise ControlPlaneNotFoundError(f"table_permission {record.internal_id} introuvable")
            security_users = {u.internal_id for u in self._load_security().users}
            self._validate_table_permission(record, doc, security_users,
                                            exclude_internal_id=record.internal_id)
            container = root.find("table_permissions")
            elem = next(e for e in container.findall("table_permission")
                        if int(e.get("internal_id")) == record.internal_id)
            container.replace(elem, record.to_element())
        self._mutate("catalog", mutator, expected_version)
        return record

    def delete_table_permission(self, permission_id, expected_version=None):
        def mutator(root):
            container = root.find("table_permissions")
            elem = next((e for e in container.findall("table_permission")
                         if int(e.get("internal_id")) == permission_id), None)
            if elem is None:
                raise ControlPlaneNotFoundError(f"table_permission {permission_id} introuvable")
            container.remove(elem)
        self._mutate("catalog", mutator, expected_version)
        return True

    def _max_data_plane_object_id(self, xml_storage_folder=None):
        """Max des internal_id (tables/colonnes/lignes) sur tous les Data Plane XML.

        Utilisé pour amorcer le compteur global ``next_object_id`` du catalogue
        en mode XML-only (aucun ORM). Retourne 0 si aucune donnée.
        """
        from ..xml_engine.document import parse_document

        maximum = 0
        databases = self.list_databases()
        for database in databases:
            if database.internal_id:
                maximum = max(maximum, int(database.internal_id))
        for database in databases:
            xml_path = database.xml_file_path
            if not xml_path:
                continue
            if not os.path.isabs(xml_path):
                if not xml_storage_folder:
                    continue
                xml_path = os.path.join(xml_storage_folder, xml_path)
            if not os.path.exists(xml_path):
                continue
            with open(xml_path, "rb") as stream:
                document = parse_document(stream.read(), validate=False)
            for table in document.get("tables", []):
                if table.get("internal_id"):
                    maximum = max(maximum, int(table["internal_id"]))
                for column in table.get("columns", []):
                    if column.get("internal_id"):
                        maximum = max(maximum, int(column["internal_id"]))
                for row in table.get("rows", []):
                    if row.get("internal_id"):
                        maximum = max(maximum, int(row["internal_id"]))
        return maximum

    def allocate_object_id(self, xml_storage_folder=None, expected_version=None):
        """Alloue un identifiant global Data Plane (tables/colonnes/lignes).

        Le compteur ``next_object_id`` vit dans catalog.xml (attribut racine) ;
        l'allocation est atomique (verrou catalog). Amorcé au max des IDs déjà
        présents dans les documents Data Plane si le compteur est absent.
        """
        holder = {}

        def mutator(root):
            current = root.get("next_object_id")
            if current is None:
                current = self._max_data_plane_object_id(xml_storage_folder) + 1
            else:
                current = int(current)
            holder["id"] = current
            root.set("next_object_id", str(current + 1))

        self._mutate("catalog", mutator, expected_version)
        return holder["id"]

    # ---------------------------------------------------------------- HISTORY / AUDIT mutations
    def add_history(self, record, expected_version=None):
        def mutator(root):
            entries = root.find("entries")
            if record.internal_id is None:
                ids = [int(e.get("internal_id")) for e in entries.findall("entry")
                       if e.get("internal_id") is not None]
                record.internal_id = (max(ids) + 1) if ids else 1
            if any(int(e.get("internal_id")) == record.internal_id for e in entries.findall("entry")):
                raise ControlPlaneIntegrityError(
                    f"history internal_id déjà utilisé: {record.internal_id}")
            entries.append(record.to_element())
        self._mutate("history", mutator, expected_version)
        return record

    def add_audit(self, record, month, expected_version=None):
        """Ajoute une entrée au mois d'audit donné.

        Contrairement aux documents principaux, un fichier mensuel absent est
        **créé** à la première écriture du mois (état vide contrôlé, documenté).
        L'attribut ``version`` du fichier mensuel reste à ``1`` : ce n'est pas
        un compteur fonctionnel (journal append-only, unicité par
        ``internal_id`` sous verrou).
        """
        if not MONTH_RE.fullmatch(month):
            raise ControlPlaneIntegrityError(f"Mois d'audit invalide: {month!r} (attendu YYYY-MM)")
        path = self.audit_path(month)
        # Allocation d'identifiant global (tous mois confondus) si absent.
        if record.internal_id is None:
            all_entries = self.list_audit()
            ids = [e.internal_id for e in all_entries if e.internal_id is not None]
            record.internal_id = (max(ids) + 1) if ids else 1

        # Append verrouillé : la création du mois et l'ajout d'entrées sont
        # sérialisés sur le même verrou (aucune perte en écriture concurrente).
        with store.database_lock(path + ".lock"):
            if not os.path.exists(path):
                store.ensure_dir(os.path.dirname(path), mode=0o700)
                document = R.AuditDocument(month=month, version=1, entries=[record])
                store.write(path, document.to_xml_bytes(validate=True), chmod_mode=0o600)
                return record

            current = store.parse_safely(store.read(path))
            entries = current.find("entries")
            if any(int(e.get("internal_id")) == record.internal_id for e in entries.findall("entry")):
                raise ControlPlaneIntegrityError(
                    f"audit internal_id déjà utilisé: {record.internal_id}")
            entries.append(record.to_element())
            data = etree.tostring(current, encoding="UTF-8", xml_declaration=True, pretty_print=True)
            store.validate_bytes(data, self._schema("audit.xsd"))
            store.atomic_write(path, data)
            store._apply_mode(path, 0o600)
        return record

    # ---------------------------------------------------------------- AUDIT rotation / rétention
    @staticmethod
    def _months_back(month, n):
        """Retourne le mois ``n`` mois avant ``month`` (format YYYY-MM)."""
        year, mon = int(month[:4]), int(month[5:7])
        total = year * 12 + (mon - 1) - n
        return f"{total // 12:04d}-{total % 12 + 1:02d}"

    def audit_policy(self, retention_months=24, compress=True, now=None):
        """Rotation de l'audit : compression des mois anciens + purge des mois
        dépassant la rétention.

        - Le **mois courant n'est jamais compressé ni supprimé**.
        - Les mois antérieurs au mois courant sont compressés (.xml -> .xml.gz)
          si ``compress=True``.
        - Les mois strictement antérieurs à ``courant - (retention_months - 1)``
          sont supprimés (fichiers .xml ou .xml.gz), uniquement s'ils ne sont
          pas le mois courant.
        - Retourne un rapport ``{current, compressed, purged}``.
        """
        if not self._audit_dir or not os.path.isdir(self._audit_dir):
            return {"current": None, "compressed": [], "purged": []}
        current = (now or datetime.utcnow()).strftime("%Y-%m")
        cutoff = self._months_back(current, max(0, int(retention_months) - 1))
        compressed, purged = [], []

        for month in self.list_audit_months():
            if month == current:
                continue
            xml_path = self.audit_path(month)
            gz_path = xml_path + ".gz"
            # Compression des mois anciens (une seule fois).
            if compress and os.path.exists(xml_path) and not os.path.exists(gz_path):
                with open(xml_path, "rb") as src, gzip.open(gz_path, "wb") as dst:
                    dst.write(src.read())
                os.chmod(gz_path, 0o600)
                store.safe_unlink(xml_path, missing_ok=True)
                compressed.append(month)
            # Purge au-delà de la rétention (jamais le mois courant).
            if month < cutoff:
                for candidate in (xml_path, gz_path):
                    if os.path.exists(candidate):
                        store.safe_unlink(candidate, missing_ok=True)
                purged.append(month)
        return {"current": current, "compressed": compressed, "purged": purged}

    # ---------------------------------------------------------------- VERSION / CHECKSUM / SNAPSHOT
    def _resolve_document_path(self, document):
        if document == "security":
            return self.security_path()
        if document == "catalog":
            return self.catalog_path()
        if document == "history":
            return self.history_path()
        if isinstance(document, str) and document.startswith("audit:"):
            return self.audit_path(document.split(":", 1)[1])
        raise ControlPlaneIntegrityError(f"document inconnu: {document!r}")

    def get_document_version(self, document):
        return store.get_version(self._resolve_document_path(document))

    def get_document_checksum(self, document):
        return store.checksum(self._resolve_document_path(document))

    def snapshot_document(self, document):
        return store.snapshot(self._resolve_document_path(document))

    def restore_document(self, document, snap):
        return store.restore(self._resolve_document_path(document), snap)


__all__ = ["XmlControlPlaneService", "permission_level"]
