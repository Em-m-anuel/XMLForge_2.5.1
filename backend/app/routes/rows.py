"""
Routes Rows - V4 gestion des données d'une table
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.row_service import RowService
from ..services.auth_service import AuthService

rows_bp = Blueprint('rows', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@rows_bp.route('/tables/<int:table_id>/rows', methods=['GET'])
@jwt_required()
def list_rows(table_id):
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        result, err = RowService.get_by_table(table_id, limit=limit, offset=offset)
        if err:
            return error_response(err, 404)
        return success_response(result)
    except Exception as e:
        return error_response(str(e), 500)

@rows_bp.route('/tables/<int:table_id>/rows', methods=['POST'])
@jwt_required()
def create_row(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        # Accepte soit {data: {...}} soit directement dict
        data_dict = json_data.get('data') if 'data' in json_data else json_data
        # Retirer champs meta comme key_identifier
        provided_key = json_data.get('key_identifier') or request.headers.get('X-Database-Key')

        # Si data contient key_identifier, retirer
        if isinstance(data_dict, dict) and 'key_identifier' in data_dict:
            provided_key = data_dict.pop('key_identifier', provided_key)

        row, err = RowService.create(
            table_id=table_id,
            data_dict=data_dict,
            creator_id=user.id,
            creator_name=user.full_name,
            ip_address=get_ip(),
            provided_key=provided_key
        )
        if err:
            status = 403 if "protégée" in err or "Clé" in err else 400
            return error_response(err, status)

        return success_response(row.to_dict(), "Ligne créée", 201)

    except Exception as e:
        return error_response(str(e), 500)

@rows_bp.route('/tables/<int:table_id>/rows/<int:row_id>', methods=['PUT'])
@jwt_required()
def update_row(table_id, row_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        data_dict = json_data.get('data') if 'data' in json_data else json_data
        provided_key = json_data.get('key_identifier') or request.headers.get('X-Database-Key')

        if isinstance(data_dict, dict) and 'key_identifier' in data_dict:
            provided_key = data_dict.pop('key_identifier', provided_key)

        row, err = RowService.update(
            table_id=table_id,
            row_id=row_id,
            data_dict=data_dict,
            updater_id=user.id,
            updater_name=user.full_name,
            ip_address=get_ip(),
            provided_key=provided_key
        )
        if err:
            status = 403 if "protégée" in err or "Clé" in err else 404 if "introuvable" in err else 400
            return error_response(err, status)

        return success_response(row.to_dict(), "Ligne mise à jour")

    except Exception as e:
        return error_response(str(e), 500)

@rows_bp.route('/tables/<int:table_id>/rows/<int:row_id>', methods=['DELETE'])
@jwt_required()
def delete_row(table_id, row_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        provided_key = request.args.get('key') or request.headers.get('X-Database-Key')
        if request.is_json:
            body = request.get_json(silent=True) or {}
            provided_key = body.get('key_identifier') or provided_key

        ok, err = RowService.delete(
            table_id=table_id,
            row_id=row_id,
            deleter_id=user.id,
            deleter_name=user.full_name,
            ip_address=get_ip(),
            provided_key=provided_key
        )
        if not ok:
            status = 403 if "protégée" in err or "Clé" in err else 404
            return error_response(err, status)

        return success_response(None, "Ligne supprimée")

    except Exception as e:
        return error_response(str(e), 500)
