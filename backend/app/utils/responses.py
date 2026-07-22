"""
Réponses JSON cohérentes pour toute l'API
"""
from flask import jsonify

def success_response(data=None, message="OK", status_code=200):
    payload = {
        "success": True,
        "message": message,
        "data": data
    }
    return jsonify(payload), status_code

def error_response(message="Erreur", status_code=400, errors=None):
    payload = {
        "success": False,
        "message": message,
        "errors": errors
    }
    return jsonify(payload), status_code

def paginated_response(items, total, page=1, per_page=20):
    return success_response(data={
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1)//per_page
    })
