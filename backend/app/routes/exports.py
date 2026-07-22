"""
Routes Export XML / SQL V2 avec IP + audit
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
            return error_response(err, 404)

        if request.args.get('download') == 'true':
            return Response(
                xml_content,
                mimetype='application/xml',
                headers={'Content-Disposition': f'attachment; filename=database_{database_id}.xml'}
            )

        return success_response({"xml": xml_content, "database_id": database_id}, "Export XML généré")

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
            return error_response(err, 404)

        if request.args.get('download') == 'true':
            return Response(
                sql_content,
                mimetype='application/sql',
                headers={'Content-Disposition': f'attachment; filename=database_{database_id}.sql'}
            )

        return success_response({"sql": sql_content, "database_id": database_id}, "Export SQL généré")

    except Exception as e:
        return error_response(str(e), 500)
