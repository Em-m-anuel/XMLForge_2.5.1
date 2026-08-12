"""
Service Column V4 - avec protection personnelle
"""
import uuid as uuid_lib
from ..extensions import db
from ..models.column import Column
from ..models.table import Table
from ..models.database import Database
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from .table_service import TableService
from ..socket_events import emit_new_column, emit_modification, emit_suppression

class ColumnService:

    @staticmethod
    def get_by_table(table_id, include_archived=True):
        query = Column.query.filter_by(table_id=table_id)
        if not include_archived:
            query = query.filter_by(status="ACTIVE")
        return query.order_by(Column.created_at.asc()).all()

    @staticmethod
    def get_by_id(col_id):
        return Column.query.get(col_id)

    @staticmethod
    def create(data, creator_id, creator_name, provided_key=None, ip_address=None):
        table_id = data.get('table_id')
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        if table.is_archived():
            return None, f"Table '{table.name}' archivée, création colonne impossible."

        allowed, msg = TableService._check_protection(table, provided_key=provided_key, user_id=creator_id)
        if not allowed:
            return None, msg

        if Column.query.filter_by(table_id=table_id, name=data['name']).first():
            return None, f"Colonne '{data['name']}' existe déjà dans table {table.name}"

        column = Column(
            uuid=str(uuid_lib.uuid4()),
            name=data['name'],
            type=data.get('type', 'VARCHAR'),
            length=data.get('length', '-'),
            nullable=data.get('nullable', True),
            primary_key=data.get('primary_key', False),
            foreign_key=data.get('foreign_key', False),
            unique=data.get('unique', False),
            auto_increment=data.get('auto_increment', False),
            default_value=data.get('default'),
            creator_id=creator_id,
            table_id=table_id,
            comment=data.get('comment', ''),
            status="ACTIVE",
            last_modified_by_id=creator_id,
            last_modified_by_name=creator_name,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        db.session.add(column)
        db.session.flush()

        table.last_modified_by_id = creator_id
        table.last_modified_by_name = creator_name
        table.updated_at = now_utc()

        database = Database.query.get(table.database_id)
        if database:
            database.last_modified_by_id = creator_id
            database.last_modified_by_name = creator_name
            database.updated_at = now_utc()

        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a ajouté",
            element_type="colonne",
            element_name=column.name,
            description=f"Colonne {column.name} ajoutée à table {table.name}",
            database_id=table.database_id,
            table_id=table_id,
            ip_address=ip_address,
            before=None,
            after=column.to_dict()
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="CREATION_COLONNE",
            element_type="colonne",
            element_name=column.name,
            description=f"Création colonne {column.name} dans table {table.name}",
            meta={"column_id": column.id, "table_id": table_id}
        )

        emit_new_column(column.to_dict(), creator_name)

        return column, None

    @staticmethod
    def update(col_id, data, user_id, user_name, provided_key=None, ip_address=None):
        column = Column.query.get(col_id)
        if not column:
            return None, "Colonne introuvable"

        if column.is_archived():
            return None, f"Colonne '{column.name}' archivée, modification impossible."

        table = Table.query.get(column.table_id)
        if not table:
            return None, "Table parente introuvable"

        if table.is_archived():
            return None, f"Table '{table.name}' archivée, modification colonne impossible."

        allowed, msg = TableService._check_protection(table, provided_key=provided_key, user_id=user_id)
        if not allowed:
            return None, msg

        before = column.to_dict()

        for field in ['name','type','length','nullable','primary_key','foreign_key','unique','auto_increment','default','comment']:
            if field in data:
                if field == 'default':
                    setattr(column, 'default_value', data[field])
                elif field == 'primary_key':
                    setattr(column, 'primary_key', data[field])
                elif field == 'foreign_key':
                    setattr(column, 'foreign_key', data[field])
                elif field == 'unique':
                    setattr(column, 'unique', data[field])
                elif field == 'auto_increment':
                    setattr(column, 'auto_increment', data[field])
                elif field == 'comment':
                    setattr(column, 'comment', data[field])
                else:
                    setattr(column, field, data[field])

        column.last_modified_by_id = user_id
        column.last_modified_by_name = user_name
        column.updated_at = now_utc()

        db.session.commit()

        after = column.to_dict()

        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()

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
            element_type="colonne",
            element_name=column.name,
            description=f"Colonne {column.id} modifiée dans table {table.name}",
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
            action="MODIFICATION_COLONNE",
            element_type="colonne",
            element_name=column.name,
            meta={"column_id": col_id, "before": before, "after": after}
        )

        emit_modification("colonne", column.to_dict(), user_name)

        return column, None

    @staticmethod
    def delete(col_id, user_id, user_name, provided_key=None, ip_address=None):
        column = Column.query.get(col_id)
        if not column:
            return False, "Colonne introuvable"

        if column.is_archived():
            return False, f"Colonne '{column.name}' archivée, suppression impossible."

        table = Table.query.get(column.table_id)
        if not table:
            return False, "Table parente introuvable"

        if table.is_archived():
            return False, f"Table '{table.name}' archivée, suppression colonne impossible."

        allowed, msg = TableService._check_protection(table, provided_key=provided_key, user_id=user_id)
        if not allowed:
            return False, msg

        before = column.to_dict()

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a supprimé",
            element_type="colonne",
            element_name=column.name,
            description=f"Colonne {column.name} supprimée de table {table.name}",
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
            action="SUPPRESSION_COLONNE",
            element_type="colonne",
            element_name=column.name,
            meta={"column_id": col_id, "table_id": table.id}
        )

        emit_suppression("colonne", column.name, table.database_id, user_name)

        db.session.delete(column)
        db.session.commit()

        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()

        database = Database.query.get(table.database_id)
        if database:
            database.last_modified_by_id = user_id
            database.last_modified_by_name = user_name
            database.updated_at = now_utc()

        db.session.commit()

        return True, None
