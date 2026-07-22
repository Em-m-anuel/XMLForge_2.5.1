"""
Modèle User
"""
from datetime import datetime
from ..extensions import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relations - avec foreign_keys explicites pour éviter ambiguïté avec last_modified_by
    databases_created = db.relationship('Database', foreign_keys='Database.creator_id', backref='creator', lazy=True, cascade="all, delete-orphan")
    tables_created = db.relationship('Table', foreign_keys='Table.creator_id', backref='creator_user', lazy=True)
    columns_created = db.relationship('Column', foreign_keys='Column.creator_id', backref='creator_user', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
