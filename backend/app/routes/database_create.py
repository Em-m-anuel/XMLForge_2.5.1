"""
Route POST /database/create - création réelle MySQL V2 avec audit + IP
"""
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.export_service import ExportService
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
import mysql.connector
from mysql.connector import Error

db_create_bp = Blueprint('db_create', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@db_create_bp.route('/database/create', methods=['POST'])
@jwt_required()
def create_real_database():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON avec database_id requis", 400)

        database_id = json_data.get('database_id')
        if not database_id:
            return error_response("database_id requis", 400)

        sql_content, err = ExportService.export_database_to_sql(database_id)
        if err:
            return error_response(err, 404)

        host = current_app.config.get('MYSQL_HOST', 'localhost')
        port = current_app.config.get('MYSQL_PORT', 3306)
        user_db = current_app.config.get('MYSQL_USER', 'root')
        password = current_app.config.get('MYSQL_PASSWORD', '')
        target_db_name = json_data.get('target_database_name')

        if not target_db_name:
            from ..services.database_service import DatabaseService
            db_obj = DatabaseService.get_by_id(database_id)
            if not db_obj:
                return error_response("Base logique introuvable", 404)
            import re
            target_db_name = re.sub(r'[^a-zA-Z0-9_]+', '_', db_obj.name).lower()[:64]
            if not target_db_name:
                target_db_name = f"xmlforge_{database_id}"

        try:
            conn = mysql.connector.connect(host=host, port=port, user=user_db, password=password)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{target_db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute(f"USE `{target_db_name}`;")

            import re
            sql_filtered = re.sub(r'CREATE\s+DATABASE.*?;', '', sql_content, flags=re.IGNORECASE | re.DOTALL)
            sql_filtered = re.sub(r'USE\s+`?.*?`?\s*;', '', sql_filtered, flags=re.IGNORECASE)

            statements = [s.strip() for s in sql_filtered.split(';') if s.strip()]

            executed = 0
            errors = []
            for stmt in statements:
                if not stmt:
                    continue
                try:
                    cursor.execute(stmt + ';')
                    executed += 1
                except Error as e:
                    errors.append(f"{str(e)} in: {stmt[:80]}...")

            conn.commit()
            cursor.close()
            conn.close()

            AuditService.log(
                user_id=user.id,
                user_name=user.full_name,
                ip_address=get_ip(),
                action="CREATION_REELLE_BASE",
                element_type="base",
                element_name=target_db_name,
                description=f"Création réelle MySQL {target_db_name} avec {executed} tables",
                meta={"database_id": database_id, "target": target_db_name, "executed": executed}
            )

            return success_response({
                "target_database": target_db_name,
                "executed_statements": executed,
                "errors": errors,
                "sql_preview": sql_content[:2000]
            }, f"Base MySQL réelle '{target_db_name}' créée avec {executed} tables")

        except Error as e:
            AuditService.log(
                user_id=user.id,
                user_name=user.full_name,
                ip_address=get_ip(),
                action="ERREUR_CREATION_REELLE",
                element_type="base",
                element_name=target_db_name,
                description=str(e),
                meta={"database_id": database_id}
            )
            return error_response(f"Erreur MySQL ({host}:{port} user={user_db}): {str(e)}. Vérifiez .env MYSQL_*", 500, errors={"sql": sql_content[:2000]})
        except Exception as e:
            return error_response(f"Erreur création réelle: {str(e)}", 500)

    except Exception as e:
        return error_response(str(e), 500)
