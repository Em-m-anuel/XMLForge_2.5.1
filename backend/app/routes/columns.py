"""
Routes Columns V2
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import ColumnCreateSchema, ColumnUpdateSchema
from ..utils.responses import success_response, error_response
from ..services.column_service import ColumnService
from ..services.auth_service import AuthService
from marshmallow import ValidationError

columns_bp = Blueprint('columns', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@columns_bp.route('/columns/<int:table_id>', methods=['GET'])
@jwt_required()
def list_columns(table_id):
    try:
        include_archived = request.args.get('include_archived', 'true').lower() != 'false'
        cols = ColumnService.get_by_table(table_id, include_archived=include_archived)
        data = [c.to_dict() for c in cols]
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)

@columns_bp.route('/columns', methods=['POST'])
@jwt_required()
def create_column():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        schema = ColumnCreateSchema()
        validated = schema.load(json_data)

        provided_key = validated.get('key_identifier') or request.headers.get('X-Database-Key') or json_data.get('key_identifier')

        col, err = ColumnService.create(validated, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip())
        if err:
            status = 403 if "protégée" in err or "Clé" in err else 400
            return error_response(err, status)

        return success_response(col.to_dict(), "Colonne créée", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@columns_bp.route('/columns/<int:col_id>', methods=['PUT'])
@jwt_required()
def update_column(col_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json() or {}
        schema = ColumnUpdateSchema()
        validated = schema.load(json_data)

        provided_key = validated.get('key_identifier') or request.headers.get('X-Database-Key')

        col, err = ColumnService.update(col_id, validated, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip())
        if err:
            status = 403 if "protégée" in err or "Clé" in err else 404
            return error_response(err, status)

        return success_response(col.to_dict(), "Colonne mise à jour")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@columns_bp.route('/columns/<int:col_id>', methods=['DELETE'])
@jwt_required()
def delete_column(col_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        provided_key = request.args.get('key') or request.headers.get('X-Database-Key')
        if request.is_json:
            body = request.get_json(silent=True) or {}
            provided_key = body.get('key_identifier') or provided_key

        ok, err = ColumnService.delete(col_id, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip())
        if not ok:
            status = 403 if "protégée" in err or "Clé" in err else 404
            return error_response(err, status)

        return success_response(None, "Colonne supprimée")

    except Exception as e:
        return error_response(str(e), 500)
