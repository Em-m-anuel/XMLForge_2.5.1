"""
Routes Databases - CRUD + liste + V2 métadonnées
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import DatabaseCreateSchema, DatabaseUpdateSchema
from ..utils.responses import success_response, error_response
from ..services.database_service import DatabaseService
from ..services.auth_service import AuthService
from ..services.permission_service import PermissionService
from marshmallow import ValidationError

databases_bp = Blueprint('databases', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None


def serialize_database(database, user_id, include_key=False):
    data = database.to_dict(include_key=include_key)
    data["access"] = PermissionService.database_access(user_id, database)
    data["is_owner"] = PermissionService.is_owner(user_id, database)
    return data

@databases_bp.route('/databases', methods=['GET'])
@jwt_required()
def list_databases():
    try:
        user_id = int(get_jwt_identity())
        include_archived = request.args.get('include_archived', 'true').lower() != 'false'
        dbs = DatabaseService.get_all(include_archived=include_archived, user_id=user_id)
        data = [serialize_database(db_obj, user_id, include_key=False) for db_obj in dbs]
        return success_response(data)
    except Exception as e:
        return error_response(str(e), 500)

@databases_bp.route('/databases', methods=['POST'])
@jwt_required()
def create_database():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return error_response("Utilisateur introuvable", 404)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        schema = DatabaseCreateSchema()
        validated = schema.load(json_data)

        db_obj = DatabaseService.create(
            name=validated['name'],
            description=validated.get('description',''),
            creator_id=user.id,
            creator_name=user.full_name,
            comment=validated.get('comment','') if 'comment' in validated else json_data.get('comment',''),
            ip_address=get_ip(),
            scope=json_data.get('scope', 'PERSONAL'),
            common_permission=json_data.get('common_permission'),
        )

        return success_response(serialize_database(db_obj, user.id, include_key=True), "Base créée", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception as e:
        return error_response(str(e), 500)

@databases_bp.route('/databases/<int:db_id>', methods=['PUT'])
@jwt_required()
def update_database(db_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json() or {}
        schema = DatabaseUpdateSchema()
        validated = schema.load(json_data)

        # Permettre comment via même route pour compat
        if 'comment' in json_data:
            validated['comment'] = json_data['comment']

        if 'scope' in json_data:
            validated['scope'] = json_data['scope']
        if 'common_permission' in json_data:
            validated['common_permission'] = json_data['common_permission']
        expected_version = json_data.get('expected_version') or request.headers.get('If-Match')
        db_obj, err = DatabaseService.update(db_id, validated, user.id, user.full_name, ip_address=get_ip(), expected_version=expected_version)
        if err:
            status = 404 if "introuvable" in err else 403 if "Permission" in err or "refusée" in err else 409 if "Conflit" in err else 400
            return error_response(err, status)

        return success_response(
            serialize_database(db_obj, user.id, include_key=PermissionService.can_database(user.id, db_obj, 'admin')),
            "Base mise à jour"
        )

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@databases_bp.route('/databases/<int:db_id>', methods=['DELETE'])
@jwt_required()
def delete_database(db_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        ok, err = DatabaseService.delete(db_id, user.id, user.full_name, ip_address=get_ip())
        if not ok:
            return error_response(err, 403 if "Permission" in err else 404)

        return success_response(None, "Base supprimée")

    except Exception as e:
        return error_response(str(e), 500)

@databases_bp.route('/databases/<int:db_id>', methods=['GET'])
@jwt_required()
def get_database(db_id):
    try:
        db_obj = DatabaseService.get_by_id(db_id)
        if not db_obj:
            return error_response("Base introuvable", 404)

        user_id = int(get_jwt_identity())
        if not PermissionService.can_database(user_id, db_obj, 'read'):
            return error_response("Accès refusé", 403)
        include_key = PermissionService.can_database(user_id, db_obj, 'admin')
        return success_response(serialize_database(db_obj, user_id, include_key=include_key))

    except Exception as e:
        return error_response(str(e), 500)
