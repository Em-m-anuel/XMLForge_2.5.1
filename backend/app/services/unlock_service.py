"""Service Unlock — déverrouillage personnel par utilisateur/session.

Stockage **mémoire** (volatil, décision Phase 6) : un redémarrage efface les
déverrouillages. Aucune dépendance SQLite.
"""

from datetime import datetime, timedelta

from ..data_plane import get_table
from ..utils.helpers import now_utc

_memory_unlocks = {}


class _MemoryUnlock:
    def __init__(self, user_id, table_id, unlocked_at, expires_at):
        self.id = None
        self.user_id = user_id
        self.table_id = table_id
        self.unlocked_at = unlocked_at
        self.expires_at = expires_at

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            "id": None, "user_id": self.user_id, "table_id": self.table_id,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
        }


class UnlockService:
    @staticmethod
    def is_unlocked(user_id, table_id):
        expires = _memory_unlocks.get((int(user_id), int(table_id)))
        if not expires:
            return False
        if expires < datetime.utcnow():
            _memory_unlocks.pop((int(user_id), int(table_id)), None)
            return False
        return True

    @staticmethod
    def _valid_keys(table, database):
        valid = []
        if getattr(table, "file_identifier", None):
            valid.append(table.file_identifier)
        if database is not None and getattr(database, "key_identifier", None):
            valid.append(database.key_identifier)
        return valid

    @staticmethod
    def unlock_table(user_id, table_id, provided_key):
        table = get_table(table_id)
        if not table:
            return False, "Table introuvable"
        from ..control_plane import get_backend
        database = get_backend().get_database(getattr(table, "database_id", None))
        if not database:
            return False, "Base introuvable"
        if not getattr(table, "is_protected", False):
            return True, "Table non protégée, accès autorisé"
        if provided_key not in UnlockService._valid_keys(table, database):
            return False, "Clé invalide"
        _memory_unlocks[(int(user_id), int(table_id))] = datetime.utcnow() + timedelta(hours=24)
        return True, "Table déverrouillée pour votre session"

    @staticmethod
    def list_user_unlocks(user_id):
        valid = []
        for (uid, tid), expires in list(_memory_unlocks.items()):
            if uid != int(user_id):
                continue
            if expires < datetime.utcnow():
                _memory_unlocks.pop((uid, tid), None)
                continue
            valid.append(_MemoryUnlock(uid, tid, None, expires))
        return valid

    @staticmethod
    def clear_user_unlocks(user_id):
        for key in [k for k in _memory_unlocks if k[0] == int(user_id)]:
            _memory_unlocks.pop(key, None)

    @staticmethod
    def clear_expired():
        now = datetime.utcnow()
        for key in [k for k, v in _memory_unlocks.items() if v < now]:
            _memory_unlocks.pop(key, None)

    @staticmethod
    def check_protection(user_id, table, provided_key=None):
        if not getattr(table, "is_protected", False):
            return True, None
        if user_id and UnlockService.is_unlocked(user_id, table.id):
            return True, None
        if not provided_key:
            return False, f"Table '{table.name}' protégée, clé requise"
        from ..control_plane import get_backend
        database = get_backend().get_database(getattr(table, "database_id", None))
        if provided_key in UnlockService._valid_keys(table, database):
            return True, None
        return False, "Clé invalide pour table protégée"
