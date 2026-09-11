"""Service AuditLog - audit indépendant (via la couche Control Plane)."""
from ..control_plane import get_backend
from ..utils.helpers import now_utc


class AuditService:

    @staticmethod
    def log(user_id=None, user_name=None, ip_address=None, action="", element_type=None,
            element_name=None, description="", meta=None):
        try:
            entry = get_backend().add_audit(
                user_id=user_id, user_name=user_name, ip_address=ip_address, action=action,
                element_type=element_type, element_name=element_name,
                description=description, meta=meta, timestamp=now_utc(),
            )
            return entry
        except Exception as e:
            print(f"[AuditService] Erreur log: {e}")
            return None

    @staticmethod
    def get_all(limit=100):
        return get_backend().list_audit(limit=limit)
