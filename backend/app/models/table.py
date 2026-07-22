"""
Modèle Table V2 - enrichi métadonnées + file_identifier pour protection
XML devient source de vérité
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db

class Table(db.Model):
    __tablename__ = 'tables'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    database_id = db.Column(db.Integer, db.ForeignKey('databases.id'), nullable=False, index=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # V2 métadonnées
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_modified_by_name = db.Column(db.String(120), nullable=True)
    comment = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)  # ACTIVE / ARCHIVED

    is_protected = db.Column(db.Boolean, default=False, nullable=False)
    file_identifier = db.Column(db.String(64), nullable=True)  # XML-XXXX-XXXX-XXXX ou custom, pour protection

    # Relations
    columns = db.relationship('Column', backref='table', lazy=True, cascade="all, delete-orphan")
    last_modifier = db.relationship('User', foreign_keys=[last_modified_by_id], backref='tables_modified')

    __table_args__ = (
        db.UniqueConstraint('database_id', 'name', name='uq_table_db_name'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "description": self.description,
            "database_id": self.database_id,
            "creator_id": self.creator_id,
            "creator_name": self.creator_user.full_name if hasattr(self, 'creator_user') and self.creator_user else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name,
            "comment": self.comment or "",
            "status": self.status,
            "is_protected": self.is_protected,
            "file_identifier": self.file_identifier or "",
            "protected": self.is_protected,  # alias pour compat XML
            "archived": self.is_archived(),  # bool alias
            "columns_count": len(self.columns) if self.columns is not None else 0
        }

    def is_archived(self):
        return self.status == "ARCHIVED"

    def get_required_key(self):
        """Retourne la clé nécessaire pour déverrouiller : file_identifier si présent, sinon None (on utilisera clé base)"""
        return self.file_identifier or None
