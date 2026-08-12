"""
Service Row - V4 gestion des données d'une table (enregistrements)
"""
from ..extensions import db
from ..models.table import Table
from ..models.table_row import TableRow
from ..models.database import Database
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification
import uuid as uuid_lib
import json

class RowService:

    @staticmethod
    def _check_table_access(table_id, user_id=None, provided_key=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"
        if table.is_archived():
            return None, f"Table '{table.name}' archivée, modification impossible"
        database = Database.query.get(table.database_id)
        if database and database.is_archived():
            return None, f"Base '{database.name}' archivée, modification impossible"

        # Vérifier protection avec unlocks personnels
        if table.is_protected:
            from ..models.table_unlock import TableUnlock
            if user_id:
                unlock = TableUnlock.query.filter_by(user_id=user_id, table_id=table_id).first()
                if unlock and not unlock.is_expired():
                    return table, None
            # Sinon vérifier clé fournie
            valid_keys = []
            if table.file_identifier:
                valid_keys.append(table.file_identifier)
            if database and database.key_identifier:
                valid_keys.append(database.key_identifier)
            if valid_keys:
                if not provided_key:
                    return None, f"Table '{table.name}' protégée, clé requise"
                if provided_key not in valid_keys:
                    return None, "Clé invalide pour table protégée"

        return table, None

    @staticmethod
    def get_by_table(table_id, limit=100, offset=0):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"
        query = TableRow.query.filter_by(table_id=table_id).order_by(TableRow.created_at.asc())
        total = query.count()
        rows = query.offset(offset).limit(min(limit, 500)).all()
        return {"rows": [r.to_dict() for r in rows], "total": total, "table": table.to_dict()}, None

    @staticmethod
    def create(table_id, data_dict, creator_id=None, creator_name=None, ip_address=None, provided_key=None):
        table, err = RowService._check_table_access(table_id, user_id=creator_id, provided_key=provided_key)
        if err:
            return None, err

        # Validation basique: data_dict doit être dict
        if not isinstance(data_dict, dict):
            return None, "Données invalides, dict attendu"

        row = TableRow(
            uuid=str(uuid_lib.uuid4()),
            table_id=table_id,
            data_json=json.dumps(data_dict, ensure_ascii=False),
            creator_id=creator_id,
            last_modified_by_id=creator_id,
            last_modified_by_name=creator_name,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        db.session.add(row)
        db.session.commit()

        table.last_modified_by_id = creator_id
        table.last_modified_by_name = creator_name
        table.updated_at = now_utc()
        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a créé",
            element_type="ligne",
            element_name=f"{table.name}#{row.id}",
            description=f"Ligne créée dans table {table.name}",
            database_id=table.database_id,
            table_id=table_id,
            ip_address=ip_address,
            before=None,
            after=row.to_dict()
        )
        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="CREATION_LIGNE",
            element_type="ligne",
            element_name=f"{table.name}#{row.id}",
            meta={"table_id": table_id, "row_id": row.id}
        )
        emit_modification("ligne", row.to_dict(), creator_name or "unknown")

        return row, None

    @staticmethod
    def update(table_id, row_id, data_dict, updater_id=None, updater_name=None, ip_address=None, provided_key=None):
        table, err = RowService._check_table_access(table_id, user_id=updater_id, provided_key=provided_key)
        if err:
            return None, err

        row = TableRow.query.filter_by(id=row_id, table_id=table_id).first()
        if not row:
            return None, "Ligne introuvable"

        before = row.to_dict()

        if not isinstance(data_dict, dict):
            return None, "Données invalides"

        row.set_data(data_dict)
        row.last_modified_by_id = updater_id
        row.last_modified_by_name = updater_name
        row.updated_at = now_utc()
        db.session.commit()

        HistoryService.log(
            user_id=updater_id,
            user_name=updater_name,
            action_type="a modifié",
            element_type="ligne",
            element_name=f"{table.name}#{row.id}",
            description=f"Ligne {row_id} modifiée dans table {table.name}",
            database_id=table.database_id,
            table_id=table_id,
            ip_address=ip_address,
            before=before,
            after=row.to_dict()
        )
        AuditService.log(
            user_id=updater_id,
            user_name=updater_name,
            ip_address=ip_address,
            action="MODIFICATION_LIGNE",
            element_type="ligne",
            element_name=f"{table.name}#{row.id}",
            meta={"table_id": table_id, "row_id": row_id, "before": before, "after": row.to_dict()}
        )
        emit_modification("ligne", row.to_dict(), updater_name or "unknown")

        return row, None

    @staticmethod
    def delete(table_id, row_id, deleter_id=None, deleter_name=None, ip_address=None, provided_key=None):
        table, err = RowService._check_table_access(table_id, user_id=deleter_id, provided_key=provided_key)
        if err:
            return False, err

        row = TableRow.query.filter_by(id=row_id, table_id=table_id).first()
        if not row:
            return False, "Ligne introuvable"

        before = row.to_dict()

        db.session.delete(row)
        db.session.commit()

        HistoryService.log(
            user_id=deleter_id,
            user_name=deleter_name,
            action_type="a supprimé",
            element_type="ligne",
            element_name=f"{table.name}#{row_id}",
            description=f"Ligne {row_id} supprimée de table {table.name}",
            database_id=table.database_id,
            table_id=table_id,
            ip_address=ip_address,
            before=before,
            after=None
        )
        AuditService.log(
            user_id=deleter_id,
            user_name=deleter_name,
            ip_address=ip_address,
            action="SUPPRESSION_LIGNE",
            element_type="ligne",
            element_name=f"{table.name}#{row_id}",
            meta={"table_id": table_id, "row_id": row_id}
        )

        return True, None

    @staticmethod
    def bulk_import(table_id, rows_data, creator_id=None, creator_name=None, ip_address=None, provided_key=None):
        """Import multiple rows (for project import)"""
        table, err = RowService._check_table_access(table_id, user_id=creator_id, provided_key=provided_key)
        if err:
            return None, err

        created = []
        for data_dict in rows_data:
            if not isinstance(data_dict, dict):
                continue
            row = TableRow(
                uuid=str(uuid_lib.uuid4()),
                table_id=table_id,
                data_json=json.dumps(data_dict, ensure_ascii=False),
                creator_id=creator_id,
                last_modified_by_id=creator_id,
                last_modified_by_name=creator_name,
                created_at=now_utc(),
                updated_at=now_utc()
            )
            db.session.add(row)
            created.append(row)

        db.session.commit()
        return created, None
