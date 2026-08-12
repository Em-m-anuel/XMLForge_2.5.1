"""
Service Sync - V4 avec protection personnelle
- Sync base (full)
- Sync table : XML d'une seule table, modifie uniquement la table sélectionnée
"""

import uuid as uuid_lib
import json
from ..extensions import db
from ..models.database import Database
from ..models.table import Table
from ..models.column import Column
from ..utils.helpers import now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_modification
from .import_service import ImportService


class SyncService:

    @staticmethod
    def _is_table_unlocked_personally(user_id, table):
        if not table.is_protected:
            return True
        if not user_id:
            return False
        try:
            from ..models.table_unlock import TableUnlock
            unlock = TableUnlock.query.filter_by(user_id=user_id, table_id=table.id).first()
            if unlock and not unlock.is_expired():
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def sync_database_from_xml(database_id, xml_content, user_id, user_name, ip_address=None, provided_key=None):
        database = Database.query.get(database_id)
        if not database:
            return None, "Base introuvable"

        if database.is_archived():
            return None, f"Base '{database.name}' archivée, synchronisation impossible. Restaurez-la d'abord."

        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        before_db = database.to_dict(include_key=True)
        updated = False
        if db_info.get('description') and db_info['description'] != database.description:
            database.description = db_info['description']
            updated = True
        if db_info.get('comment') and db_info['comment'] != database.comment:
            database.comment = db_info['comment']
            updated = True

        if updated:
            database.last_modified_by_id = user_id
            database.last_modified_by_name = user_name
            database.updated_at = now_utc()

        existing_tables_by_name = {t.name: t for t in Table.query.filter_by(database_id=database_id).all()}

        created_tables = 0
        updated_tables = 0
        created_columns = 0
        updated_columns = 0
        deleted_columns = 0
        created_rows = 0
        deleted_rows = 0
        sync_details = []

        for t_data in tables_data:
            t_name = t_data['name']
            existing_table = existing_tables_by_name.get(t_name)

            if not existing_table:
                new_table = Table(
                    uuid=str(uuid_lib.uuid4()),
                    name=t_name,
                    description=t_data.get('description',''),
                    database_id=database_id,
                    creator_id=user_id,
                    is_protected=t_data.get('protected', False),
                    file_identifier=t_data.get('file_identifier'),
                    comment=t_data.get('comment',''),
                    status=t_data.get('status','ACTIVE'),
                    last_modified_by_id=user_id,
                    last_modified_by_name=user_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(new_table)
                db.session.flush()
                created_tables += 1
                existing_table = new_table
                sync_details.append(f"Table créée: {t_name}")
            else:
                if existing_table.is_protected:
                    # Vérifier unlock personnel d'abord
                    if not SyncService._is_table_unlocked_personally(user_id, existing_table):
                        valid_keys = []
                        if existing_table.file_identifier:
                            valid_keys.append(existing_table.file_identifier)
                        if database.key_identifier:
                            valid_keys.append(database.key_identifier)
                        if provided_key and provided_key not in valid_keys:
                            sync_details.append(f"Table {t_name} protégée, clé invalide, mise à jour ignorée")
                            continue
                        elif not provided_key and valid_keys:
                            sync_details.append(f"Table {t_name} protégée, pas de clé fournie, mise à jour ignorée")
                            continue

                changed = False
                if t_data.get('description','') and t_data['description'] != existing_table.description:
                    existing_table.description = t_data['description']
                    changed = True
                if t_data.get('comment','') is not None and t_data['comment'] != existing_table.comment:
                    existing_table.comment = t_data['comment']
                    changed = True
                if 'protected' in t_data:
                    if t_data['protected'] != existing_table.is_protected:
                        existing_table.is_protected = t_data['protected']
                        changed = True
                if t_data.get('file_identifier') is not None:
                    if t_data['file_identifier'] != existing_table.file_identifier:
                        existing_table.file_identifier = t_data['file_identifier']
                        changed = True
                if t_data.get('status') and t_data['status'] != existing_table.status:
                    existing_table.status = t_data['status']
                    changed = True

                if changed:
                    existing_table.last_modified_by_id = user_id
                    existing_table.last_modified_by_name = user_name
                    existing_table.updated_at = now_utc()
                    updated_tables += 1
                    sync_details.append(f"Table mise à jour: {t_name}")

            existing_cols_by_name = {c.name: c for c in Column.query.filter_by(table_id=existing_table.id).all()}
            xml_col_names = set()

            for col_data in t_data['columns']:
                col_name = col_data['name']
                if not col_name:
                    continue
                xml_col_names.add(col_name)
                existing_col = existing_cols_by_name.get(col_name)

                if not existing_col:
                    new_col = Column(
                        uuid=str(uuid_lib.uuid4()),
                        name=col_data['name'],
                        type=col_data['type'],
                        length=col_data['length'],
                        nullable=col_data['nullable'],
                        primary_key=col_data['primary_key'],
                        foreign_key=col_data['foreign_key'],
                        unique=col_data['unique'],
                        auto_increment=col_data['auto_increment'],
                        default_value=col_data['default'],
                        creator_id=user_id,
                        table_id=existing_table.id,
                        comment=col_data.get('comment',''),
                        status=col_data.get('status','ACTIVE'),
                        last_modified_by_id=user_id,
                        last_modified_by_name=user_name,
                        created_at=now_utc(),
                        updated_at=now_utc()
                    )
                    db.session.add(new_col)
                    created_columns += 1
                    sync_details.append(f"  Colonne créée: {t_name}.{col_name}")
                else:
                    changed_col = False
                    for field in ['type','length','nullable','primary_key','foreign_key','unique','auto_increment','default','comment','status']:
                        if field in col_data:
                            current_val = getattr(existing_col, 'default_value' if field=='default' else field)
                            new_val = col_data[field]
                            if isinstance(current_val, bool) and isinstance(new_val, bool):
                                if current_val != new_val:
                                    changed_col = True
                                    setattr(existing_col, field if field!='default' else 'default_value', new_val)
                            else:
                                if str(current_val or '') != str(new_val or ''):
                                    changed_col = True
                                    if field == 'default':
                                        setattr(existing_col, 'default_value', new_val)
                                    else:
                                        setattr(existing_col, field, new_val)

                    if changed_col:
                        existing_col.last_modified_by_id = user_id
                        existing_col.last_modified_by_name = user_name
                        existing_col.updated_at = now_utc()
                        updated_columns += 1
                        sync_details.append(f"  Colonne mise à jour: {t_name}.{col_name}")

            for col_name, col_obj in existing_cols_by_name.items():
                if col_name not in xml_col_names:
                    db.session.delete(col_obj)
                    deleted_columns += 1
                    sync_details.append(f"  Colonne supprimée: {t_name}.{col_name}")

            # --- Synchronisation des rows ---
            if 'rows' in t_data:
                from ..models.table_row import TableRow
                existing_rows = TableRow.query.filter_by(table_id=existing_table.id).all()
                for r in existing_rows:
                    db.session.delete(r)
                    deleted_rows += 1

                for row_data in t_data.get('rows', []):
                    new_row = TableRow(
                        uuid=str(uuid_lib.uuid4()),
                        table_id=existing_table.id,
                        data_json=json.dumps(row_data, ensure_ascii=False),
                        creator_id=user_id,
                        last_modified_by_id=user_id,
                        last_modified_by_name=user_name,
                        created_at=now_utc(),
                        updated_at=now_utc()
                    )
                    db.session.add(new_row)
                    created_rows += 1

                sync_details.append(f"  Rows {t_name}: {deleted_rows} supprimées, {created_rows} recréées")

        db.session.commit()

        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()

        after_db = database.to_dict(include_key=True)

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a synchronisé",
            element_type="base",
            element_name=database.name,
            description=f"Sync XML: {created_tables} tables créées, {updated_tables} mises à jour, {created_columns} colonnes créées, {updated_columns} mises à jour, {deleted_columns} supprimées, {created_rows} rows recréées",
            database_id=database.id,
            ip_address=ip_address,
            before=before_db,
            after=after_db
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="SYNC_XML",
            element_type="base",
            element_name=database.name,
            description=f"Synchronisation XML base {database.name}: {created_tables}C {updated_tables}U tables, {created_columns}C {updated_columns}U {deleted_columns}D colonnes, {created_rows} rows",
            meta={"database_id": database_id, "details": sync_details}
        )

        emit_modification("base", database.to_dict(), user_name)

        from .export_service import ExportService
        sql_content, err = ExportService.export_database_to_sql(database_id)
        if err:
            sql_content = f"-- Erreur génération SQL: {err}"

        return {
            "database": database.to_dict(include_key=True),
            "created_tables": created_tables,
            "updated_tables": updated_tables,
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns,
            "created_rows": created_rows,
            "deleted_rows": deleted_rows,
            "details": sync_details,
            "sql": sql_content
        }, None

    @staticmethod
    def sync_table_from_xml(table_id, xml_content, user_id, user_name, ip_address=None, provided_key=None):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        database = Database.query.get(table.database_id)
        if not database:
            return None, "Base parente introuvable"

        if table.is_archived():
            return None, f"Table '{table.name}' archivée, synchronisation impossible. Restaurez-la d'abord."

        if database.is_archived():
            return None, f"Base '{database.name}' archivée, synchronisation impossible."

        # Vérifier protection avec unlock personnel
        if table.is_protected:
            if not SyncService._is_table_unlocked_personally(user_id, table):
                valid_keys = []
                if table.file_identifier:
                    valid_keys.append(table.file_identifier)
                if database.key_identifier:
                    valid_keys.append(database.key_identifier)
                if valid_keys:
                    if not provided_key:
                        return None, f"Table '{table.name}' protégée. Clé requise (file_identifier ou clé base)."
                    if provided_key not in valid_keys:
                        return None, f"Clé invalide pour table protégée '{table.name}'."

        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        if not tables_data:
            return None, "Aucune table trouvée dans le XML"

        t_data = None
        for td in tables_data:
            if td['name'] == table.name:
                t_data = td
                break
        if not t_data:
            t_data = tables_data[0]

        before_table = table.to_dict()

        sync_details = []
        created_columns = 0
        updated_columns = 0
        deleted_columns = 0
        created_rows = 0
        deleted_rows = 0

        new_name = t_data.get('name')
        if new_name and new_name != table.name:
            existing = Table.query.filter_by(database_id=table.database_id, name=new_name).first()
            if existing and existing.id != table.id:
                return None, f"Une autre table nommée '{new_name}' existe déjà dans cette base"
            sync_details.append(f"Table renommée: {table.name} → {new_name}")
            table.name = new_name

        if t_data.get('description','') is not None:
            if t_data['description'] != table.description:
                table.description = t_data['description']
                sync_details.append(f"Description mise à jour")

        if t_data.get('comment','') is not None:
            if t_data['comment'] != table.comment:
                table.comment = t_data['comment']

        if 'protected' in t_data:
            if t_data['protected'] != table.is_protected:
                table.is_protected = t_data['protected']
                sync_details.append(f"Protection changée: {table.is_protected}")

        if t_data.get('file_identifier') is not None:
            if t_data['file_identifier'] != table.file_identifier:
                table.file_identifier = t_data['file_identifier']
                sync_details.append(f"File identifier mis à jour: {table.file_identifier}")

        if t_data.get('status') and t_data['status'] != table.status:
            table.status = t_data['status']
            sync_details.append(f"Status: {t_data['status']}")

        table.last_modified_by_id = user_id
        table.last_modified_by_name = user_name
        table.updated_at = now_utc()

        existing_cols_by_name = {c.name: c for c in Column.query.filter_by(table_id=table.id).all()}
        xml_col_names = set()

        for col_data in t_data['columns']:
            col_name = col_data['name']
            if not col_name:
                continue
            xml_col_names.add(col_name)
            existing_col = existing_cols_by_name.get(col_name)

            if not existing_col:
                new_col = Column(
                    uuid=str(uuid_lib.uuid4()),
                    name=col_data['name'],
                    type=col_data['type'],
                    length=col_data['length'],
                    nullable=col_data['nullable'],
                    primary_key=col_data['primary_key'],
                    foreign_key=col_data['foreign_key'],
                    unique=col_data['unique'],
                    auto_increment=col_data['auto_increment'],
                    default_value=col_data['default'],
                    creator_id=user_id,
                    table_id=table.id,
                    comment=col_data.get('comment',''),
                    status=col_data.get('status','ACTIVE'),
                    last_modified_by_id=user_id,
                    last_modified_by_name=user_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(new_col)
                created_columns += 1
                sync_details.append(f"Colonne créée: {col_name}")
            else:
                changed = False
                field_map = {
                    'type': 'type',
                    'length': 'length',
                    'nullable': 'nullable',
                    'primary_key': 'primary_key',
                    'foreign_key': 'foreign_key',
                    'unique': 'unique',
                    'auto_increment': 'auto_increment',
                    'default': 'default_value',
                    'comment': 'comment',
                    'status': 'status'
                }
                for xml_field, model_field in field_map.items():
                    if xml_field in col_data:
                        new_val = col_data[xml_field]
                        cur_val = getattr(existing_col, model_field)
                        if isinstance(cur_val, bool) and isinstance(new_val, bool):
                            if cur_val != new_val:
                                setattr(existing_col, model_field, new_val)
                                changed = True
                        else:
                            if str(cur_val or '') != str(new_val or ''):
                                setattr(existing_col, model_field, new_val)
                                changed = True

                if changed:
                    existing_col.last_modified_by_id = user_id
                    existing_col.last_modified_by_name = user_name
                    existing_col.updated_at = now_utc()
                    updated_columns += 1
                    sync_details.append(f"Colonne mise à jour: {col_name}")

        for col_name, col_obj in existing_cols_by_name.items():
            if col_name not in xml_col_names:
                db.session.delete(col_obj)
                deleted_columns += 1
                sync_details.append(f"Colonne supprimée: {col_name}")

        # --- Synchronisation des rows ---
        if 'rows' in t_data:
            from ..models.table_row import TableRow
            existing_rows = TableRow.query.filter_by(table_id=table.id).all()
            for r in existing_rows:
                db.session.delete(r)
                deleted_rows += 1

            for row_data in t_data.get('rows', []):
                new_row = TableRow(
                    uuid=str(uuid_lib.uuid4()),
                    table_id=table.id,
                    data_json=json.dumps(row_data, ensure_ascii=False),
                    creator_id=user_id,
                    last_modified_by_id=user_id,
                    last_modified_by_name=user_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(new_row)
                created_rows += 1

            sync_details.append(f"Rows: {deleted_rows} supprimées, {created_rows} recréées")

        db.session.commit()

        database.last_modified_by_id = user_id
        database.last_modified_by_name = user_name
        database.updated_at = now_utc()
        db.session.commit()

        after_table = table.to_dict()

        HistoryService.log(
            user_id=user_id,
            user_name=user_name,
            action_type="a synchronisé",
            element_type="table",
            element_name=table.name,
            description=f"Sync XML table {table.name}: {created_columns}C {updated_columns}U {deleted_columns}D colonnes, {created_rows} rows recréées",
            database_id=database.id,
            table_id=table.id,
            ip_address=ip_address,
            before=before_table,
            after=after_table
        )

        AuditService.log(
            user_id=user_id,
            user_name=user_name,
            ip_address=ip_address,
            action="SYNC_XML_TABLE",
            element_type="table",
            element_name=table.name,
            description=f"Synchronisation XML table {table.name}",
            meta={"table_id": table.id, "database_id": database.id, "details": sync_details}
        )

        emit_modification("table", table.to_dict(), user_name)

        from .export_service import ExportService
        sql_content, err = ExportService.export_table_to_sql(table.id)
        if err:
            sql_content = f"-- Erreur génération SQL: {err}"

        xml_export, _ = ExportService.export_table_to_xml(table.id)

        return {
            "table": after_table,
            "database": database.to_dict(include_key=True),
            "created_columns": created_columns,
            "updated_columns": updated_columns,
            "deleted_columns": deleted_columns,
            "created_rows": created_rows,
            "deleted_rows": deleted_rows,
            "details": sync_details,
            "sql": sql_content,
            "xml": xml_export
        }, None