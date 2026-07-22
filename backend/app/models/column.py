"""
Modèle Column V2 - enrichi métadonnées
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db

class Column(db.Model):
    __tablename__ = 'columns'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="VARCHAR")
    length = db.Column(db.String(20), default="-")
    nullable = db.Column(db.Boolean, default=True, nullable=False)
    primary_key = db.Column(db.Boolean, default=False, nullable=False)
    foreign_key = db.Column(db.Boolean, default=False, nullable=False)
    unique = db.Column(db.Boolean, default=False, nullable=False)
    auto_increment = db.Column(db.Boolean, default=False, nullable=False)
    default_value = db.Column(db.String(255), nullable=True)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # V2
    last_modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_modified_by_name = db.Column(db.String(120), nullable=True)
    comment = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="ACTIVE", nullable=False)

    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False, index=True)

    last_modifier = db.relationship('User', foreign_keys=[last_modified_by_id], backref='columns_modified')

    __table_args__ = (
        db.UniqueConstraint('table_id', 'name', name='uq_column_table_name'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "name": self.name,
            "type": self.type,
            "length": self.length,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
            "foreign_key": self.foreign_key,
            "unique": self.unique,
            "auto_increment": self.auto_increment,
            "default": self.default_value,
            "creator_id": self.creator_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_modified_by_id": self.last_modified_by_id,
            "last_modified_by": self.last_modified_by_name,
            "comment": self.comment or "",
            "status": self.status,
            "table_id": self.table_id
        }

    def is_archived(self):
        return self.status == "ARCHIVED"
