"""Service History V2 - journalisation enrichie (via la couche Control Plane)."""
from ..control_plane import get_backend
from ..utils.helpers import now_utc


class HistoryService:

    @staticmethod
    def log(user_id, user_name, action_type, element_type, element_name, description="",
            database_id=None, table_id=None, ip_address=None, before=None, after=None):
        try:
            entry = get_backend().add_history(
                user_id=user_id, user_name=user_name, action_type=action_type,
                element_type=element_type, element_name=element_name,
                description=description, database_id=database_id, table_id=table_id,
                ip_address=ip_address, before=before, after=after,
                created_at=now_utc(),
            )
            return entry
        except Exception as e:
            print(f"[HistoryService] Erreur log: {e}")
            return None

    @staticmethod
    def get_all(limit=100, database_id=None):
        return get_backend().list_history(limit=limit, database_id=database_id)
