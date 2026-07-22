"""
Modèle Database V2 - enrichi métadonnées
Conserve compatibilité V1
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db

class Database(db.Model):
    __tablename__ = 'databases'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # V2 métadonnées
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_modified_by_name = db.Column(db.String(120), nullable=True)
    comment = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)  # ACTIVE / ARCHIVED

    key_identifier = db.Column(db.String(32), unique=True, nullable=False, index=True)  # XML-XXXX-XXXX-XXXX

    # Relations
    tables = db.relationship('Table', backref='database', lazy=True, cascade="all, delete-orphan", foreign_keys='Table.database_id')
    last_modifier = db.relationship('User', foreign_keys=[last_modified_by_id], backref='databases_modified')

    def to_dict(self, include_key=False):
        data = {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "creator_id": self.creator_id,
            "creator_name": self.creator.full_name if hasattr(self, 'creator') and self.creator else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name,
            "comment": self.comment or "",
            "status": self.status,
            "tables_count": len(self.tables) if self.tables is not None else 0
        }
        if include_key:
            data["key_identifier"] = self.key_identifier
        return data

    def is_archived(self):
        return self.status == "ARCHIVED"
