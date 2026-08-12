"""
Service Database V2 - métadonnées enrichies, état, commentaires, audit, websocket
Conserve compatibilité V1
"""
import uuid as uuid_lib
from ..extensions import db
from ..models.database import Database
from ..utils.helpers import generate_key_identifier, now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_new_database, emit_modification, emit_suppression

class DatabaseService:

    @staticmethod
    def get_all(include_archived=True):
        query = Database.query
        if not include_archived:
            query = query.filter_by(status="ACTIVE")
        return query.order_by(Database.updated_at.desc()).all()

    @staticmethod
    def get_by_id(db_id):
        return Database.query.get(db_id)

    @staticmethod
    def get_by_key(key_identifier):
        return Database.query.filter_by(key_identifier=key_identifier).first()

    @staticmethod
    def create(name, description, creator_id, creator_name, comment="", ip_address=None):
        for _ in range(5):
            key = generate_key_identifier()
            if not Database.query.filter_by(key_identifier=key).first():
                break
        else:
            key = generate_key_identifier()

        database = Database(
            uuid=str(uuid_lib.uuid4()),
            name=name,
            description=description,
            creator_id=creator_id,
            key_identifier=key,
            comment=comment or "",
            status="ACTIVE",
            last_modified_by_id=creator_id,
            last_modified_by_name=creator_name,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        db.session.add(database)
        db.session.commit()

        # Historique V2 avec IP, before/after
        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a créé",
            element_type="base",
            element_name=name,
            description=f"Base {name} créée avec clé {key}",
            database_id=database.id,
            ip_address=ip_address,
            before=None,
            after=database.to_dict(include_key=True)
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="CREATION_BASE",
            element_type="base",
            element_name=name,
            description=f"Création base {name} ({database.id})",
            meta={"database_id": database.id, "key_identifier": key}
        )

        emit_new_database(database.to_dict(include_key=True), creator_name)

        return database

    @staticmethod
    def update(db_id, data, user_id, user_name, ip_address=None):
        database = Database.query.get(db_id)
        if not database:
            return None, "Base introuvable"

        if database.is_archived():
            return None, f"Base '{database.name}' archivée, modification impossible. Restaurez-la d'abord."

        before = database.to_dict(include_key=True)

        if 'name' in data and data['name']:
            database.name = data['name']
        if 'description' in data:
            database.description = data['description']
        if 'comment' in data:
            database.comment = data['comment']

        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()

        db.session.commit()

        after = database.to_dict(include_key=True)

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a modifié",
            element_type="base",
            element_name=database.name,
            description=f"Base {db_id} modifiée",
            database_id=database.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="MODIFICATION_BASE",
            element_type="base",
            element_name=database.name,
            description=f"Modification base {database.id}",
            meta={"database_id": database.id, "before": before, "after": after}
        )

        emit_modification("base", database.to_dict(), user_name)

        return database, None

    @staticmethod
    def delete(db_id, user_id, user_name, ip_address=None):
        database = Database.query.get(db_id)
        if not database:
            return False, "Base introuvable"

        if database.is_archived():
            return False, f"Base '{database.name}' archivée, suppression impossible. Restaurez-la d'abord."

        before = database.to_dict(include_key=True)

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a supprimé",
            element_type="base",
            element_name=database.name,
            description=f"Base {database.name} supprimée",
            database_id=database.id,
            ip_address=ip_address,
            before=before,
            after=None
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="SUPPRESSION_BASE",
            element_type="base",
            element_name=database.name,
            description=f"Suppression base {database.name} ({db_id})",
            meta={"database_id": db_id}
        )

        emit_suppression("base", database.name, db_id, user_name)

        db.session.delete(database)
        db.session.commit()
        return True, None

    @staticmethod
    def update_comment(db_id, comment, user_id, user_name, ip_address=None):
        database = Database.query.get(db_id)
        if not database:
            return None, "Base introuvable"
        if database.is_archived():
            return None, f"Base '{database.name}' archivée, modification commentaire impossible."

        before = {"comment": database.comment}
        database.comment = comment
        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()
        after = {"comment": comment}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a commenté",
            element_type="base",
            element_name=database.name,
            description=comment,
            database_id=database.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="COMMENTAIRE_BASE",
            element_type="base",
            element_name=database.name,
            description=comment,
            meta={"database_id": db_id}
        )

        emit_modification("base", database.to_dict(), user_name)

        return database, None

    @staticmethod
    def archive(db_id, user_id, user_name, ip_address=None):
        database = Database.query.get(db_id)
        if not database:
            return None, "Base introuvable"
        if database.is_archived():
            return None, "Base déjà archivée"

        before = {"status": database.status}
        database.status = "ARCHIVED"
        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()
        after = {"status": "ARCHIVED"}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a archivé",
            element_type="base",
            element_name=database.name,
            description=f"Base {database.name} archivée",
            database_id=database.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="ARCHIVAGE_BASE",
            element_type="base",
            element_name=database.name,
            meta={"database_id": db_id}
        )

        emit_modification("base", database.to_dict(), user_name)

        return database, None

    @staticmethod
    def restore(db_id, user_id, user_name, ip_address=None):
        database = Database.query.get(db_id)
        if not database:
            return None, "Base introuvable"
        if not database.is_archived():
            return None, "Base non archivée"

        before = {"status": database.status}
        database.status = "ACTIVE"
        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()
        after = {"status": "ACTIVE"}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a restauré",
            element_type="base",
            element_name=database.name,
            description=f"Base {database.name} restaurée",
            database_id=database.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="RESTAURATION_BASE",
            element_type="base",
            element_name=database.name,
            meta={"database_id": db_id}
        )

        emit_modification("base", database.to_dict(), user_name)

        return database, None

    @staticmethod
    def get_database_by_name(user_id, database_name):
        """Récupère une base de données par nom pour un utilisateur"""
        return Database.query.filter_by(
            name=database_name,
            creator_id=user_id,
            status="ACTIVE"
        ).first()
    
    @staticmethod
    def get_database_by_name_any_user(database_name):
        """Récupère une base de données par nom (sans filtre user_id) - pour admin"""
        return Database.query.filter_by(
            name=database_name,
            status="ACTIVE"
        ).first()
