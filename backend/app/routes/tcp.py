"""
Routes pour la gestion des credentials TCP/IP
"""
from flask import Blueprint, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services.auth_service import AuthService
from ..services.tcp_credential_service import TcpCredentialService
from ..utils.responses import success_response, error_response

tcp_bp = Blueprint('tcp', __name__, url_prefix='/api/tcp')


@tcp_bp.route('/credentials', methods=['GET'])
@jwt_required()
def get_tcp_credentials():
    """Retourne les credentials TCP pour l'utilisateur actuel"""
    user_id = get_jwt_identity()
    
    try:
        credential = TcpCredentialService.get_by_user_id(user_id)
        
        if not credential:
            # Créer automatiquement des credentials s'ils n'existent pas
            result, error = TcpCredentialService.create_for_user(user_id)
            if error:
                return error_response(error, 400)
            # Le secret généré ne peut être relu depuis son hash : le rendre une
            # seule fois lors de la création automatique.
            return success_response(result, "Credentials créés; conservez le mot de passe affiché une seule fois")
        return success_response(credential.to_dict(), "Credentials récupérés")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/credentials', methods=['POST'])
@jwt_required()
def create_tcp_credentials():
    """Crée des credentials TCP pour l'utilisateur"""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    
    try:
        tcp_username = data.get('tcp_username')
        tcp_password = data.get('tcp_password')
        tcp_host = data.get('tcp_host', '127.0.0.1')
        tcp_port = data.get('tcp_port', 3307)
        
        result, error = TcpCredentialService.create_for_user(
            user_id, tcp_username, tcp_password, tcp_host, tcp_port
        )
        
        if error:
            return error_response(error, 400)
        
        return success_response(result, "Credentials TCP créés avec succès")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/credentials', methods=['PUT'])
@jwt_required()
def update_tcp_credentials():
    """Met à jour les credentials TCP de l'utilisateur"""
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    
    try:
        tcp_username = data.get('tcp_username')
        tcp_password = data.get('tcp_password')
        tcp_host = data.get('tcp_host')
        tcp_port = data.get('tcp_port')
        
        result, error = TcpCredentialService.update_for_user(
            user_id, tcp_username, tcp_password, tcp_host, tcp_port
        )
        
        if error:
            return error_response(error, 404)
        
        return success_response(result, "Credentials TCP mis à jour")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/credentials/regenerate', methods=['POST'])
@jwt_required()
def regenerate_tcp_password():
    """Régénère le mot de passe TCP"""
    user_id = get_jwt_identity()
    
    try:
        result, error = TcpCredentialService.regenerate_password(user_id)
        
        if error:
            return error_response(error, 404)
        
        return success_response(result, "Mot de passe TCP régénéré")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/credentials', methods=['DELETE'])
@jwt_required()
def delete_tcp_credentials():
    """Supprime les credentials TCP de l'utilisateur"""
    user_id = get_jwt_identity()
    
    try:
        result, error = TcpCredentialService.delete_for_user(user_id)
        
        if error:
            return error_response(error, 404)
        
        return success_response(None, "Credentials TCP supprimés")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/credentials/show-password', methods=['POST'])
@jwt_required()
def show_tcp_password():
    """Retourne le mot de passe TCP en clair (pour copier)
    Nécessite une confirmation du mot de passe XMLForge actuel
    """
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    
    try:
        from ..control_plane import get_backend

        user = get_backend().get_user(user_id)
        if not user:
            return error_response("Utilisateur non trouvé", 404)
        
        # Vérifier le mot de passe XMLForge fourni
        current_password = data.get('current_password')
        if not current_password:
            return error_response("Mot de passe requis", 400)
        
        if not AuthService.verify_password(user, current_password):
            return error_response("Mot de passe incorrect", 401)
        
        # Récupérer les credentials TCP
        credential = TcpCredentialService.get_by_user_id(user_id)
        if not credential:
            return error_response("Credentials TCP introuvables", 404)
        
        # Régénérer et retourner le mot de passe
        result, error = TcpCredentialService.regenerate_password(user_id)
        if error:
            return error_response(error, 404)
        
        credentials = {
            'tcp_host': credential.tcp_host,
            'tcp_port': credential.tcp_port,
            'username': credential.tcp_username,
            'password': result['plain_password'],
            'connection_string': f"xmlforge://{credential.tcp_username}:{result['plain_password']}@{credential.tcp_host}:{credential.tcp_port}"
        }
        
        return success_response(credentials, "Credentials TCP complets")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/sessions', methods=['GET'])
@jwt_required()
def get_tcp_sessions():
    """Retourne les sessions TCP actives de l'utilisateur"""
    user_id = get_jwt_identity()
    
    try:
        tcp_server = current_app.tcp_server
        if not tcp_server:
            return error_response("Serveur TCP non disponible", 503)
        
        all_sessions = tcp_server.get_sessions_info()
        
        # Filtrer les sessions de l'utilisateur
        user_sessions = [s for s in all_sessions if int(s['user_id']) == int(user_id)]
        
        return success_response({
            'sessions': user_sessions,
            'count': len(user_sessions)
        }, "Sessions TCP récupérées")
    
    except Exception as e:
        return error_response(str(e), 500)


@tcp_bp.route('/status', methods=['GET'])
def get_tcp_server_status():
    """Retourne l'état du serveur TCP"""
    try:
        tcp_server = current_app.tcp_server
        if not tcp_server:
            return success_response({
                'running': False,
                'port': 3307,
                'message': 'Serveur TCP non initialisé'
            }, "État du serveur TCP")
        
        status = {
            'running': tcp_server.running,
            'host': tcp_server.host,
            'port': tcp_server.port,
            'active_sessions': len(tcp_server.sessions)
        }
        
        return success_response(status, "État du serveur TCP")
    
    except Exception as e:
        return error_response(str(e), 500)
