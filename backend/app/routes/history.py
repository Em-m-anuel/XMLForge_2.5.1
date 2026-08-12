"""
Route History - V4 admin only (nyx@xmlforge.io)
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from ..utils.responses import success_response, error_response
from ..services.history_service import HistoryService
from ..auth.decorators import admin_required

history_bp = Blueprint('history', __name__)

@history_bp.route('/history', methods=['GET'])
@jwt_required()
@admin_required
def get_history():
    try:
        limit = int(request.args.get('limit', 100))
        database_id = request.args.get('database_id')
        if database_id:
            try:
                database_id = int(database_id)
            except:
                database_id = None

        limit = min(limit, 500)

        entries = HistoryService.get_all(limit=limit, database_id=database_id)
        data = [e.to_dict() for e in entries]

        return success_response(data, f"{len(data)} événements")

    except Exception as e:
        return error_response(str(e), 500)
