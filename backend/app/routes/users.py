"""
Routes Users - V4 admin only (nyx@xmlforge.io)
Gère liste, création, modif, suppression, reset pwd, activation
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.user_service import UserService
from ..services.auth_service import AuthService
from ..auth.decorators import admin_required
from marshmallow import Schema, fields, validate, INCLUDE, ValidationError

users_bp = Blueprint('users', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

class UserCreateSchema(Schema):
    class Meta:
        unknown = INCLUDE
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))
    is_active = fields.Bool(required=False, load_default=True)

class UserUpdateSchema(Schema):
    class Meta:
        unknown = INCLUDE
    full_name = fields.Str(required=False, validate=validate.Length(min=2, max=120))
    email = fields.Email(required=False)
    is_active = fields.Bool(required=False)

class ResetPasswordSchema(Schema):
    class Meta:
        unknown = INCLUDE
    new_password = fields.Str(required=True, validate=validate.Length(min=6, max=128))

@users_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required
def list_users():
    try:
        search = request.args.get('search') or request.args.get('q')
        include_inactive = request.args.get('include_inactive', 'true').lower() != 'false'
        users = UserService.get_all(search=search, include_inactive=include_inactive)
        data = [u.to_dict() for u in users]
        return success_response(data, f"{len(data)} utilisateurs")
    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_user(user_id):
    try:
        user = UserService.get_by_id(user_id)
        if not user:
            return error_response("Utilisateur introuvable", 404)
        return success_response(user.to_dict())
    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users', methods=['POST'])
@jwt_required()
@admin_required
def create_user():
    try:
        admin_id = int(get_jwt_identity())
        admin = AuthService.get_user_by_id(admin_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis", 400)

        schema = UserCreateSchema()
        validated = schema.load(json_data)

        user, err = UserService.create(
            full_name=validated['full_name'],
            email=validated['email'],
            password=validated['password'],
            creator_id=admin.id,
            creator_name=admin.full_name,
            is_active=validated.get('is_active', True),
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(user.to_dict(), "Utilisateur créé", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_user(user_id):
    try:
        admin_id = int(get_jwt_identity())
        admin = AuthService.get_user_by_id(admin_id)

        json_data = request.get_json() or {}
        schema = UserUpdateSchema()
        validated = schema.load(json_data)

        user, err = UserService.update(
            user_id=user_id,
            data=validated,
            updater_id=admin.id,
            updater_name=admin.full_name,
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(user.to_dict(), "Utilisateur mis à jour")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    try:
        admin_id = int(get_jwt_identity())
        admin = AuthService.get_user_by_id(admin_id)

        ok, err = UserService.delete(
            user_id=user_id,
            deleter_id=admin.id,
            deleter_name=admin.full_name,
            ip_address=get_ip()
        )
        if not ok:
            return error_response(err, 400)

        return success_response(None, "Utilisateur supprimé")

    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@jwt_required()
@admin_required
def reset_password(user_id):
    try:
        admin_id = int(get_jwt_identity())
        admin = AuthService.get_user_by_id(admin_id)

        json_data = request.get_json() or {}
        schema = ResetPasswordSchema()
        validated = schema.load(json_data)

        user, err = UserService.reset_password(
            user_id=user_id,
            new_password=validated['new_password'],
            updater_id=admin.id,
            updater_name=admin.full_name,
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(user.to_dict(), "Mot de passe réinitialisé")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@users_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@jwt_required()
@admin_required
def toggle_active(user_id):
    try:
        admin_id = int(get_jwt_identity())
        admin = AuthService.get_user_by_id(admin_id)

        user, err = UserService.toggle_active(
            user_id=user_id,
            updater_id=admin.id,
            updater_name=admin.full_name,
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        status = "activé" if user.is_active else "désactivé"
        return success_response(user.to_dict(), f"Utilisateur {status}")

    except Exception as e:
        return error_response(str(e), 500)
