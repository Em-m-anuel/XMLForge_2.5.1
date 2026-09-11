"""
Routes Project - Export/Import complet d'un projet XMLForge
"""
from flask import Blueprint, request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.project_service import ProjectService
from ..services.auth_service import AuthService

projects_bp = Blueprint('projects', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@projects_bp.route('/export/project/<int:database_id>', methods=['GET'])
@jwt_required()
def export_project(database_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        xml_content, err = ProjectService.export_project_to_xml(
            database_id=database_id,
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 403 if 'Permission' in err else 404)

        if request.args.get('download') == 'true':
            return Response(
                xml_content,
                mimetype='application/xml',
                headers={'Content-Disposition': f'attachment; filename=project_{database_id}.xml'}
            )

        return success_response({"xml": xml_content, "database_id": database_id}, "Export projet complet généré")

    except Exception as e:
        return error_response(str(e), 500)

@projects_bp.route('/import/project', methods=['POST'])
@jwt_required()
def import_project():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        # Support multipart file ou JSON xml
        xml_content = None
        if request.files and 'file' in request.files:
            file = request.files['file']
            xml_content = file.read().decode('utf-8')
        else:
            json_data = request.get_json(silent=True)
            if json_data and 'xml' in json_data:
                xml_content = json_data['xml']

        if not xml_content:
            return error_response("Fichier XML ou champ 'xml' requis", 400)

        database, err = ProjectService.import_project_from_xml(
            xml_content=xml_content,
            creator_id=user.id,
            creator_name=user.full_name,
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(database.to_dict(include_key=True), "Projet importé avec succès", 201)

    except Exception as e:
        return error_response(str(e), 500)
