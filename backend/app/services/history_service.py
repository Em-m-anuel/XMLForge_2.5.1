"""
Service History V2 - journalisation enrichie
UUID, IP, before/after
"""
import json
import uuid as uuid_lib
from ..extensions import db
from ..models.history import History
from ..utils.helpers import now_utc

class HistoryService:

    @staticmethod
    def log(user_id, user_name, action_type, element_type, element_name, description="", database_id=None, table_id=None, ip_address=None, before=None, after=None):
        try:
            before_str = json.dumps(before, ensure_ascii=False) if before is not None else None
            after_str = json.dumps(after, ensure_ascii=False) if after is not None else None

            entry = History(
                uuid=str(uuid_lib.uuid4()),
                user_id=user_id,
                user_name=user_name,
                action_type=action_type,
                element_type=element_type,
                element_name=element_name,
                description=description,
                database_id=database_id,
                table_id=table_id,
                ip_address=ip_address,
                before_data=before_str,
                after_data=after_str,
                created_at=now_utc()
            )
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception as e:
            db.session.rollback()
            print(f"[HistoryService] Erreur log: {e}")
            return None

    @staticmethod
    def get_all(limit=100, database_id=None):
        query = History.query.order_by(History.created_at.desc())
        if database_id:
            query = query.filter_by(database_id=database_id)
        return query.limit(limit).all()
