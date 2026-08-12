"""
Service Project - Export/Import complet d'un projet XMLForge
Exporte base + tables + colonnes + protections + file_identifier + données
"""
from ..models.database import Database
from ..models.table import Table
from ..models.table_row import TableRow
from ..extensions import db
from ..utils.helpers import now_utc
from .audit_service import AuditService
from ..socket_events import emit_export_xml
from lxml import etree
import uuid as uuid_lib
import json

class ProjectService:

    @staticmethod
    def export_project_to_xml(database_id, user_id=None, user_name=None, ip_address=None):
        database = Database.query.get(database_id)
        if not database:
            return None, "Base introuvable"

        db_attrs = {
            'name': database.name,
            'uuid': database.uuid or "",
            'description': database.description or "",
            'comment': database.comment or "",
            'status': database.status,
            'key_identifier': database.key_identifier or "",
        }
        db_elem = etree.Element('database', **db_attrs)

        tables = Table.query.filter_by(database_id=database_id).all()
        for table in tables:
            t_attrs = {
                'name': table.name,
                'uuid': table.uuid or "",
                'description': table.description or "",
                'comment': table.comment or "",
                'protected': str(table.is_protected).lower(),
                'status': table.status,
                'archived': str(table.is_archived()).lower(),
            }
            if table.file_identifier:
                t_attrs['file_identifier'] = table.file_identifier

            t_elem = etree.SubElement(db_elem, 'table', **t_attrs)

            # Columns
            cols_elem = etree.SubElement(t_elem, 'columns')
            for col in table.columns:
                c_attrs = {
                    'name': col.name,
                    'type': col.type,
                    'length': col.length,
                    'nullable': str(col.nullable).lower(),
                    'primary_key': str(col.primary_key).lower(),
                    'foreign_key': str(col.foreign_key).lower(),
                    'unique': str(col.unique).lower(),
                    'auto_increment': str(col.auto_increment).lower(),
                    'uuid': col.uuid or "",
                    'status': col.status,
                }
                if col.default_value is not None:
                    c_attrs['default'] = str(col.default_value)
                if col.comment:
                    c_attrs['comment'] = col.comment
                etree.SubElement(cols_elem, 'column', **c_attrs)

            # Rows / data
            rows_elem = etree.SubElement(t_elem, 'rows')
            rows = TableRow.query.filter_by(table_id=table.id).all()
            for row in rows:
                row_elem = etree.SubElement(rows_elem, 'row', uuid=row.uuid or "")
                data = row.get_data()
                for col_name, val in data.items():
                    cell_elem = etree.SubElement(row_elem, 'cell', column=col_name)
                    cell_elem.text = str(val) if val is not None else ""

        xml_str = etree.tostring(db_elem, pretty_print=True, encoding='unicode', xml_declaration=False)
        xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        if user_id:
            AuditService.log(
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                action="EXPORT_PROJECT",
                element_type="base",
                element_name=database.name,
                description=f"Export projet complet base {database.name}",
                meta={"database_id": database_id, "tables": len(tables)}
            )
            emit_export_xml(database_id, user_name or "unknown")

        return xml_final, None

    @staticmethod
    def import_project_from_xml(xml_content, creator_id=None, creator_name=None, ip_address=None):
        """
        Importe un projet complet depuis XML
        Reconstruit base, tables, colonnes, protections, données
        """
        from .import_service import ImportService

        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        # Mais _parse_xml_v3 ne parse pas <rows> ni <columns> wrapper, on doit parser manuellement pour V4
        # On va parser avec lxml directement pour support complet
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except Exception as e:
            return None, f"XML invalide: {e}"

        # Déterminer database element
        if root.tag.lower() == 'database':
            db_elem = root
        else:
            db_elem = root.find('.//database')
            if db_elem is None:
                # Si pas de database, créer avec nom générique
                db_elem = None

        if db_elem is not None:
            db_name = db_elem.get('name') or f"import_project_{now_utc().strftime('%Y%m%d_%H%M%S')}"
            db_desc = db_elem.get('description', '')
            db_comment = db_elem.get('comment', '')
            table_elems = db_elem.findall('./table')
            if not table_elems:
                table_elems = db_elem.findall('.//table')
        else:
            db_name = f"import_project_{now_utc().strftime('%Y%m%d_%H%M%S')}"
            db_desc = ""
            db_comment = ""
            table_elems = root.findall('.//table')
            if not table_elems:
                table_elems = [root] if root.tag.lower() == 'table' else []

        # Créer base
        from ..utils.helpers import generate_key_identifier
        for _ in range(5):
            key = generate_key_identifier()
            if not Database.query.filter_by(key_identifier=key).first():
                break

        database = Database(
            uuid=str(uuid_lib.uuid4()),
            name=db_name,
            description=db_desc,
            creator_id=creator_id,
            key_identifier=key,
            comment=db_comment,
            status="ACTIVE",
            last_modified_by_id=creator_id,
            last_modified_by_name=creator_name,
            created_at=now_utc(),
            updated_at=now_utc()
        )
        db.session.add(database)
        db.session.flush()

        created_tables = 0
        created_columns = 0
        created_rows = 0

        for t_elem in table_elems:
            t_name = t_elem.get('name')
            if not t_name:
                continue

            protected_raw = t_elem.get('protected', 'false')
            is_protected = str(protected_raw).lower() in ('true', '1', 'yes')
            file_id = t_elem.get('file_identifier') or t_elem.get('fileIdentifier')
            status = t_elem.get('status', 'ACTIVE')
            archived_raw = t_elem.get('archived', 'false')
            if str(archived_raw).lower() in ('true', '1', 'yes'):
                status = "ARCHIVED"

            table = Table(
                uuid=t_elem.get('uuid') or str(uuid_lib.uuid4()),
                name=t_name,
                description=t_elem.get('description', ''),
                database_id=database.id,
                creator_id=creator_id,
                is_protected=is_protected,
                file_identifier=file_id,
                comment=t_elem.get('comment', ''),
                status=status,
                last_modified_by_id=creator_id,
                last_modified_by_name=creator_name,
                created_at=now_utc(),
                updated_at=now_utc()
            )
            db.session.add(table)
            db.session.flush()
            created_tables += 1

            # Colonnes: chercher d'abord <columns><column> puis directement <column>
            cols_parent = t_elem.find('./columns')
            if cols_parent is not None:
                col_elems = cols_parent.findall('./column')
            else:
                col_elems = t_elem.findall('./column')

            from ..models.column import Column
            for col_elem in col_elems:
                c_name = col_elem.get('name')
                if not c_name:
                    continue

                def _bool(attr, default=False):
                    v = col_elem.get(attr)
                    if v is None:
                        # variantes camelCase
                        for var in [attr.replace('_', ''), attr.replace('_', '-')]:
                            if col_elem.get(var) is not None:
                                v = col_elem.get(var)
                                break
                    if v is None:
                        return default
                    return str(v).lower() in ('true', '1', 'yes')

                col = Column(
                    uuid=col_elem.get('uuid') or str(uuid_lib.uuid4()),
                    name=c_name,
                    type=col_elem.get('type', 'VARCHAR'),
                    length=col_elem.get('length', '-'),
                    nullable=col_elem.get('nullable', 'true').lower() not in ('false', '0', 'no') if col_elem.get('nullable') is not None else True,
                    primary_key=_bool('primary_key', False) or _bool('primaryKey', False),
                    foreign_key=_bool('foreign_key', False) or _bool('foreignKey', False),
                    unique=_bool('unique', False),
                    auto_increment=_bool('auto_increment', False) or _bool('autoIncrement', False),
                    default_value=col_elem.get('default'),
                    creator_id=creator_id,
                    table_id=table.id,
                    comment=col_elem.get('comment', ''),
                    status=col_elem.get('status', 'ACTIVE'),
                    last_modified_by_id=creator_id,
                    last_modified_by_name=creator_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(col)
                created_columns += 1

            # Rows
            rows_parent = t_elem.find('./rows')
            if rows_parent is not None:
                row_elems = rows_parent.findall('./row')
                for row_elem in row_elems:
                    data = {}
                    cell_elems = row_elem.findall('./cell')
                    for cell_elem in cell_elems:
                        col_name = cell_elem.get('column')
                        if not col_name:
                            continue
                        data[col_name] = cell_elem.text or ""
                    # Si pas de <cell> mais row contient directement des enfants?
                    if not data and row_elem.text:
                        # Ignorer
                        pass
                    if data:
                        row = TableRow(
                            uuid=row_elem.get('uuid') or str(uuid_lib.uuid4()),
                            table_id=table.id,
                            data_json=json.dumps(data, ensure_ascii=False),
                            creator_id=creator_id,
                            last_modified_by_id=creator_id,
                            last_modified_by_name=creator_name,
                            created_at=now_utc(),
                            updated_at=now_utc()
                        )
                        db.session.add(row)
                        created_rows += 1

        db.session.commit()

        from .history_service import HistoryService
        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a importé",
            element_type="base",
            element_name=database.name,
            description=f"Import projet complet: {created_tables} tables, {created_columns} colonnes, {created_rows} lignes",
            database_id=database.id,
            ip_address=ip_address,
            before=None,
            after={"tables": created_tables, "columns": created_columns, "rows": created_rows}
        )
        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="IMPORT_PROJECT",
            element_type="base",
            element_name=database.name,
            description=f"Import projet {database.name}: {created_tables} tables, {created_rows} lignes",
            meta={"database_id": database.id}
        )

        from ..socket_events import emit_import_xml
        emit_import_xml(database.to_dict(include_key=True), creator_name or "unknown")

        return database, None
