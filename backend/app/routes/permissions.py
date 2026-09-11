"""Partage des bases et permissions backend."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.permission_service import PermissionService
from ..services.user_service import UserService

permissions_bp = Blueprint("permissions", __name__)


@permissions_bp.route('/databases/<int:database_id>/permissions', methods=['GET'])
@jwt_required()
def list_permissions(database_id):
    items, error = PermissionService.list_database_permissions(int(get_jwt_identity()), database_id)
    if error: return error_response(error, 403 if "Permission" in error else 404)
    return success_response([item.to_dict() for item in items])


@permissions_bp.route('/databases/<int:database_id>/permissions', methods=['POST'])
@jwt_required()
def grant_permission(database_id):
    data = request.get_json(silent=True) or {}
    target_user = UserService.get_by_id(data.get('user_id')) if data.get('user_id') else UserService.get_by_email(data.get('email', ''))
    if not target_user:
        return error_response("Utilisateur cible introuvable (user_id ou email requis)", 404)
    rights = {key: data[key] for key in ('can_read', 'can_write', 'can_ddl', 'can_admin') if key in data}
    item, error = PermissionService.grant_database(
        int(get_jwt_identity()), database_id, target_user.id, rights
    )
    if error: return error_response(error, 403 if "Permission" in error else 400)
    return success_response(item.to_dict(), "Permission enregistrée", 201)


@permissions_bp.route('/databases/<int:database_id>/permissions/<int:user_id>', methods=['DELETE'])
@jwt_required()
def revoke_permission(database_id, user_id):
    ok, error = PermissionService.revoke_database(int(get_jwt_identity()), database_id, user_id)
    if not ok: return error_response(error, 403 if "Permission" in error else 404)
    return success_response(None, "Permission révoquée")


@permissions_bp.route('/tables/<int:table_id>/permissions', methods=['GET'])
@jwt_required()
def list_table_permissions(table_id):
    items, error = PermissionService.list_table_permissions(int(get_jwt_identity()), table_id)
    if error:
        return error_response(error, 403 if "Permission" in error else 404)
    return success_response([item.to_dict() for item in items])


@permissions_bp.route('/tables/<int:table_id>/permissions', methods=['POST'])
@jwt_required()
def grant_table_permission(table_id):
    data = request.get_json(silent=True) or {}
    target_user = UserService.get_by_id(data.get('user_id')) if data.get('user_id') else UserService.get_by_email(data.get('email', ''))
    if not target_user:
        return error_response("Utilisateur cible introuvable (user_id ou email requis)", 404)
    rights = {key: data[key] for key in ('can_read', 'can_write', 'can_ddl', 'can_admin') if key in data}
    item, error = PermissionService.grant_table(int(get_jwt_identity()), table_id, target_user.id, rights)
    if error: return error_response(error, 403 if "Permission" in error else 400)
    return success_response(item.to_dict(), "Permission table enregistrée", 201)


@permissions_bp.route('/tables/<int:table_id>/permissions/<int:user_id>', methods=['DELETE'])
@jwt_required()
def revoke_table_permission(table_id, user_id):
    ok, error = PermissionService.revoke_table(int(get_jwt_identity()), table_id, user_id)
    if not ok:
        return error_response(error, 403 if "Permission" in error else 404)
    return success_response(None, "Permission table révoquée")
