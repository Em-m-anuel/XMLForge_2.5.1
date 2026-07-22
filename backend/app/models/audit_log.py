"""
Modèle AuditLog V2 - audit indépendant de l'historique métier
Enregistre toutes les actions sensibles : connexion, déconnexion, création base, suppression, import XML, export SQL, conversion, unlock, erreurs
"""
import uuid as uuid_lib
from datetime import datetime
from ..extensions import db

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, default=lambda: str(uuid_lib.uuid4()), index=True, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # nullable pour erreurs avant auth
    user_name = db.Column(db.String(120), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    action = db.Column(db.String(100), nullable=False)  # ex: CONNEXION, DECONNEXION, CREATION_BASE, SUPPRESSION, IMPORT_XML, EXPORT_SQL, CONVERSION_XML, CONVERSION_SQL, UNLOCK_TABLE, ERREUR
    element_type = db.Column(db.String(50), nullable=True)  # base, table, colonne, auth, system
    element_name = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, default="")

    # Métadonnées additionnelles JSON (ex: database_id, table_id, etc.)
    meta_data = db.Column(db.Text, nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "ip_address": self.ip_address,
            "action": self.action,
            "element_type": self.element_type,
            "element_name": self.element_name,
            "description": self.description,
            "meta_data": self.meta_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.timestamp.isoformat() if self.timestamp else None,
        }
