"""
Routes Databases - CRUD + liste + V2 métadonnées
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import DatabaseCreateSchema, DatabaseUpdateSchema
from ..utils.responses import success_response, error_response
from ..services.database_service import DatabaseService
from ..services.auth_service import AuthService
from marshmallow import ValidationError

databases_bp = Blueprint('databases', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@databases_bp.route('/databases', methods=['GET'])
@jwt_required()
def list_databases():
    try:
        # ?include_archived=true/false
        include_archived = request.args.get('include_archived', 'true').lower() != 'false'
        dbs = DatabaseService.get_all(include_archived=include_archived)
        data = [db.to_dict(include_key=False) for db in dbs]
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
            ip_address=get_ip()
        )

        return success_response(db_obj.to_dict(include_key=True), "Base créée", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
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

        db_obj, err = DatabaseService.update(db_id, validated, user.id, user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 404 if "introuvable" in err else 400)

        return success_response(db_obj.to_dict(include_key=True), "Base mise à jour")

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
            return error_response(err, 404)

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
        include_key = (db_obj.creator_id == user_id)

        provided_key = request.headers.get('X-Database-Key') or request.args.get('key')
        if provided_key and provided_key == db_obj.key_identifier:
            include_key = True

        return success_response(db_obj.to_dict(include_key=include_key))

    except Exception as e:
        return error_response(str(e), 500)
