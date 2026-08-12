"""
Service Export V4 - XML avec <columns> et <rows>
"""
from ..models.database import Database
from ..models.table import Table
from ..models.table_row import TableRow
from lxml import etree
from ..converters.xml_to_sql import convert_xml_to_sql
from ..socket_events import emit_export_xml, emit_export_sql
from .audit_service import AuditService

class ExportService:

    @staticmethod
    def export_database_to_xml(database_id, user_id=None, user_name=None, ip_address=None):
        database = Database.query.get(database_id)
        if not database:
            return None, "Base introuvable"

        db_elem = etree.Element('database',
            name=database.name,
            uuid=database.uuid or "",
            description=database.description or "",
            comment=database.comment or "",
            status=database.status
        )

        tables = Table.query.filter_by(database_id=database_id).all()
        for table in tables:
            t_attrs = {
                'name': table.name,
                'uuid': table.uuid or "",
                'description': table.description or "",
                'comment': table.comment or "",
                'protected': str(table.is_protected).lower(),
                'archived': str(table.is_archived()).lower(),
                'status': table.status,
            }
            if table.file_identifier:
                t_attrs['file_identifier'] = table.file_identifier

            t_elem = etree.SubElement(db_elem, 'table', **t_attrs)

            # Columns wrapper for V4 compatibility
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

            # Rows
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
                action="EXPORT_XML",
                element_type="base",
                element_name=database.name,
                description=f"Export XML base {database.name}",
                meta={"database_id": database_id}
            )
            emit_export_xml(database_id, user_name or "unknown")

        return xml_final, None

    @staticmethod
    def export_database_to_sql(database_id, user_id=None, user_name=None, ip_address=None):
        xml_content, err = ExportService.export_database_to_xml(database_id, user_id, user_name, ip_address)
        if err:
            return None, err

        database = Database.query.get(database_id)

        try:
            sql = convert_xml_to_sql(xml_content, database_name=database.name)

            if user_id:
                AuditService.log(
                    user_id=user_id,
                    user_name=user_name,
                    ip_address=ip_address,
                    action="EXPORT_SQL",
                    element_type="base",
                    element_name=database.name,
                    description=f"Export SQL base {database.name}",
                    meta={"database_id": database_id}
                )
                emit_export_sql(database_id, user_name or "unknown")

            return sql, None
        except Exception as e:
            return None, f"Erreur conversion XML->SQL: {e}"

    @staticmethod
    def export_table_to_xml(table_id, user_id=None, user_name=None, ip_address=None, include_rows=True):
        table = Table.query.get(table_id)
        if not table:
            return None, "Table introuvable"

        t_attrs = {
            'name': table.name,
            'uuid': table.uuid or "",
            'description': table.description or "",
            'comment': table.comment or "",
            'protected': str(table.is_protected).lower(),
            'archived': str(table.is_archived()).lower(),
            'status': table.status,
        }
        if table.file_identifier:
            t_attrs['file_identifier'] = table.file_identifier

        t_elem = etree.Element('table', **t_attrs)

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

        if include_rows:
            rows_elem = etree.SubElement(t_elem, 'rows')
            rows = TableRow.query.filter_by(table_id=table.id).all()
            for row in rows:
                row_elem = etree.SubElement(rows_elem, 'row', uuid=row.uuid or "")
                data = row.get_data()
                for col_name, val in data.items():
                    cell_elem = etree.SubElement(row_elem, 'cell', column=col_name)
                    cell_elem.text = str(val) if val is not None else ""

        xml_str = etree.tostring(t_elem, pretty_print=True, encoding='unicode', xml_declaration=False)
        xml_final = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str

        if user_id:
            AuditService.log(
                user_id=user_id,
                user_name=user_name,
                ip_address=ip_address,
                action="EXPORT_XML_TABLE",
                element_type="table",
                element_name=table.name,
                description=f"Export XML table {table.name}",
                meta={"table_id": table_id, "database_id": table.database_id}
            )
            emit_export_xml(table.database_id, user_name or "unknown")

        return xml_final, None

    @staticmethod
    def export_table_to_sql(table_id, user_id=None, user_name=None, ip_address=None):
        xml_content, err = ExportService.export_table_to_xml(table_id, user_id, user_name, ip_address, include_rows=False)
        if err:
            return None, err

        table = Table.query.get(table_id)
        try:
            sql = convert_xml_to_sql(xml_content, database_name=None)
            if user_id:
                AuditService.log(
                    user_id=user_id,
                    user_name=user_name,
                    ip_address=ip_address,
                    action="EXPORT_SQL_TABLE",
                    element_type="table",
                    element_name=table.name,
                    description=f"Export SQL table {table.name}",
                    meta={"table_id": table_id, "database_id": table.database_id}
                )
                emit_export_sql(table.database_id, user_name or "unknown")
            return sql, None
        except Exception as e:
            return None, f"Erreur conversion XML->SQL table: {e}"
