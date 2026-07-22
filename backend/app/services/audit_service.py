"""
Service AuditLog - audit indépendant de l'historique métier
Enregistre : connexion, déconnexion, création base, suppression, import XML, export SQL, conversion, unlock, erreurs
"""
import json
import uuid as uuid_lib
from ..extensions import db
from ..models.audit_log import AuditLog
from ..utils.helpers import now_utc

class AuditService:

    @staticmethod
    def log(user_id=None, user_name=None, ip_address=None, action="", element_type=None, element_name=None, description="", meta=None):
        try:
            meta_str = json.dumps(meta, ensure_ascii=False) if meta is not None else None
            entry = AuditLog(
                uuid=str(uuid_lib.uuid4()),
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                action=action,
                element_type=element_type,
                element_name=element_name,
                description=description,
                meta_data=meta_str,
                timestamp=now_utc()
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception as e:
            db.session.rollback()
            print(f"[AuditService] Erreur log: {e}")
            return None

    @staticmethod
    def get_all(limit=100):
        return AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
