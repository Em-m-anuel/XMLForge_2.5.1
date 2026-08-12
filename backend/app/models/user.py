"""
Modèle User - V4 avec admin, activation, last_login
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # V4 admin & activation
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relations - avec foreign_keys explicites pour éviter ambiguïté avec last_modified_by
    databases_created = db.relationship('Database', foreign_keys='Database.creator_id', backref='creator', lazy=True, cascade="all, delete-orphan")
    tables_created = db.relationship('Table', foreign_keys='Table.creator_id', backref='creator_user', lazy=True)
    columns_created = db.relationship('Column', foreign_keys='Column.creator_id', backref='creator_user', lazy=True)

    def to_dict(self, include_private=False):
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_admin": self.is_admin()
        }
        if include_private:
            data["password_hash"] = "***"
        return data

    def is_admin(self):
        # Seul nyx@xmlforge.io est admin (insensible casse)
        return self.email.lower() == "nyx@xmlforge.io"

    def is_archived(self):
        return not self.is_active
