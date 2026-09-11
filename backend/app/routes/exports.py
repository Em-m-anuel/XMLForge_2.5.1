"""
Routes Export XML / SQL V2 avec IP + audit
+ V4 export par table
"""
from flask import Blueprint, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.export_service import ExportService
from ..services.auth_service import AuthService

exports_bp = Blueprint('exports', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@exports_bp.route('/export/xml/<int:database_id>', methods=['GET'])
@jwt_required()
def export_xml(database_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        xml_content, err = ExportService.export_database_to_xml(database_id, user_id=user.id, user_name=user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 403 if 'Permission' in err else 404)

        if request.args.get('download') == 'true':
            return Response(
                xml_content,
                mimetype='application/xml',
                headers={'Content-Disposition': f'attachment; filename=database_{database_id}.xml'}
            )

        from ..data_plane import get_data_plane
        database = get_data_plane().get_database(database_id)
        return success_response({
            "xml": xml_content, "database_id": database_id,
            "document_version": database.document_version if database else None
        }, "Export XML généré")

    except Exception as e:
        return error_response(str(e), 500)

@exports_bp.route('/export/sql/<int:database_id>', methods=['GET'])
@jwt_required()
def export_sql(database_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        sql_content, err = ExportService.export_database_to_sql(database_id, user_id=user.id, user_name=user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 403 if 'Permission' in err else 404)

        if request.args.get('download') == 'true':
            return Response(
                sql_content,
                mimetype='application/sql',
                headers={'Content-Disposition': f'attachment; filename=database_{database_id}.sql'}
            )

        return success_response({"sql": sql_content, "database_id": database_id}, "Export SQL généré")

    except Exception as e:
        return error_response(str(e), 500)

# ===== V4 : export par table =====
@exports_bp.route('/export/table-xml/<int:table_id>', methods=['GET'])
@jwt_required()
def export_table_xml(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        xml_content, err = ExportService.export_table_to_xml(table_id, user_id=user.id, user_name=user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 403 if 'Permission' in err else 404)

        from ..data_plane import get_data_plane, get_table
        table = get_table(table_id)
        if request.args.get('download') == 'true':
            fname = f"{table.name if table else table_id}.xml"
            return Response(
                xml_content,
                mimetype='application/xml',
                headers={'Content-Disposition': f'attachment; filename={fname}'}
            )
        database = get_data_plane().get_database(table.database_id) if table else None
        return success_response({
            "xml": xml_content, "table_id": table_id,
            "document_version": database.document_version if database else None
        }, "Export XML table généré")

    except Exception as e:
        return error_response(str(e), 500)

@exports_bp.route('/export/table-sql/<int:table_id>', methods=['GET'])
@jwt_required()
def export_table_sql(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        sql_content, err = ExportService.export_table_to_sql(table_id, user_id=user.id, user_name=user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 403 if 'Permission' in err else 404)

        from ..data_plane import get_table
        table = get_table(table_id)
        if request.args.get('download') == 'true':
            fname = f"{table.name if table else table_id}.sql"
            return Response(
                sql_content,
                mimetype='application/sql',
                headers={'Content-Disposition': f'attachment; filename={fname}'}
            )
        return success_response({"sql": sql_content, "table_id": table_id}, "Export SQL table généré")

    except Exception as e:
        return error_response(str(e), 500)

# Alias for compatibility /api/export/table/xml
@exports_bp.route('/export/xml/table/<int:table_id>', methods=['GET'])
@jwt_required()
def export_table_xml_alias(table_id):
    return export_table_xml(table_id)

@exports_bp.route('/export/sql/table/<int:table_id>', methods=['GET'])
@jwt_required()
def export_table_sql_alias(table_id):
    return export_table_sql(table_id)
