"""
Modèle TcpCredential - Stocke les credentials TCP/IP par utilisateur
"""
from ..extensions import db
from datetime import datetime


class TcpCredential(db.Model):
    """Credentials TCP/IP pour un utilisateur"""
    
    __tablename__ = 'tcp_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    tcp_username = db.Column(db.String(120), nullable=False)  # Email utilisé pour TCP
    tcp_password = db.Column(db.String(255), nullable=False)  # Mot de passe TCP (hashé)
    tcp_host = db.Column(db.String(120), default='127.0.0.1')
    tcp_port = db.Column(db.Integer, default=3307)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relation avec User
    user = db.relationship('User', backref=db.backref('tcp_credential', uselist=False, lazy='joined'))
    
    def to_dict(self):
        """Convertit en dictionnaire (sans mot de passe)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tcp_username': self.tcp_username,
            'tcp_host': self.tcp_host,
            'tcp_port': self.tcp_port,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def to_dict_with_password(self):
        """Convertit en dictionnaire (avec mot de passe pour affichage temporaire)"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tcp_username': self.tcp_username,
            'tcp_password': self.tcp_password,
            'tcp_host': self.tcp_host,
            'tcp_port': self.tcp_port,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
