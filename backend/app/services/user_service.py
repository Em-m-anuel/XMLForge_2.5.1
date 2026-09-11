"""Service Users — V4/V6E admin only.

Les lectures/écritures des utilisateurs et rôles passent par la couche
d'adaptation ``control_plane`` (backend selon ``CONTROL_BACKEND``).
"""
from ..control_plane import get_backend
from ..extensions import bcrypt
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification


class UserService:

    @staticmethod
    def get_all(search=None, include_inactive=True):
        return get_backend().list_users(search=search, include_inactive=include_inactive)

    @staticmethod
    def get_by_id(user_id):
        return get_backend().get_user(user_id)

    @staticmethod
    def get_by_email(email):
        return get_backend().get_user_by_email(email)

    @staticmethod
    def create(full_name, email, password, creator_id=None, creator_name=None,
               is_active=True, role_name="user", ip_address=None):
        backend = get_backend()
        if backend.get_user_by_email(email.lower()):
            return None, "Email déjà utilisé"

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        role = backend.get_role_by_name(str(role_name or 'user').lower())
        if role is None:
            return None, "Rôle introuvable"
        user = backend.insert_user(
            full_name=full_name,
            email=email.lower(),
            password_hash=pw_hash,
            role_id=role.id,
            is_active=is_active,
            token_version=1,
            created_at=now_utc(),
            updated_at=now_utc(),
        )

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a créé",
            element_type="utilisateur",
            element_name=user.email,
            description=f"Utilisateur {user.email} créé",
            ip_address=ip_address,
            before=None,
            after=user.to_dict()
        )
        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="CREATION_UTILISATEUR",
            element_type="utilisateur",
            element_name=user.email,
            description=f"Création utilisateur {user.email}",
            meta={"user_id": user.id}
        )
        emit_modification("utilisateur", user.to_dict(), creator_name or "admin")

        return user, None

    @staticmethod
    def update(user_id, data, updater_id=None, updater_name=None, ip_address=None):
        backend = get_backend()
        user = backend.get_user(user_id)
        if user is None:
            return None, "Utilisateur introuvable"

        before = user.to_dict()
        changes = {}

        if 'full_name' in data and data['full_name']:
            changes['full_name'] = data['full_name']
        if 'email' in data and data['email']:
            existing = backend.get_user_by_email(data['email'].lower())
            if existing is not None and existing.id != user_id:
                return None, "Email déjà utilisé"
            changes['email'] = data['email'].lower()
        if 'is_active' in data:
            if user.is_admin() and not bool(data['is_active']):
                admin_count = backend.count_active_admins()
                if admin_count <= 1:
                    return None, "Impossible de désactiver le dernier administrateur"
            new_active = bool(data['is_active'])
            if user.is_active != new_active:
                changes['token_version'] = (user.token_version or 1) + 1
            changes['is_active'] = new_active
        if 'role' in data and data['role']:
            role = backend.get_role_by_name(str(data['role']).lower())
            if role is None:
                return None, "Rôle introuvable"
            if user.is_admin() and role.name != 'admin':
                admin_count = backend.count_active_admins()
                if admin_count <= 1:
                    return None, "Impossible de retirer le rôle du dernier administrateur"
            changes['role_id'] = role.id

        changes['updated_at'] = now_utc()
        backend.update_user_fields(user_id, changes)
        user = backend.get_user(user_id)
        after = user.to_dict()

        HistoryService.log(
            user_id=updater_id,
            user_name=updater_name,
            action_type="a modifié",
            element_type="utilisateur",
            element_name=user.email,
            description=f"Utilisateur {user.email} modifié",
            ip_address=ip_address,
            before=before,
            after=after
        )
        AuditService.log(
            user_id=updater_id,
            user_name=updater_name,
            ip_address=ip_address,
            action="MODIFICATION_UTILISATEUR",
            element_type="utilisateur",
            element_name=user.email,
            meta={"user_id": user_id, "before": before, "after": after}
        )
        emit_modification("utilisateur", user.to_dict(), updater_name or "admin")

        return user, None

    @staticmethod
    def delete(user_id, deleter_id=None, deleter_name=None, ip_address=None):
        backend = get_backend()
        user = backend.get_user(user_id)
        if user is None:
            return False, "Utilisateur introuvable"

        if user.is_admin():
            admin_count = backend.count_active_admins()
            if admin_count <= 1:
                return False, "Impossible de supprimer le dernier administrateur"

        if deleter_id and int(deleter_id) == int(user_id):
            return False, "Vous ne pouvez pas supprimer votre propre compte"

        owned = [d for d in backend.list_databases()
                 if (getattr(d, "owner_id", None) or getattr(d, "creator_id", None)) == user_id]
        if owned:
            return False, "Transférez ou supprimez les bases possédées avant de supprimer cet utilisateur"

        before = user.to_dict()

        # Supprimer aussi les unlocks (volatils).
        from .unlock_service import UnlockService
        UnlockService.clear_user_unlocks(user_id)

        try:
            backend.delete_user(user_id)
        except Exception as exc:
            return False, str(exc)

        HistoryService.log(
            user_id=deleter_id,
            user_name=deleter_name,
            action_type="a supprimé",
            element_type="utilisateur",
            element_name=before['email'],
            description=f"Utilisateur {before['email']} supprimé",
            ip_address=ip_address,
            before=before,
            after=None
        )
        AuditService.log(
            user_id=deleter_id,
            user_name=deleter_name,
            ip_address=ip_address,
            action="SUPPRESSION_UTILISATEUR",
            element_type="utilisateur",
            element_name=before['email'],
            meta={"deleted_user_id": user_id}
        )

        return True, None

    @staticmethod
    def reset_password(user_id, new_password, updater_id=None, updater_name=None, ip_address=None):
        backend = get_backend()
        user = backend.get_user(user_id)
        if user is None:
            return None, "Utilisateur introuvable"

        pw_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        backend.update_user_fields(user_id, {
            "password_hash": pw_hash,
            "token_version": (user.token_version or 1) + 1,
            "updated_at": now_utc(),
        })
        from .unlock_service import UnlockService
        UnlockService.clear_user_unlocks(user_id)
        user = backend.get_user(user_id)

        AuditService.log(
            user_id=updater_id,
            user_name=updater_name,
            ip_address=ip_address,
            action="RESET_PASSWORD",
            element_type="utilisateur",
            element_name=user.email,
            meta={"user_id": user_id}
        )

        return user, None

    @staticmethod
    def toggle_active(user_id, updater_id=None, updater_name=None, ip_address=None):
        backend = get_backend()
        user = backend.get_user(user_id)
        if user is None:
            return None, "Utilisateur introuvable"

        if user.is_admin() and user.is_active:
            admin_count = backend.count_active_admins()
            if admin_count <= 1:
                return None, "Impossible de désactiver le dernier administrateur"

        backend.update_user_fields(user_id, {
            "is_active": not user.is_active,
            "token_version": (user.token_version or 1) + 1,
            "updated_at": now_utc(),
        })
        user = backend.get_user(user_id)

        action = "ACTIVATION_UTILISATEUR" if user.is_active else "DESACTIVATION_UTILISATEUR"
        AuditService.log(
            user_id=updater_id,
            user_name=updater_name,
            ip_address=ip_address,
            action=action,
            element_type="utilisateur",
            element_name=user.email,
            meta={"user_id": user_id, "is_active": user.is_active}
        )

        return user, None
