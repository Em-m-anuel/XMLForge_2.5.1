"""
Service Export V3 - XML source de vérité, contient toutes infos pour réimport sans perte
"""
from ..models.database import Database
from ..models.table import Table
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

        # Même archivée, exportable
        db_elem = etree.Element('database',
            name=database.name,
            uuid=database.uuid or "",
            description=database.description or "",
            comment=database.comment or "",
            status=database.status
        )

        tables = Table.query.filter_by(database_id=database_id).all()
        for table in tables:
            # Attributs selon spec XMLForge XML Specification
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
                # references pour FK
                # On pourrait chercher si colonne FK a une référence stockée, mais pour l'instant on ne stocke pas ref table.col dans colonne, on pourrait mettre dans commentaire ou attr references si existe
                # Pour V3, on ajoute references si foreign_key et on a une info dans description? On laisse vide, mais le champ references est supporté à l'import
                etree.SubElement(t_elem, 'column', **c_attrs)

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
        # SQL toujours généré depuis structure logique enregistrée, pas directement depuis XML
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
