"""
Service Unlock - V4 déverrouillage personnel par utilisateur
"""
from datetime import datetime, timedelta
from ..extensions import db
from ..models.table import Table
from ..models.database import Database
from ..models.table_unlock import TableUnlock
from ..utils.helpers import now_utc

class UnlockService:

    @staticmethod
    def is_unlocked(user_id, table_id):
        unlock = TableUnlock.query.filter_by(user_id=user_id, table_id=table_id).first()
        if not unlock:
            return False
        if unlock.is_expired():
            # Supprimer expiré
            db.session.delete(unlock)
            db.session.commit()
            return False
        return True

    @staticmethod
    def unlock_table(user_id, table_id, provided_key):
        table = Table.query.get(table_id)
        if not table:
            return False, "Table introuvable"

        database = Database.query.get(table.database_id)
        if not database:
            return False, "Base introuvable"

        if not table.is_protected:
            return True, "Table non protégée, accès autorisé"

        valid_keys = []
        if table.file_identifier:
            valid_keys.append(table.file_identifier)
        if database.key_identifier:
            valid_keys.append(database.key_identifier)

        if provided_key not in valid_keys:
            return False, "Clé invalide"

        # Créer ou mettre à jour unlock
        existing = TableUnlock.query.filter_by(user_id=user_id, table_id=table_id).first()
        if existing:
            existing.unlocked_at = now_utc()
            existing.expires_at = datetime.utcnow() + timedelta(hours=24)
        else:
            unlock = TableUnlock(
                user_id=user_id,
                table_id=table_id,
                unlocked_at=now_utc(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )
            db.session.add(unlock)

        db.session.commit()
        return True, "Table déverrouillée pour votre session"

    @staticmethod
    def list_user_unlocks(user_id):
        unlocks = TableUnlock.query.filter_by(user_id=user_id).all()
        # Filtrer expirés
        valid = []
        for u in unlocks:
            if u.is_expired():
                db.session.delete(u)
            else:
                valid.append(u)
        db.session.commit()
        return valid

    @staticmethod
    def clear_user_unlocks(user_id):
        TableUnlock.query.filter_by(user_id=user_id).delete()
        db.session.commit()

    @staticmethod
    def clear_expired():
        now = datetime.utcnow()
        TableUnlock.query.filter(TableUnlock.expires_at < now).delete()
        db.session.commit()

    @staticmethod
    def check_protection(user_id, table, provided_key=None):
        """
        Vérifie si user a accès à table protégée
        Retourne (allowed, message)
        """
        if not table.is_protected:
            return True, None

        # Vérifier unlock personnel
        if user_id and UnlockService.is_unlocked(user_id, table.id):
            return True, None

        # Vérifier clé fournie
        if not provided_key:
            return False, f"Table '{table.name}' protégée, clé requise"

        database = Database.query.get(table.database_id)
        valid_keys = []
        if table.file_identifier:
            valid_keys.append(table.file_identifier)
        if database and database.key_identifier:
            valid_keys.append(database.key_identifier)

        if provided_key in valid_keys:
            return True, None

        return False, "Clé invalide pour table protégée"
