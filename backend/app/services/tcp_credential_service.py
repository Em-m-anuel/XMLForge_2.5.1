"""Service TcpCredential - gestion des credentials TCP/IP (via Control Plane)."""
import secrets
from ..control_plane import get_backend
from ..extensions import bcrypt
from ..utils.helpers import now_utc


class TcpCredentialService:

    @staticmethod
    def get_by_user_id(user_id):
        return get_backend().get_tcp_credential_by_user(user_id)

    @staticmethod
    def create_for_user(user_id, tcp_username=None, tcp_password=None,
                        tcp_host='127.0.0.1', tcp_port=3307):
        backend = get_backend()
        user = backend.get_user(user_id)
        if not user:
            return None, "Utilisateur introuvable"

        if not tcp_username:
            tcp_username = user.email
        if not tcp_password:
            tcp_password = secrets.token_urlsafe(16)

        existing = backend.get_tcp_credential_by_user(user_id)
        username_owner = backend.get_tcp_credential_by_username(tcp_username)
        if username_owner and username_owner.user_id != int(user_id):
            return None, "Username TCP déjà utilisé"
        if existing:
            return None, "Credentials TCP existent déjà pour cet utilisateur"

        password_hash = bcrypt.generate_password_hash(tcp_password).decode('utf-8')
        credential = backend.insert_tcp_credential(
            user_id=user_id, tcp_username=tcp_username, tcp_password_hash=password_hash,
            tcp_host=tcp_host, tcp_port=tcp_port, is_active=True,
            created_at=now_utc(), updated_at=now_utc(),
        )
        return {
            'credential': credential.to_dict(),
            'plain_password': tcp_password
        }, None

    @staticmethod
    def update_for_user(user_id, tcp_username=None, tcp_password=None,
                        tcp_host=None, tcp_port=None):
        backend = get_backend()
        credential = backend.get_tcp_credential_by_user(user_id)
        if not credential:
            return None, "Credentials TCP introuvables"

        changes = {}
        if tcp_username:
            owner = backend.get_tcp_credential_by_username(tcp_username)
            if owner and owner.user_id != int(user_id):
                return None, "Username TCP déjà utilisé"
            changes['tcp_username'] = tcp_username
        if tcp_password:
            changes['tcp_password'] = bcrypt.generate_password_hash(tcp_password).decode('utf-8')
        if tcp_host:
            changes['tcp_host'] = tcp_host
        if tcp_port:
            changes['tcp_port'] = tcp_port
        changes['updated_at'] = now_utc()
        credential = backend.update_tcp_credential_fields(credential.id, changes)
        return credential.to_dict(), None

    @staticmethod
    def regenerate_password(user_id):
        backend = get_backend()
        credential = backend.get_tcp_credential_by_user(user_id)
        if not credential:
            return None, "Credentials TCP introuvables"

        new_password = secrets.token_urlsafe(16)
        backend.update_tcp_credential_fields(credential.id, {
            'tcp_password': bcrypt.generate_password_hash(new_password).decode('utf-8'),
            'updated_at': now_utc(),
        })
        credential = backend.get_tcp_credential_by_user(user_id)
        return {
            'credential': credential.to_dict(),
            'plain_password': new_password
        }, None

    @staticmethod
    def delete_for_user(user_id):
        backend = get_backend()
        credential = backend.get_tcp_credential_by_user(user_id)
        if not credential:
            return False, "Credentials TCP introuvables"
        backend.delete_tcp_credential(credential.id)
        return True, None

    @staticmethod
    def authenticate(tcp_username, plain_password):
        """Retourne l'utilisateur actif lié à des credentials TCP actifs."""
        backend = get_backend()
        credential = backend.get_tcp_credential_by_username(tcp_username)
        if not credential or not credential.is_active:
            return None
        user = backend.get_user(credential.user_id)
        if not user or not user.is_active:
            return None
        if not bcrypt.check_password_hash(credential.tcp_password, plain_password):
            return None
        return user

    @staticmethod
    def verify_tcp_password(user_id, plain_password):
        credential = get_backend().get_tcp_credential_by_user(user_id)
        if not credential:
            return False
        return bcrypt.check_password_hash(credential.tcp_password, plain_password)
