"""
Service Users - V4 admin only
"""
from ..extensions import db, bcrypt
from ..models.user import User
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification
import uuid as uuid_lib

class UserService:

    @staticmethod
    def get_all(search=None, include_inactive=True):
        query = User.query
        if search:
            search_lower = f"%{search.lower()}%"
            query = query.filter(
                db.or_(
                    User.email.ilike(search_lower),
                    User.full_name.ilike(search_lower)
                )
            )
        if not include_inactive:
            query = query.filter_by(is_active=True)
        return query.order_by(User.created_at.desc()).all()

    @staticmethod
    def get_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def get_by_email(email):
        return User.query.filter_by(email=email.lower()).first()

    @staticmethod
    def create(full_name, email, password, creator_id=None, creator_name=None, is_active=True, ip_address=None):
        if User.query.filter_by(email=email.lower()).first():
            return None, "Email déjà utilisé"

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            full_name=full_name,
            email=email.lower(),
            password_hash=pw_hash,
            created_at=now_utc(),
            updated_at=now_utc(),
            is_active=is_active
        )
        db.session.add(user)
        db.session.commit()

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
        user = User.query.get(user_id)
        if not user:
            return None, "Utilisateur introuvable"

        before = user.to_dict()

        if 'full_name' in data and data['full_name']:
            user.full_name = data['full_name']
        if 'email' in data and data['email']:
            # Vérifier unicité
            existing = User.query.filter_by(email=data['email'].lower()).first()
            if existing and existing.id != user_id:
                return None, "Email déjà utilisé"
            user.email = data['email'].lower()
        if 'is_active' in data:
            user.is_active = bool(data['is_active'])

        user.updated_at = now_utc()
        db.session.commit()

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
        user = User.query.get(user_id)
        if not user:
            return False, "Utilisateur introuvable"

        # Empêcher suppression de l'admin principal
        if user.email.lower() == "nyx@xmlforge.io":
            return False, "Impossible de supprimer l'administrateur principal"

        if deleter_id and int(deleter_id) == int(user_id):
            return False, "Vous ne pouvez pas supprimer votre propre compte"

        before = user.to_dict()

        # Supprimer aussi les unlocks
        from ..models.table_unlock import TableUnlock
        TableUnlock.query.filter_by(user_id=user_id).delete()

        db.session.delete(user)
        db.session.commit()

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
        user = User.query.get(user_id)
        if not user:
            return None, "Utilisateur introuvable"

        pw_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.password_hash = pw_hash
        user.updated_at = now_utc()
        db.session.commit()

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
        user = User.query.get(user_id)
        if not user:
            return None, "Utilisateur introuvable"

        if user.email.lower() == "nyx@xmlforge.io":
            return None, "Impossible de désactiver l'administrateur principal"

        user.is_active = not user.is_active
        user.updated_at = now_utc()
        db.session.commit()

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
