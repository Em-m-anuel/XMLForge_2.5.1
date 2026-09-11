"""Endpoint du sous-ensemble SQL commun à REST et TCP (moteur XML)."""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..query.xml_query_service import XmlQueryService

query_bp = Blueprint("query", __name__)


@query_bp.route('/databases/<int:database_id>/query', methods=['POST'])
@jwt_required()
def execute_query(database_id):
    data = request.get_json(silent=True) or {}
    sql = data.get('sql') or data.get('query')
    if not sql:
        return error_response("Champ sql requis", 400)
    provided_key = data.get('key_identifier') or request.headers.get('X-Database-Key')
    expected_version = data.get('expected_version') or request.headers.get('If-Match')
    try:
        result = XmlQueryService.execute_sql(
            database_id, int(get_jwt_identity()), sql,
            provided_key=provided_key, expected_version=expected_version,
        )
        return success_response(result, "Requête exécutée via le moteur XML")
    except Exception as exc:
        status = getattr(exc, 'status_code', 400)
        return error_response(str(exc), status, {"code": getattr(exc, 'code', 'QUERY_ERROR')})


@query_bp.route('/databases/<int:database_id>/schema', methods=['GET'])
@jwt_required()
def get_database_schema(database_id):
    """Introspection du schéma réel (basée sur le XML)."""
    try:
        from ..services.schema_service import SchemaService
        schema = SchemaService.get(database_id, int(get_jwt_identity()))
        return success_response(schema, "Schéma récupéré")
    except Exception as exc:
        status = getattr(exc, 'status_code', 400)
        return error_response(str(exc), status, {"code": getattr(exc, 'code', 'SCHEMA_ERROR')})
