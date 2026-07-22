"""
Route Unlock Table V2 avec IP + audit
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import UnlockTableSchema
from ..utils.responses import success_response, error_response
from ..services.table_service import TableService
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
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

        ok, msg = TableService.unlock(validated['table_id'], validated['key_identifier'])
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
            description=f"Table {validated['table_id']} déverrouillée",
            meta={"table_id": validated['table_id']}
        )

        return success_response({"unlocked": True, "table_id": validated['table_id']}, msg)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)
