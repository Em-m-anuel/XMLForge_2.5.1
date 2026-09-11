"""
Routes Tables V3 - support file_identifier, protected, archived, comment
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import TableCreateSchema, TableUpdateSchema
from ..utils.responses import success_response, error_response
from ..services.table_service import TableService
from ..services.auth_service import AuthService
from ..services.permission_service import PermissionService
from marshmallow import ValidationError

tables_bp = Blueprint('tables', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None


def serialize_table(table, user_id, include_secret=False):
    data = table.to_dict(include_secret=include_secret)
    data["access"] = PermissionService.table_access(user_id, table)
    return data

@tables_bp.route('/tables/<int:database_id>', methods=['GET'])
@jwt_required()
def list_tables(database_id):
    try:
        user_id = int(get_jwt_identity())
        include_archived = request.args.get('include_archived', 'true').lower() != 'false'
        tbls = TableService.get_by_database(database_id, include_archived=include_archived, user_id=user_id)
        data = [serialize_table(table, user_id, include_secret=PermissionService.can_table(user_id, table, 'admin')) for table in tbls]
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)

@tables_bp.route('/tables/<int:table_id>/detail', methods=['GET'])
@jwt_required()
def get_table_detail(table_id):
    table = TableService.get_by_id(table_id)
    if not table:
        return error_response("Table introuvable", 404)
    user_id = int(get_jwt_identity())
    if not PermissionService.can_table(user_id, table, 'read'):
        return error_response("Accès refusé", 403)
    return success_response(serialize_table(table, user_id, include_secret=PermissionService.can_table(user_id, table, 'admin')))


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
            ip_address=get_ip(),
            expected_version=json_data.get('expected_version') or request.headers.get('If-Match')
        )
        if err:
            return error_response(err, 409 if "Conflit" in err else 403 if "Permission" in err or "refusée" in err else 400)

        return success_response(serialize_table(table, user.id), "Table créée", 201)

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

        table, err = TableService.update(table_id, validated, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip(), expected_version=json_data.get('expected_version') or request.headers.get('If-Match'))
        if err:
            status = 409 if "Conflit" in err else 403 if "protégée" in err or "Clé" in err or "Permission" in err or "refusée" in err else 404 if "introuvable" in err else 409 if "Conflit" in err else 400
            return error_response(err, status)

        return success_response(serialize_table(table, user.id), "Table mise à jour")

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

        expected_version = request.headers.get('If-Match')
        ok, err = TableService.delete(table_id, user.id, user.full_name, provided_key=provided_key, ip_address=get_ip(), expected_version=expected_version)
        if not ok:
            status = 409 if "Conflit" in err else 403 if "protégée" in err or "Clé" in err or "Permission" in err or "refusée" in err else 404
            return error_response(err, status)

        return success_response(None, "Table supprimée")

    except Exception as e:
        return error_response(str(e), 500)
