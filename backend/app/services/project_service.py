"""Import/export complet d'une base XMLForge canonique."""
from .export_service import ExportService
from .import_service import ImportService
from .audit_service import AuditService


class ProjectService:
    @staticmethod
    def export_project_to_xml(database_id, user_id=None, user_name=None, ip_address=None):
        # Un projet contient le document canonique complet, y compris données et
        # métadonnées de protection : droit admin requis par ExportService.
        content, error = ExportService.export_database_to_xml(
            database_id, user_id=user_id, user_name=user_name,
            ip_address=ip_address, include_secrets=True,
        )
        if not error and user_id:
            AuditService.log(user_id=user_id, user_name=user_name, ip_address=ip_address,
                             action="EXPORT_PROJECT", element_type="base",
                             element_name=str(database_id))
        return content, error

    @staticmethod
    def import_project_from_xml(xml_content, creator_id=None, creator_name=None, ip_address=None):
        return ImportService.import_xml(
            xml_content=xml_content, database_name=None,
            creator_id=creator_id, creator_name=creator_name,
            description="Import projet XMLForge", ip_address=ip_address,
        )
