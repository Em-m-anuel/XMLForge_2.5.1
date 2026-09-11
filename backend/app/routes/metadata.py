"""
Routes V2 - Métadonnées enrichies: commentaires, état (archive/restore)
Conserve compatibilité, ajoute nouvelles fonctionnalités sans casser l'existant
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.database_service import DatabaseService
from ..services.table_service import TableService
from ..services.auth_service import AuthService
from ..services.permission_service import PermissionService

metadata_bp = Blueprint('metadata', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

# ------------------- COMMENTAIRES -------------------

@metadata_bp.route('/databases/<int:db_id>/comment', methods=['GET'])
@jwt_required()
def get_db_comment(db_id):
    try:
        db = DatabaseService.get_by_id(db_id)
        if not db:
            return error_response("Base introuvable", 404)
        if not PermissionService.can_database(int(get_jwt_identity()), db, 'read'):
            return error_response("Accès refusé", 403)
        return success_response({"comment": db.comment or "", "database_id": db.id, "uuid": db.uuid})
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/databases/<int:db_id>/comment', methods=['PUT'])
@jwt_required()
def put_db_comment(db_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json() or {}
        comment = data.get('comment', '')
        db_obj, err = DatabaseService.update_comment(db_id, comment, user.id, user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 400 if "archivée" not in err else 403)
        return success_response({"comment": db_obj.comment, "database_id": db_obj.id}, "Commentaire mis à jour")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/tables/<int:table_id>/comment', methods=['GET'])
@jwt_required()
def get_table_comment(table_id):
    try:
        table = TableService.get_by_id(table_id)
        if not table:
            return error_response("Table introuvable", 404)
        if not PermissionService.can_table(int(get_jwt_identity()), table, 'read'):
            return error_response("Accès refusé", 403)
        return success_response({"comment": table.comment or "", "table_id": table.id, "uuid": table.uuid})
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/tables/<int:table_id>/comment', methods=['PUT'])
@jwt_required()
def put_table_comment(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json() or {}
        comment = data.get('comment','')
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        table, err = TableService.update_comment(table_id, comment, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err or "archivée" in err else 404
            return error_response(err, status)
        return success_response({"comment": table.comment, "table_id": table.id}, "Commentaire mis à jour")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/columns/<int:col_id>/comment', methods=['GET'])
@jwt_required()
def get_column_comment(col_id):
    try:
        from ..services.column_service import ColumnService
        col = ColumnService.get_by_id(col_id)
        if not col:
            return error_response("Colonne introuvable", 404)
        if not PermissionService.can_table(int(get_jwt_identity()), col.table_id, 'read'):
            return error_response("Accès refusé", 403)
        return success_response({"comment": col.comment or "", "column_id": col.id, "uuid": col.uuid})
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/columns/<int:col_id>/comment', methods=['PUT'])
@jwt_required()
def put_column_comment(col_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json() or {}
        comment = data.get('comment','')
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        from ..services.column_service import ColumnService
        col, err = ColumnService.update_comment(col_id, comment, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err or "archivée" in err else 404
            return error_response(err, status)
        return success_response({"comment": col.comment, "column_id": col.id}, "Commentaire mis à jour")
    except Exception as e:
        return error_response(str(e), 500)

# ------------------- ARCHIVE / RESTORE -------------------

@metadata_bp.route('/databases/<int:db_id>/archive', methods=['POST'])
@jwt_required()
def archive_database(db_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        db_obj, err = DatabaseService.archive(db_id, user.id, user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 400)
        return success_response(db_obj.to_dict(), "Base archivée")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/databases/<int:db_id>/restore', methods=['POST'])
@jwt_required()
def restore_database(db_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        db_obj, err = DatabaseService.restore(db_id, user.id, user.full_name, ip_address=get_ip())
        if err:
            return error_response(err, 400)
        return success_response(db_obj.to_dict(), "Base restaurée")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/tables/<int:table_id>/archive', methods=['POST'])
@jwt_required()
def archive_table(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json(silent=True) or {}
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        table, err = TableService.archive(table_id, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err else 400
            return error_response(err, status)
        return success_response(table.to_dict(), "Table archivée")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/tables/<int:table_id>/restore', methods=['POST'])
@jwt_required()
def restore_table(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json(silent=True) or {}
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        table, err = TableService.restore(table_id, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err else 400
            return error_response(err, status)
        return success_response(table.to_dict(), "Table restaurée")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/columns/<int:col_id>/archive', methods=['POST'])
@jwt_required()
def archive_column(col_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json(silent=True) or {}
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        from ..services.column_service import ColumnService
        col, err = ColumnService.archive(col_id, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err else 400
            return error_response(err, status)
        return success_response(col.to_dict(), "Colonne archivée")
    except Exception as e:
        return error_response(str(e), 500)

@metadata_bp.route('/columns/<int:col_id>/restore', methods=['POST'])
@jwt_required()
def restore_column(col_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        data = request.get_json(silent=True) or {}
        key = data.get('key_identifier') or request.headers.get('X-Database-Key')
        from ..services.column_service import ColumnService
        col, err = ColumnService.restore(col_id, user.id, user.full_name, ip_address=get_ip(), provided_key=key)
        if err:
            status = 403 if "protégée" in err else 400
            return error_response(err, status)
        return success_response(col.to_dict(), "Colonne restaurée")
    except Exception as e:
        return error_response(str(e), 500)
