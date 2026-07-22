"""
Routes Tables V3 - support file_identifier, protected, archived, comment
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import TableCreateSchema, TableUpdateSchema
from ..utils.responses import success_response, error_response
from ..services.table_service import TableService
from ..services.auth_service import AuthService
from marshmallow import ValidationError

tables_bp = Blueprint('tables', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@tables_bp.route('/tables/<int:database_id>', methods=['GET'])
@jwt_required()
def list_tables(database_id):
    try:
        include_archived = request.args.get('include_archived', 'true').lower() != 'false'
        tbls = TableService.get_by_database(database_id, include_archived=include_archived)
        data = [t.to_dict() for t in tbls]
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)

@tables_bp.route('/tables', methods=['POST'])
@jwt_required()
def create_table():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        schema = TableCreateSchema()
        validated = schema.load(json_data)

        # Gérer alias protected / is_protected et file_identifier / fileIdentifier
        is_protected = validated.get('is_protected', False) or validated.get('protected', False)
        file_identifier = validated.get('file_identifier') or validated.get('fileIdentifier') or json_data.get('file_identifier') or json_data.get('fileIdentifier')

        table, err = TableService.create(
            name=validated['name'],
            description=validated.get('description',''),
            database_id=validated['database_id'],
            creator_id=user.id,
            creator_name=user.full_name,
            is_protected=is_protected,
            file_identifier=file_identifier,
            comment=validated.get('comment') or json_data.get('comment',''),
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(table.to_dict(), "Table créée", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@tables_bp.route('/tables/<int:table_id>', methods=['PUT'])
@jwt_required()
def update_table(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json() or {}
        schema = TableUpdateSchema()
        validated = schema.load(json_data)

        # Normaliser alias
        if 'protected' in validated and 'is_protected' not in validated:
            validated['is_protected'] = validated['protected']
        if 'fileIdentifier' in validated and 'file_identifier' not in validated:
            validated['file_identifier'] = validated['fileIdentifier']

        provided_key = validated.get('key_identifier') or request.headers.get('X-Database-Key')

        table, err = TableService.update(table_id, validated, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip())
        if err:
            status = 403 if "protégée" in err or "Clé" in err else 404 if "introuvable" in err else 400
            return error_response(err, status)

        return success_response(table.to_dict(), "Table mise à jour")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@tables_bp.route('/tables/<int:table_id>', methods=['DELETE'])
@jwt_required()
def delete_table(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        provided_key = request.args.get('key') or request.headers.get('X-Database-Key')
        if request.is_json:
            body = request.get_json(silent=True) or {}
            provided_key = body.get('key_identifier') or provided_key

        ok, err = TableService.delete(table_id, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip())
        if not ok:
            status = 403 if "protégée" in err or "Clé" in err else 404
            return error_response(err, status)

        return success_response(None, "Table supprimée")

    except Exception as e:
        return error_response(str(e), 500)
