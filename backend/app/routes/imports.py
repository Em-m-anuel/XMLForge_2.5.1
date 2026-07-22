"""
Routes Import XML / SQL V2 avec IP + audit
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.import_service import ImportService
from ..services.auth_service import AuthService

imports_bp = Blueprint('imports', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@imports_bp.route('/import/xml', methods=['POST'])
@jwt_required()
def import_xml():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        xml_content = None
        database_name = request.form.get('database_name') or request.form.get('name')
        description = request.form.get('description', 'Import XML')
        comment = request.form.get('comment', '')

        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return error_response("Fichier vide", 400)
            xml_content = file.read().decode('utf-8')
        else:
            json_data = request.get_json(silent=True)
            if json_data:
                xml_content = json_data.get('xml')
                database_name = json_data.get('database_name') or json_data.get('name') or database_name
                description = json_data.get('description', description)
                comment = json_data.get('comment', comment)

        if not xml_content:
            return error_response("Fichier XML ou champ 'xml' requis", 400)

        database, err = ImportService.import_xml(
            xml_content=xml_content,
            database_name=database_name,
            creator_id=user.id,
            creator_name=user.full_name,
            description=description,
            ip_address=get_ip(),
            comment=comment
        )
        if err:
            return error_response(err, 400)

        return success_response(database.to_dict(include_key=True), "Import XML réussi", 201)

    except Exception as e:
        return error_response(str(e), 500)

@imports_bp.route('/import/sql', methods=['POST'])
@jwt_required()
def import_sql():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        sql_content = None
        database_name = request.form.get('database_name') or request.form.get('name')
        description = request.form.get('description', 'Import SQL')
        comment = request.form.get('comment', '')

        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return error_response("Fichier vide", 400)
            sql_content = file.read().decode('utf-8')
        else:
            json_data = request.get_json(silent=True)
            if json_data:
                sql_content = json_data.get('sql')
                database_name = json_data.get('database_name') or json_data.get('name') or database_name
                description = json_data.get('description', description)
                comment = json_data.get('comment', comment)

        if not sql_content:
            return error_response("Fichier SQL ou champ 'sql' requis", 400)

        database, err = ImportService.import_sql(
            sql_content=sql_content,
            database_name=database_name,
            creator_id=user.id,
            creator_name=user.full_name,
            description=description,
            ip_address=get_ip(),
            comment=comment
        )
        if err:
            return error_response(err, 400)

        return success_response(database.to_dict(include_key=True), "Import SQL réussi", 201)

    except Exception as e:
        return error_response(str(e), 500)
