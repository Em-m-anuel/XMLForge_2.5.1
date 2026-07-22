"""
Modèle History V2 - enrichi avec UUID, IP, before/after
Conserve compatibilité V1
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db

class History(db.Model):
    __tablename__ = 'history'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_name = db.Column(db.String(120), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # a créé, a ajouté, etc.
    element_type = db.Column(db.String(50), nullable=False)  # base, table, colonne
    element_name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")

    # V2 enrichissements
    ip_address = db.Column(db.String(45), nullable=True)
    before_data = db.Column(db.Text, nullable=True)  # JSON string
    after_data = db.Column(db.Text, nullable=True)   # JSON string

    database_id = db.Column(db.Integer, db.ForeignKey('databases.id'), nullable=True)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action_type": self.action_type,
            "element_type": self.element_type,
            "element_name": self.element_name,
            "description": self.description,
            "ip_address": self.ip_address,
            "before": self.before_data,
            "after": self.after_data,
            "database_id": self.database_id,
            "table_id": self.table_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "date": self.created_at.isoformat() if self.created_at else None,  # alias pour compat frontend
        }
