"""
Route Unlock Table V4 - déverrouillage personnel par utilisateur/session
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import UnlockTableSchema
from ..utils.responses import success_response, error_response
from ..services.table_service import TableService
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
from ..services.unlock_service import UnlockService
from marshmallow import ValidationError

unlock_bp = Blueprint('unlock', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@unlock_bp.route('/unlock-table', methods=['POST'])
@jwt_required()
def unlock_table():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON requis avec table_id et key_identifier", 400)

        schema = UnlockTableSchema()
        validated = schema.load(json_data)

        # V4: unlock personnel
        ok, msg = TableService.unlock(validated['table_id'], validated['key_identifier'], user_id=user_id)
        if not ok:
            AuditService.log(
                user_id=user.id,
                user_name=user.full_name,
                ip_address=get_ip(),
                action="ERREUR_DEVERROUILLAGE",
                element_type="table",
                element_name=str(validated['table_id']),
                description=f"Tentative unlock échouée: {msg}"
            )
            return error_response(msg, 403)

        AuditService.log(
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip(),
            action="DEVERROUILLAGE_TABLE",
            element_type="table",
            element_name=str(validated['table_id']),
            description=f"Table {validated['table_id']} déverrouillée pour user {user.email}",
            meta={"table_id": validated['table_id'], "user_id": user_id}
        )

        return success_response({"unlocked": True, "table_id": validated['table_id'], "personal": True}, msg)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@unlock_bp.route('/unlocks', methods=['GET'])
@jwt_required()
def list_unlocks():
    try:
        user_id = int(get_jwt_identity())
        unlocks = UnlockService.list_user_unlocks(user_id)
        data = [u.to_dict() for u in unlocks]
        return success_response(data, f"{len(data)} tables déverrouillées pour votre session")
    except Exception as e:
        return error_response(str(e), 500)

@unlock_bp.route('/unlocks', methods=['DELETE'])
@jwt_required()
def clear_unlocks():
    try:
        user_id = int(get_jwt_identity())
        UnlockService.clear_user_unlocks(user_id)
        return success_response(None, "Tous les déverrouillages effacés pour votre session")
    except Exception as e:
        return error_response(str(e), 500)
