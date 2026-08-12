"""
Service TcpCredential - Gestion des credentials TCP/IP par utilisateur
"""
import secrets
from ..extensions import db, bcrypt
from ..models.tcp_credential import TcpCredential
from ..models.user import User
from ..utils.helpers import now_utc


class TcpCredentialService:
    
    @staticmethod
    def get_by_user_id(user_id):
        """Récupère les credentials TCP d'un utilisateur"""
        return TcpCredential.query.filter_by(user_id=user_id).first()
    
    @staticmethod
    def create_for_user(user_id, tcp_username=None, tcp_password=None, tcp_host='127.0.0.1', tcp_port=3307):
        """Crée des credentials TCP pour un utilisateur"""
        # Si username/password non fournis, utiliser l'email et générer un mot de passe
        user = User.query.get(user_id)
        if not user:
            return None, "Utilisateur introuvable"
        
        if not tcp_username:
            tcp_username = user.email
        
        if not tcp_password:
            # Générer un mot de passe aléatoire
            tcp_password = secrets.token_urlsafe(16)
        
        # Vérifier si les credentials existent déjà
        existing = TcpCredential.query.filter_by(user_id=user_id).first()
        if existing:
            return None, "Credentials TCP existent déjà pour cet utilisateur"
        
        # Hasher le mot de passe
        password_hash = bcrypt.generate_password_hash(tcp_password).decode('utf-8')
        
        credential = TcpCredential(
            user_id=user_id,
            tcp_username=tcp_username,
            tcp_password=password_hash,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
            is_active=True,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        
        db.session.add(credential)
        db.session.commit()
        
        # Retourner avec le mot de passe en clair (pour affichage unique)
        return {
            'credential': credential.to_dict(),
            'plain_password': tcp_password
        }, None
    
    @staticmethod
    def update_for_user(user_id, tcp_username=None, tcp_password=None, tcp_host=None, tcp_port=None):
        """Met à jour les credentials TCP d'un utilisateur"""
        credential = TcpCredential.query.filter_by(user_id=user_id).first()
        if not credential:
            return None, "Credentials TCP introuvables"
        
        if tcp_username:
            credential.tcp_username = tcp_username
        
        if tcp_password:
            credential.tcp_password = bcrypt.generate_password_hash(tcp_password).decode('utf-8')
        
        if tcp_host:
            credential.tcp_host = tcp_host
        
        if tcp_port:
            credential.tcp_port = tcp_port
        
        credential.updated_at = now_utc()
        db.session.commit()
        
        return credential.to_dict(), None
    
    @staticmethod
    def regenerate_password(user_id):
        """Régénère le mot de passe TCP d'un utilisateur"""
        credential = TcpCredential.query.filter_by(user_id=user_id).first()
        if not credential:
            return None, "Credentials TCP introuvables"
        
        # Générer nouveau mot de passe
        new_password = secrets.token_urlsafe(16)
        credential.tcp_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        credential.updated_at = now_utc()
        db.session.commit()
        
        return {
            'credential': credential.to_dict(),
            'plain_password': new_password
        }, None
    
    @staticmethod
    def delete_for_user(user_id):
        """Supprime les credentials TCP d'un utilisateur"""
        credential = TcpCredential.query.filter_by(user_id=user_id).first()
        if not credential:
            return False, "Credentials TCP introuvables"
        
        db.session.delete(credential)
        db.session.commit()
        return True, None
    
    @staticmethod
    def verify_tcp_password(user_id, plain_password):
        """Vérifie le mot de passe TCP"""
        credential = TcpCredential.query.filter_by(user_id=user_id).first()
        if not credential:
            return False
        
        return bcrypt.check_password_hash(credential.tcp_password, plain_password)
