"""
Modèle TableRow - V4 données d'une table (enregistrements)
Stocke les lignes d'une table logique XMLForge, pas MySQL réelle
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db
import json

class TableRow(db.Model):
    __tablename__ = 'table_rows'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False, index=True)
    # data stocké en JSON string: {"id": "1", "nom": "Jean", "email": "jean@test.com"}
    data_json = db.Column(db.Text, nullable=False, default="{}")

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_modified_by_name = db.Column(db.String(120), nullable=True)

    table = db.relationship('Table', backref=db.backref('rows', lazy=True, cascade="all, delete-orphan"))
    creator = db.relationship('User', foreign_keys=[creator_id], backref='rows_created')
    last_modifier = db.relationship('User', foreign_keys=[last_modified_by_id], backref='rows_modified')

    def get_data(self):
        try:
            return json.loads(self.data_json) if self.data_json else {}
        except:
            return {}

    def set_data(self, data_dict):
        self.data_json = json.dumps(data_dict, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "table_id": self.table_id,
            "data": self.get_data(),
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name
        }
