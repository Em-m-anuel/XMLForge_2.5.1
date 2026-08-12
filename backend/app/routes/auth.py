"""
Routes Auth - V4 avec clear unlocks on logout
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.validators import RegisterSchema, LoginSchema
from ..utils.responses import success_response, error_response
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
from ..services.unlock_service import UnlockService
from marshmallow import ValidationError

auth_bp = Blueprint('auth', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return error_response("JSON requis", 400)

        schema = RegisterSchema()
        validated = schema.load(data)

        user, err = AuthService.register(
            full_name=validated['full_name'],
            email=validated['email'],
            password=validated['password'],
            ip_address=get_ip()
        )
        if err:
            return error_response(err, 400)

        return success_response(user.to_dict(), "Inscription réussie", 201)

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(f"Erreur serveur: {str(e)}", 500)

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return error_response("JSON requis", 400)

        schema = LoginSchema()
        validated = schema.load(data)

        result, err = AuthService.login(validated['email'], validated['password'], ip_address=get_ip())
        if err:
            return error_response(err, 401)

        user = result['user']
        token = result['token']

        return success_response({
            "user": user.to_dict(),
            "access_token": token
        }, "Connexion réussie")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(f"Erreur serveur: {str(e)}", 500)

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(int(user_id))
        if not user:
            return error_response("Utilisateur introuvable", 404)
        return success_response(user.to_dict())
    except Exception as e:
        return error_response(str(e), 500)

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(int(user_id))
        # V4: clear personal unlocks on logout
        try:
            UnlockService.clear_user_unlocks(int(user_id))
        except Exception:
            pass
        AuditService.log(
            user_id=user.id if user else None,
            user_name=user.full_name if user else None,
            ip_address=get_ip(),
            action="DECONNEXION",
            element_type="auth",
            element_name=user.email if user else "unknown",
            description="Déconnexion - unlocks effacés"
        )
        return success_response(None, "Déconnexion réussie - supprimez le token côté client")
    except Exception as e:
        return error_response(str(e), 500)
