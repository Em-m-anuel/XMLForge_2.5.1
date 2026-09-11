"""Décorateurs auth additionnels - V4 admin."""
from functools import wraps
from flask import request
from flask_jwt_extended import get_jwt_identity
from ..data_plane import get_table
from ..utils.responses import error_response


def protected_table_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        table_id = kwargs.get('table_id') or request.view_args.get('table_id')
        if table_id:
            table = get_table(table_id)
            if table and table.is_protected:
                key = request.headers.get('X-Database-Key') or request.args.get('key')
                if request.is_json:
                    body = request.get_json(silent=True) or {}
                    key = body.get('key_identifier') or key
                if not key:
                    return error_response(f"Table {table.name} protégée, clé requise", 403)
                from ..control_plane import get_backend
                db = get_backend().get_database(table.database_id)
                if not db or getattr(db, "key_identifier", None) != key:
                    # Also check file_identifier
                    if table.file_identifier and key == table.file_identifier:
                        pass
                    else:
                        return error_response("Clé invalide", 403)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from ..services.auth_service import AuthService
        try:
            user_id = int(get_jwt_identity())
        except Exception:
            return error_response("Non authentifié", 401)
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return error_response("Utilisateur introuvable", 404)
        if not user.is_admin():
            return error_response("Accès refusé: rôle administrateur requis", 403)
        return f(*args, **kwargs)
    return decorated
