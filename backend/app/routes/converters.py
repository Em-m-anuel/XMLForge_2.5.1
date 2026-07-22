"""
Routes Conversion XML <-> SQL V2 avec audit IP
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..utils.responses import success_response, error_response
from ..converters import convert_xml_to_sql, convert_sql_to_xml
from ..utils.validators import ConvertXmlToSqlSchema, ConvertSqlToXmlSchema
from ..services.audit_service import AuditService
from ..services.auth_service import AuthService
from marshmallow import ValidationError

converters_bp = Blueprint('converters', __name__)

def get_ip():
    return request.remote_addr or request.headers.get('X-Forwarded-For','') or None

@converters_bp.route('/convert/xml-to-sql', methods=['POST'])
@jwt_required()
def xml_to_sql_route():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON avec champ 'xml' requis", 400)

        schema = ConvertXmlToSqlSchema()
        validated = schema.load(json_data)

        xml_content = validated['xml']
        db_name = json_data.get('database_name') or json_data.get('name')

        try:
            sql = convert_xml_to_sql(xml_content, database_name=db_name)
        except Exception as e:
            AuditService.log(
                user_id=user.id if user else None,
                user_name=user.full_name if user else None,
                ip_address=get_ip(),
                action="ERREUR_CONVERSION_XML",
                element_type="converter",
                element_name="xml-to-sql",
                description=str(e)
            )
            return error_response(f"Erreur conversion: {str(e)}", 400)

        AuditService.log(
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip(),
            action="CONVERSION_XML",
            element_type="converter",
            element_name=db_name or "xml-to-sql",
            description="Conversion XML → SQL réussie"
        )

        return success_response({"sql": sql}, "Conversion XML → SQL réussie")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)

@converters_bp.route('/convert/sql-to-xml', methods=['POST'])
@jwt_required()
def sql_to_xml_route():
    try:
        user_id = int(get_jwt_identity())
        user = AuthService.get_user_by_id(user_id)

        json_data = request.get_json()
        if not json_data:
            return error_response("JSON avec champ 'sql' requis", 400)

        schema = ConvertSqlToXmlSchema()
        validated = schema.load(json_data)

        sql_content = validated['sql']
        db_name = json_data.get('database_name') or json_data.get('name') or "converted_db"

        try:
            xml_content = convert_sql_to_xml(sql_content, database_name=db_name)
        except Exception as e:
            AuditService.log(
                user_id=user.id if user else None,
                user_name=user.full_name if user else None,
                ip_address=get_ip(),
                action="ERREUR_CONVERSION_SQL",
                element_type="converter",
                element_name="sql-to-xml",
                description=str(e)
            )
            return error_response(f"Erreur conversion: {str(e)}", 400)

        AuditService.log(
            user_id=user.id,
            user_name=user.full_name,
            ip_address=get_ip(),
            action="CONVERSION_SQL",
            element_type="converter",
            element_name=db_name,
            description="Conversion SQL → XML réussie"
        )

        return success_response({"xml": xml_content}, "Conversion SQL → XML réussie")

    except ValidationError as ve:
        return error_response("Validation échouée", 400, ve.messages)
    except Exception as e:
        return error_response(str(e), 500)
