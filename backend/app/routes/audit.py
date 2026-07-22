"""
Routes AuditLog - audit indépendant
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from ..utils.responses import success_response, error_response
from ..services.audit_service import AuditService

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def get_audit_logs():
    try:
        limit = int(request.args.get('limit', 100))
        limit = min(limit, 500)
        logs = AuditService.get_all(limit=limit)
        data = [l.to_dict() for l in logs]
        return success_response(data, f"{len(data)} logs d'audit")
    except Exception as e:
        return error_response(str(e), 500)

@audit_bp.route('/audit', methods=['GET'])
@jwt_required()
def get_audit_alias():
    # Alias pour /audit-logs
    return get_audit_logs()
