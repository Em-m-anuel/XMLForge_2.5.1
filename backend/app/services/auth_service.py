"""
Service Auth - logique métier authentification V4 avec admin, activation, last_login
"""
from ..extensions import db, bcrypt
from ..models.user import User
from flask_jwt_extended import create_access_token
from ..utils.helpers import now_utc
from .audit_service import AuditService

class AuthService:

    @staticmethod
    def register(full_name, email, password, ip_address=None):
        if User.query.filter_by(email=email.lower()).first():
            AuditService.log(
                ip_address=ip_address,
                action="ERREUR_INSCRIPTION",
                element_type="auth",
                element_name=email,
                description="Email déjà utilisé"
            )
            return None, "Email déjà utilisé"

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            full_name=full_name,
            email=email.lower(),
            password_hash=pw_hash,
            created_at=now_utc(),
            updated_at=now_utc(),
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        AuditService.log(
            user_id=user.id,
            user_name=user.full_name,
            ip_address=ip_address,
            action="INSCRIPTION",
            element_type="auth",
            element_name=user.email,
            description=f"Inscription {user.email}",
            meta={"user_id": user.id}
        )

        return user, None

    @staticmethod
    def login(email, password, ip_address=None):
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            AuditService.log(
                ip_address=ip_address,
                action="ERREUR_CONNEXION",
                element_type="auth",
                element_name=email,
                description="Email introuvable"
            )
            return None, "Email ou mot de passe incorrect"
        if not user.is_active:
            AuditService.log(
                user_id=user.id,
                user_name=user.full_name,
                ip_address=ip_address,
                action="ERREUR_CONNEXION",
                element_type="auth",
                element_name=email,
                description="Compte désactivé"
            )
            return None, "Compte désactivé, contactez l'administrateur"
        if not bcrypt.check_password_hash(user.password_hash, password):
            AuditService.log(
                user_id=user.id,
                user_name=user.full_name,
                ip_address=ip_address,
                action="ERREUR_CONNEXION",
                element_type="auth",
                element_name=email,
                description="Mot de passe incorrect"
            )
            return None, "Email ou mot de passe incorrect"

        user.last_login = now_utc()
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))

        AuditService.log(
            user_id=user.id,
            user_name=user.full_name,
            ip_address=ip_address,
            action="CONNEXION",
            element_type="auth",
            element_name=user.email,
            description=f"Connexion {user.email}",
            meta={"user_id": user.id}
        )

        return {"user": user, "token": access_token}, None

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def verify_credentials(email, password):
        """Vérifie les identifiants pour connexion TCP/IP"""
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            return None
        if not user.is_active:
            return None
        if not bcrypt.check_password_hash(user.password_hash, password):
            return None
        return user
