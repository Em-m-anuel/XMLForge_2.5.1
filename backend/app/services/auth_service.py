"""Service Auth — logique métier authentification V4/V6E.

La persistance du plan de contrôle (users, roles) passe par la couche
d'adaptation ``control_plane`` (backend XML, unique). Les mots de passe restent
des hashes bcrypt ; le secret JWT reste en configuration.
"""
from ..control_plane import get_backend
from ..extensions import bcrypt
from flask_jwt_extended import create_access_token
from ..utils.helpers import now_utc
from .audit_service import AuditService


class AuthService:

    @staticmethod
    def register(full_name, email, password, ip_address=None):
        backend = get_backend()
        if backend.get_user_by_email(email.lower()):
            AuditService.log(
                ip_address=ip_address,
                action="ERREUR_INSCRIPTION",
                element_type="auth",
                element_name=email,
                description="Email déjà utilisé"
            )
            return None, "Email déjà utilisé"

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        role = backend.get_role_by_name('user')
        if role is None:
            role = backend.ensure_role('user', 'Utilisateur XMLForge')
        user = backend.insert_user(
            full_name=full_name,
            email=email.lower(),
            password_hash=pw_hash,
            role_id=role.id,
            is_active=True,
            token_version=1,
            created_at=now_utc(),
            updated_at=now_utc(),
        )

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
        backend = get_backend()
        user = backend.get_user_by_email(email.lower())
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

        backend.update_user_fields(user.id, {"last_login": now_utc()})

        # Une reconnexion crée une nouvelle session : les déverrouillages de la
        # session précédente ne doivent pas survivre.
        from .unlock_service import UnlockService
        UnlockService.clear_user_unlocks(user.id)

        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={"token_version": user.token_version or 1},
        )

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
        return get_backend().get_user(user_id)

    @staticmethod
    def verify_password(user, password):
        return bool(user and bcrypt.check_password_hash(user.password_hash, password))

    @staticmethod
    def verify_credentials(email, password):
        """Compatibilité REST/outils. TCP utilise TcpCredentialService."""
        user = get_backend().get_user_by_email(email.lower())
        if not user:
            return None
        if not user.is_active:
            return None
        if not bcrypt.check_password_hash(user.password_hash, password):
            return None
        return user
