"""
Service Import V4 - supporte nouvelle spec XMLForge avec <columns> et <rows>
- DATABASE: name, description, comment
- TABLE: name, description, protected, file_identifier, comment, archived
- COLUMN: name, type, length, nullable, primary_key, foreign_key, references, unique, auto_increment, default, comment
- ROWS: <rows><row><cell column="...">value</cell></row></rows>
"""
import uuid as uuid_lib
from ..extensions import db
from ..models.database import Database
from ..models.table import Table
from ..models.column import Column
from ..converters import parse_xml, parse_sql
from ..utils.helpers import generate_key_identifier, now_utc
from .history_service import HistoryService
from .audit_service import AuditService
from ..socket_events import emit_import_xml
from lxml import etree
import json

class ImportService:

    @staticmethod
    def _parse_xml_v3(xml_content):
        """
        Parse XML V3/V4 avec tous les attributs spec
        Retourne dict: {
          database: {name, description, comment},
          tables: [{name, description, protected, file_identifier, comment, archived, status, columns: [{...}], rows: [{...}]}]
        }
        Supporte ancien format aussi
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except Exception as e:
            raise ValueError(f"XML invalide: {e}")

        database_info = {"name": None, "description": "", "comment": ""}

        if root.tag.lower() == 'database':
            database_info["name"] = root.get('name')
            database_info["description"] = root.get('description','')
            database_info["comment"] = root.get('comment','')
            table_elems = root.findall('./table')
            if not table_elems:
                table_elems = root.findall('.//table')
        elif root.tag.lower() == 'table':
            table_elems = [root]
        else:
            db_elem = root.find('.//database')
            if db_elem is not None:
                database_info["name"] = db_elem.get('name')
                database_info["description"] = db_elem.get('description','')
                database_info["comment"] = db_elem.get('comment','')
                table_elems = db_elem.findall('./table')
                if not table_elems:
                    table_elems = db_elem.findall('.//table')
            else:
                table_elems = root.findall('.//table')
                if not table_elems:
                    table_elems = root.findall('./table')

        tables = []
        for t_elem in table_elems:
            t_name = t_elem.get('name')
            if not t_name:
                continue

            protected_raw = t_elem.get('protected', t_elem.get('is_protected', 'false'))
            is_protected = str(protected_raw).lower() in ('true','1','yes')

            file_id = t_elem.get('file_identifier') or t_elem.get('fileIdentifier') or t_elem.get('file_id') or None

            archived_raw = t_elem.get('archived', 'false')
            status_raw = t_elem.get('status', 'ACTIVE')
            if str(archived_raw).lower() in ('true','1','yes'):
                status = "ARCHIVED"
            else:
                status = status_raw if status_raw in ('ACTIVE','ARCHIVED') else "ACTIVE"
                if str(archived_raw).lower() in ('true','1','yes'):
                    status = "ARCHIVED"

            tables.append({
                'name': t_name,
                'description': t_elem.get('description',''),
                'comment': t_elem.get('comment',''),
                'protected': is_protected,
                'file_identifier': file_id,
                'status': status,
                'archived': status == "ARCHIVED",
                'columns': ImportService._parse_columns_from_table(t_elem),
                'rows': ImportService._parse_rows_from_table(t_elem)
            })

        return database_info, tables

    @staticmethod
    def _parse_columns_from_table(t_elem):
        cols = []
        # Cherche d'abord dans <columns> puis directement <column>
        col_parent = t_elem.find('./columns')
        if col_parent is not None:
            col_elems = col_parent.findall('./column')
        else:
            col_elems = t_elem.findall('./column')

        for col_elem in col_elems:
            name = col_elem.get('name')
            if not name:
                continue

            def _bool(attr, default=False):
                v = col_elem.get(attr)
                if v is None:
                    variants = {
                        'primary_key': ['primaryKey','primary_key','primary-key'],
                        'foreign_key': ['foreignKey','foreign_key','foreign-key'],
                        'auto_increment': ['autoIncrement','auto_increment','auto-increment'],
                    }
                    for var in variants.get(attr, []):
                        if col_elem.get(var) is not None:
                            v = col_elem.get(var)
                            break
                if v is None:
                    return default
                return str(v).lower() in ('true','1','yes')

            col = {
                'name': name,
                'type': col_elem.get('type','VARCHAR'),
                'length': col_elem.get('length','-'),
                'nullable': col_elem.get('nullable','true').lower() not in ('false','0','no') if col_elem.get('nullable') is not None else True,
                'primary_key': _bool('primary_key', False),
                'foreign_key': _bool('foreign_key', False),
                'unique': _bool('unique', False),
                'auto_increment': _bool('auto_increment', False),
                'default': col_elem.get('default'),
                'comment': col_elem.get('comment',''),
                'references': col_elem.get('references') or col_elem.get('foreignKeyRef') or None,
                'status': col_elem.get('status','ACTIVE'),
                'archived': col_elem.get('archived','false').lower() in ('true','1','yes')
            }
            if col['archived']:
                col['status'] = "ARCHIVED"
            cols.append(col)
        return cols

    @staticmethod
    def _parse_rows_from_table(t_elem):
        rows = []
        rows_parent = t_elem.find('./rows')
        if rows_parent is None:
            return rows

        for row_elem in rows_parent.findall('./row'):
            data = {}
            # Version <cell column="name">value</cell>
            cell_elems = row_elem.findall('./cell')
            for cell_elem in cell_elems:
                col_name = cell_elem.get('column')
                if not col_name:
                    continue
                data[col_name] = cell_elem.text or ""
            # Fallback: si row contient directement des balises <id>1</id> etc (ancienne spec)
            if not data:
                for child in row_elem:
                    if child.tag.lower() != 'cell':
                        if child.text is not None:
                            data[child.tag] = child.text

            if data:
                rows.append(data)
        return rows

    @staticmethod
    def import_xml(xml_content, database_name, creator_id, creator_name, description="Import XML", ip_address=None, comment=""):
        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        final_db_name = database_name or db_info.get('name') or f"import_xml_{now_utc().strftime('%Y%m%d_%H%M%S')}"
        final_db_desc = description or db_info.get('description','')
        final_db_comment = comment or db_info.get('comment','')

        for _ in range(5):
            key = generate_key_identifier()
            if not Database.query.filter_by(key_identifier=key).first():
                break

        database = Database(
            uuid=str(uuid_lib.uuid4()),
            name=final_db_name,
            description=final_db_desc,
            creator_id=creator_id,
            key_identifier=key,
            comment=final_db_comment,
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

        for t_data in tables_data:
            t_name = t_data['name']
            table = Table(
                uuid=str(uuid_lib.uuid4()),
                name=t_name,
                description=t_data.get('description',''),
                database_id=database.id,
                creator_id=creator_id,
                is_protected=t_data.get('protected', False),
                file_identifier=t_data.get('file_identifier'),
                comment=t_data.get('comment',''),
                status=t_data.get('status','ACTIVE'),
                last_modified_by_id=creator_id,
                last_modified_by_name=creator_name,
                created_at=now_utc(),
                updated_at=now_utc()
            )
            db.session.add(table)
            db.session.flush()
            created_tables += 1

            for col in t_data['columns']:
                column = Column(
                    uuid=str(uuid_lib.uuid4()),
                    name=col['name'],
                    type=col['type'],
                    length=col['length'],
                    nullable=col['nullable'],
                    primary_key=col['primary_key'],
                    foreign_key=col['foreign_key'],
                    unique=col['unique'],
                    auto_increment=col['auto_increment'],
                    default_value=col['default'],
                    creator_id=creator_id,
                    table_id=table.id,
                    comment=col.get('comment',''),
                    status=col.get('status','ACTIVE'),
                    last_modified_by_id=creator_id,
                    last_modified_by_name=creator_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(column)
                created_columns += 1

            # Rows
            for row_data in t_data.get('rows', []):
                from ..models.table_row import TableRow
                row = TableRow(
                    uuid=str(uuid_lib.uuid4()),
                    table_id=table.id,
                    data_json=json.dumps(row_data, ensure_ascii=False),
                    creator_id=creator_id,
                    last_modified_by_id=creator_id,
                    last_modified_by_name=creator_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(row)
                created_rows += 1

        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a importé",
            element_type="base",
            element_name=database.name,
            description=f"Import XML V4: {created_tables} tables, {created_columns} colonnes, {created_rows} lignes",
            database_id=database.id,
            ip_address=ip_address,
            before=None,
            after={"tables": created_tables, "columns": created_columns, "rows": created_rows}
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="IMPORT_XML",
            element_type="base",
            element_name=database.name,
            description=f"Import XML {database.name}: {created_tables} tables",
            meta={"database_id": database.id, "tables": created_tables, "columns": created_columns, "rows": created_rows}
        )

        emit_import_xml(database.to_dict(include_key=True), creator_name)

        return database, None

    @staticmethod
    def import_sql(sql_content, database_name, creator_id, creator_name, description="Import SQL", ip_address=None, comment=""):
        try:
            from ..converters import parse_sql
            tables_data = parse_sql(sql_content)
        except Exception as e:
            return None, f"Erreur parsing SQL: {e}"

        if not tables_data:
            return None, "Aucune table trouvée dans SQL"

        if not database_name:
            database_name = f"import_sql_{now_utc().strftime('%Y%m%d_%H%M%S')}"

        for _ in range(5):
            key = generate_key_identifier()
            if not Database.query.filter_by(key_identifier=key).first():
                break

        database = Database(
            uuid=str(uuid_lib.uuid4()),
            name=database_name,
            description=description,
            creator_id=creator_id,
            key_identifier=key,
            comment=comment,
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

        for t_data in tables_data:
            t_name = t_data['name']
            table = Table(
                uuid=str(uuid_lib.uuid4()),
                name=t_name,
                description="",
                database_id=database.id,
                creator_id=creator_id,
                is_protected=False,
                comment="",
                status="ACTIVE",
                last_modified_by_id=creator_id,
                last_modified_by_name=creator_name,
                created_at=now_utc(),
                updated_at=now_utc()
            )
            db.session.add(table)
            db.session.flush()
            created_tables += 1

            for col in t_data['columns']:
                column = Column(
                    uuid=str(uuid_lib.uuid4()),
                    name=col['name'],
                    type=col['type'],
                    length=col['length'],
                    nullable=col['nullable'],
                    primary_key=col['primary_key'],
                    foreign_key=col['foreign_key'],
                    unique=col['unique'],
                    auto_increment=col['auto_increment'],
                    default_value=col['default'],
                    creator_id=creator_id,
                    table_id=table.id,
                    comment="",
                    status="ACTIVE",
                    last_modified_by_id=creator_id,
                    last_modified_by_name=creator_name,
                    created_at=now_utc(),
                    updated_at=now_utc()
                )
                db.session.add(column)
                created_columns += 1

        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a importé",
            element_type="base",
            element_name=database.name,
            description=f"Import SQL: {created_tables} tables, {created_columns} colonnes",
            database_id=database.id,
            ip_address=ip_address,
            before=None,
            after={"tables": created_tables, "columns": created_columns}
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="IMPORT_SQL",
            element_type="base",
            element_name=database.name,
            description=f"Import SQL {database.name}: {created_tables} tables",
            meta={"database_id": database.id}
        )

        emit_import_xml(database.to_dict(include_key=True), creator_name)

        return database, None
