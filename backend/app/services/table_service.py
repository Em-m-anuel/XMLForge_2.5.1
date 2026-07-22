"""
Service Table V3 - XML source de vérité, file_identifier, protection renforcée
"""
import uuid as uuid_lib
from ..extensions import db
from ..models.table import Table
from ..models.database import Database
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_new_table, emit_modification, emit_suppression

class TableService:

    @staticmethod
    def get_by_database(database_id, include_archived=True):
        query = Table.query.filter_by(database_id=database_id)
        if not include_archived:
            query = query.filter_by(status="ACTIVE")
        return query.order_by(Table.created_at.asc()).all()

    @staticmethod
    def get_by_id(table_id):
        return Table.query.get(table_id)

    @staticmethod
    def _check_protection(table, provided_key):
        if not table.is_protected:
            return True, None
        if not provided_key:
            return False, f"Table '{table.name}' protégée. Clé_identifiant requise (file_identifier ou clé base)."
        database = Database.query.get(table.database_id)
        if not database:
            return False, "Base parente introuvable"

        # Clés valides : file_identifier de la table si présent, sinon clé base, mais on accepte les deux pour souplesse
        valid_keys = []
        if table.file_identifier:
            valid_keys.append(table.file_identifier)
        if database.key_identifier:
            valid_keys.append(database.key_identifier)

        if provided_key in valid_keys:
            return True, None
        return False, "Clé_identifiant invalide pour cette table (vérifiez file_identifier ou clé base)."

    @staticmethod
    def _check_archived(table):
        if table.is_archived():
            return False, f"Table '{table.name}' archivée, modification impossible. Restaurez-la d'abord."
        return True, None

    @staticmethod
    def create(name, description, database_id, creator_id, creator_name, is_protected=False, comment="", file_identifier=None, ip_address=None):
        database = Database.query.get(database_id)
        if not database:
            return None, "Base introuvable"
        if database.is_archived():
            return None, f"Base '{database.name}' archivée, création table impossible."

        if Table.query.filter_by(database_id=database_id, name=name).first():
            return None, f"Table '{name}' existe déjà dans cette base"

        # Si protégée et pas de file_identifier fourni, on génère ou on utilise clé base? On laisse vide, protection via clé base
        # Si file_identifier fourni, on le stocke

        table = Table(
            uuid=str(uuid_lib.uuid4()),
            name=name,
            description=description,
            database_id=database_id,
            creator_id=creator_id,
            is_protected=is_protected,
            file_identifier=file_identifier or None,
            comment=comment or "",
            status="ACTIVE",
            last_modified_by_id=creator_id,
            last_modified_by_name=creator_name,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        db.session.add(table)
        db.session.flush()

        database.last_modified_by_id = creator_id
        database.last_modified_by_name = creator_name
        database.updated_at = now_utc()
        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a créé",
            element_type="table",
            element_name=name,
            description=f"Table {name} créée dans base {database.name} (protégée={is_protected}, file_id={file_identifier})",
            database_id=database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=None,
            after=table.to_dict()
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="CREATION_TABLE",
            element_type="table",
            element_name=name,
            description=f"Création table {name} dans base {database.name}",
            meta={"table_id": table.id, "database_id": database_id, "protected": is_protected, "file_identifier": file_identifier}
        )

        emit_new_table(table.to_dict(), creator_name)

        return table, None

    @staticmethod
    def update(table_id, data, user_id, user_name, provided_key=None, ip_address=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        allowed, msg = TableService._check_archived(table)
        if not allowed:
            return None, msg

        allowed, msg = TableService._check_protection(table, provided_key)
        if not allowed:
            return None, msg

        before = table.to_dict()

        if 'name' in data and data['name']:
            if data['name'] != table.name:
                if Table.query.filter_by(database_id=table.database_id, name=data['name']).first():
                    return None, f"Table '{data['name']}' existe déjà"
            table.name = data['name']
        if 'description' in data:
            table.description = data['description']
        if 'is_protected' in data:
            table.is_protected = bool(data['is_protected'])
        if 'file_identifier' in data:
            # Permet modifier l'identifiant du fichier
            table.file_identifier = data['file_identifier'] or None
        # Alias protected file_identifier from XML spec
        if 'protected' in data:
            table.is_protected = str(data['protected']).lower() in ('true','1','yes')
        if 'archived' in data:
            # archived bool -> status
            table.status = "ARCHIVED" if str(data['archived']).lower() in ('true','1','yes') else "ACTIVE"
        if 'comment' in data:
            table.comment = data['comment']
        if 'status' in data:
            # Respect spec ACTIVE/ARCHIVED
            if data['status'] in ('ACTIVE','ARCHIVED'):
                table.status = data['status']

        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()
        db.session.commit()

        after = table.to_dict()

        database = Database.query.get(table.database_id)
        if database:
            database.last_modified_by_id = user_id
            database.last_modified_by_name = user_name
            database.updated_at = now_utc()
            db.session.commit()

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a modifié",
            element_type="table",
            element_name=table.name,
            description=f"Table {table_id} modifiée",
            database_id=table.database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="MODIFICATION_TABLE",
            element_type="table",
            element_name=table.name,
            meta={"table_id": table_id, "before": before, "after": after}
        )

        emit_modification("table", table.to_dict(), user_name)

        return table, None

    @staticmethod
    def delete(table_id, user_id, user_name, provided_key=None, ip_address=None):
        table = Table.query.get(table_id)
        if not table:
            return False, "Table introuvable"

        allowed, msg = TableService._check_archived(table)
        if not allowed:
            return False, msg

        allowed, msg = TableService._check_protection(table, provided_key)
        if not allowed:
            return False, msg

        before = table.to_dict()

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a supprimé",
            element_type="table",
            element_name=table.name,
            description=f"Table {table.name} supprimée",
            database_id=table.database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=before,
            after=None
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="SUPPRESSION_TABLE",
            element_type="table",
            element_name=table.name,
            meta={"table_id": table_id, "database_id": table.database_id}
        )

        emit_suppression("table", table.name, table.database_id, user_name)

        db.session.delete(table)
        db.session.commit()

        database = Database.query.get(table.database_id)
        if database:
            database.last_modified_by_id = user_id
            database.last_modified_by_name = user_name
            database.updated_at = now_utc()
            db.session.commit()

        return True, None

    @staticmethod
    def update_comment(table_id, comment, user_id, user_name, ip_address=None, provided_key=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        allowed, msg = TableService._check_archived(table)
        if not allowed:
            return None, msg

        allowed, msg = TableService._check_protection(table, provided_key)
        if not allowed:
            return None, msg

        before = {"comment": table.comment}
        table.comment = comment
        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()
        db.session.commit()
        after = {"comment": comment}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a commenté",
            element_type="table",
            element_name=table.name,
            description=comment,
            database_id=table.database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="COMMENTAIRE_TABLE",
            element_type="table",
            element_name=table.name,
            description=comment,
            meta={"table_id": table_id}
        )

        emit_modification("table", table.to_dict(), user_name)

        return table, None

    @staticmethod
    def archive(table_id, user_id, user_name, ip_address=None, provided_key=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        allowed, msg = TableService._check_protection(table, provided_key)
        if not allowed:
            return None, msg

        if table.is_archived():
            return None, "Table déjà archivée"

        before = {"status": table.status}
        table.status = "ARCHIVED"
        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()
        db.session.commit()
        after = {"status": "ARCHIVED"}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a archivé",
            element_type="table",
            element_name=table.name,
            description=f"Table {table.name} archivée",
            database_id=table.database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="ARCHIVAGE_TABLE",
            element_type="table",
            element_name=table.name,
            meta={"table_id": table_id}
        )

        emit_modification("table", table.to_dict(), user_name)

        return table, None

    @staticmethod
    def restore(table_id, user_id, user_name, ip_address=None, provided_key=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        allowed, msg = TableService._check_protection(table, provided_key)
        if not allowed:
            return None, msg

        if not table.is_archived():
            return None, "Table non archivée"

        before = {"status": table.status}
        table.status = "ACTIVE"
        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()
        db.session.commit()
        after = {"status": "ACTIVE"}

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a restauré",
            element_type="table",
            element_name=table.name,
            description=f"Table {table.name} restaurée",
            database_id=table.database_id,
            table_id=table.id,
            ip_address=ip_address,
            before=before,
            after=after
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="RESTAURATION_TABLE",
            element_type="table",
            element_name=table.name,
            meta={"table_id": table_id}
        )

        emit_modification("table", table.to_dict(), user_name)

        return table, None

    @staticmethod
    def unlock(table_id, key_identifier):
        table = Table.query.get(table_id)
        if not table:
            return False, "Table introuvable"
        if not table.is_protected:
            return True, "Table non protégée, accès autorisé"

        database = Database.query.get(table.database_id)
        if not database:
            return False, "Base introuvable"

        valid_keys = []
        if table.file_identifier:
            valid_keys.append(table.file_identifier)
        if database.key_identifier:
            valid_keys.append(database.key_identifier)

        if key_identifier in valid_keys:
            return True, "Clé valide, accès autorisé"
        else:
            return False, "Clé invalide – vérifiez file_identifier ou clé base"
