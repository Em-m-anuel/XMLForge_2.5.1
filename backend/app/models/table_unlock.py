"""
Modèle TableUnlock - V4 déverrouillage personnel par utilisateur et session
Permet de savoir qu'un utilisateur a déverrouillé une table protégée
"""
from datetime import datetime, timedelta
from ..extensions import db

class TableUnlock(db.Model):
    __tablename__ = 'table_unlocks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    table_id = db.Column(db.Integer, db.ForeignKey('tables.id'), nullable=False, index=True)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    # Contrainte unique user + table
    __table_args__ = (
        db.UniqueConstraint('user_id', 'table_id', name='uq_unlock_user_table'),
    )

    user = db.relationship('User', backref=db.backref('unlocks', lazy=True, cascade="all, delete-orphan"))
    table = db.relationship('Table', backref=db.backref('unlocks', lazy=True, cascade="all, delete-orphan"))

    @staticmethod
    def default_expiry():
        return datetime.utcnow() + timedelta(hours=24)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "table_id": self.table_id,
            "unlocked_at": self.unlocked_at.isoformat() if self.unlocked_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired()
        }
