"""
Service Import V3 - supporte nouvelle spec XMLForge XML Specification
- DATABASE: name, description, comment
- TABLE: name, description, protected, file_identifier, comment, archived
- COLUMN: name, type, length, nullable, primary_key, foreign_key, references, unique, auto_increment, default, comment
- XML est source de vérité
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

class ImportService:

    @staticmethod
    def _parse_xml_v3(xml_content):
        """
        Parse XML V3 avec tous les attributs spec
        Retourne dict: {
          database: {name, description, comment},
          tables: [{name, description, protected, file_identifier, comment, archived, status, columns: [{...}]}]
        }
        Supporte ancien format aussi
        """
        try:
            root = etree.fromstring(xml_content.encode('utf-8'))
        except Exception as e:
            raise ValueError(f"XML invalide: {e}")

        database_info = {"name": None, "description": "", "comment": ""}

        # Si root est database
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
            # Chercher database puis tables, ou directement tables
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
                # Si root contient directement colonnes sans table? Non

        tables = []
        for t_elem in table_elems:
            t_name = t_elem.get('name')
            if not t_name:
                continue

            # Attributs V3
            # protected peut être "true"/"false" ou bool
            protected_raw = t_elem.get('protected', t_elem.get('is_protected', 'false'))
            is_protected = str(protected_raw).lower() in ('true','1','yes')

            # file_identifier peut être file_identifier ou fileIdentifier
            file_id = t_elem.get('file_identifier') or t_elem.get('fileIdentifier') or t_elem.get('file_id') or None

            # archived bool ou status
            archived_raw = t_elem.get('archived', 'false')
            status_raw = t_elem.get('status', 'ACTIVE')
            if str(archived_raw).lower() in ('true','1','yes'):
                status = "ARCHIVED"
            else:
                # Si status fourni, utiliser, sinon ACTIVE
                status = status_raw if status_raw in ('ACTIVE','ARCHIVED') else "ACTIVE"
                # Si archived attr true, override
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
                'columns': ImportService._parse_columns_from_table(t_elem)
            })

        return database_info, tables

    @staticmethod
    def _parse_columns_from_table(t_elem):
        cols = []
        for col_elem in t_elem.findall('./column'):
            # Attributs V3
            name = col_elem.get('name')
            if not name:
                continue

            def _bool(attr, default=False):
                v = col_elem.get(attr)
                if v is None:
                    # essayer variantes camelCase
                    variants = {
                        'primary_key': ['primaryKey','primary_key','primary-key'],
                        'foreign_key': ['foreignKey','foreign_key','foreign-key'],
                        'auto_increment': ['autoIncrement','auto_increment','auto-increment'],
                    }
                    # Pour chaque attr, chercher variantes
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
            # Si status ARCHIVED via archived attr
            if col['archived']:
                col['status'] = "ARCHIVED"
            cols.append(col)
        return cols

    @staticmethod
    def import_xml(xml_content, database_name, creator_id, creator_name, description="Import XML", ip_address=None, comment=""):
        try:
            db_info, tables_data = ImportService._parse_xml_v3(xml_content)
        except Exception as e:
            return None, f"Erreur parsing XML: {e}"

        # Nom base : priorité param, sinon depuis XML, sinon auto
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

        db.session.commit()

        HistoryService.log(
            user_id=creator_id,
            user_name=creator_name,
            action_type="a importé",
            element_type="base",
            element_name=database.name,
            description=f"Import XML V3: {created_tables} tables, {created_columns} colonnes",
            database_id=database.id,
            ip_address=ip_address,
            before=None,
            after={"tables": created_tables, "columns": created_columns}
        )

        AuditService.log(
            user_id=creator_id,
            user_name=creator_name,
            ip_address=ip_address,
            action="IMPORT_XML",
            element_type="base",
            element_name=database.name,
            description=f"Import XML {database.name}: {created_tables} tables",
            meta={"database_id": database.id, "tables": created_tables, "columns": created_columns}
        )

        emit_import_xml(database.to_dict(include_key=True), creator_name)

        return database, None

    @staticmethod
    def import_sql(sql_content, database_name, creator_id, creator_name, description="Import SQL", ip_address=None, comment=""):
        # Réutilise ancien parse_sql mais enrichi avec V3
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
