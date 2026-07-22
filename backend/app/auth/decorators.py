"""
Décorateurs auth additionnels
"""
from functools import wraps
from flask import request
from flask_jwt_extended import get_jwt_identity
from ..models.table import Table
from ..models.database import Database

def protected_table_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Vérifie si table protégée et clé fournie
        table_id = kwargs.get('table_id') or request.view_args.get('table_id')
        if table_id:
            table = Table.query.get(table_id)
            if table and table.is_protected:
                key = request.headers.get('X-Database-Key') or request.args.get('key')
                if request.is_json:
                    body = request.get_json(silent=True) or {}
                    key = body.get('key_identifier') or key
                if not key:
                    return {"success": False, "message": f"Table {table.name} protégée, clé requise"}, 403
                db = Database.query.get(table.database_id)
                if not db or db.key_identifier != key:
                    return {"success": False, "message": "Clé invalide"}, 403
        return f(*args, **kwargs)
    return decorated
