"""
Route Sync XML - XML devient source de vérité
POST /databases/<id>/sync-xml  (sync full base)
POST /tables/<id>/sync-xml      (V4 : sync une seule table, exigence maquette)
Body: {xml: "<database>...</database>" ou "<table>...</table>"}
Headers: Authorization Bearer + optionnel X-Database-Key pour tables protégées
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..services.sync_service import SyncService
from ..services.auth_service import AuthService

sync_bp = Blueprint('sync', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@sync_bp.route('/databases/<int:database_id>/sync-xml', methods=['POST'])
@jwt_required()
def sync_database_xml(database_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return error_response("Utilisateur introuvable", 404)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON avec champ 'xml' requis", 400)

        xml_content = json_data.get('xml')
        if not xml_content:
            return error_response("Champ 'xml' requis", 400)

        provided_key = json_data.get('key_identifier') or request.headers.get('X-Database-Key')

        result, err = SyncService.sync_database_from_xml(
            database_id=database_id,
            xml_content=xml_content,
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip(),
            provided_key=provided_key
        )

        if err:
            return error_response(err, 400)

        return success_response(result, "Synchronisation XML réussie - base logique mise à jour, SQL régénéré depuis structure enregistrée")

    except Exception as e:
        return error_response(str(e), 500)

@sync_bp.route('/databases/<int:database_id>/sync', methods=['POST'])
@jwt_required()
def sync_database_alias(database_id):
    return sync_database_xml(database_id)

# ===== V4 : Sync par table (éditeur XML par table) =====
@sync_bp.route('/tables/<int:table_id>/sync-xml', methods=['POST'])
@jwt_required()
def sync_table_xml(table_id):
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)
        if not user:
            return error_response("Utilisateur introuvable", 404)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON avec champ 'xml' requis", 400)

        xml_content = json_data.get('xml')
        if not xml_content:
            return error_response("Champ 'xml' requis", 400)

        provided_key = json_data.get('key_identifier') or json_data.get('file_identifier') or request.headers.get('X-Database-Key')

        result, err = SyncService.sync_table_from_xml(
            table_id=table_id,
            xml_content=xml_content,
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip(),
            provided_key=provided_key
        )

        if err:
            # 403 si protection
            status = 403 if "protégée" in err or "Clé" in err else 400
            return error_response(err, status)

        return success_response(result, "Synchronisation XML table réussie - seule la table sélectionnée a été modifiée")

    except Exception as e:
        return error_response(str(e), 500)

@sync_bp.route('/tables/<int:table_id>/sync', methods=['POST'])
@jwt_required()
def sync_table_alias(table_id):
    return sync_table_xml(table_id)
