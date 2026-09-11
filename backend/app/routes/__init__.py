"""
Enregistrement de tous les Blueprints V4
Supporte /api/* et /* pour compat frontend
"""
from .auth import auth_bp
from .databases import databases_bp
from .tables import tables_bp
from .columns import columns_bp
from .imports import imports_bp
from .exports import exports_bp
from .converters import converters_bp
from .history import history_bp
from .unlock import unlock_bp
from .metadata import metadata_bp
from .audit import audit_bp
from .sync import sync_bp
from .users import users_bp
from .rows import rows_bp
from .projects import projects_bp
from .tcp import tcp_bp
from .permissions import permissions_bp
from .query import query_bp

def _clone_blueprint(bp, new_name):
    from flask import Blueprint
    new_bp = Blueprint(new_name, bp.import_name)
    new_bp.deferred_functions = list(bp.deferred_functions)
    return new_bp

def register_routes(app):
    original_bps = [
        auth_bp,
        databases_bp,
        tables_bp,
        columns_bp,
        imports_bp,
        exports_bp,
        converters_bp,
        history_bp,
        unlock_bp,
        metadata_bp,
        audit_bp,
        sync_bp,
        users_bp,
        rows_bp,
        projects_bp,
        permissions_bp,
        query_bp,
    ]

    # Sans préfixe historique et avec /api pour compatibilité.
    for bp in original_bps:
        app.register_blueprint(bp)
    for bp in original_bps:
        clone = _clone_blueprint(bp, f"{bp.name}_api")
        app.register_blueprint(clone, url_prefix='/api')

    # TCP possède déjà son préfixe canonique /api/tcp : ne pas le cloner sous
    # /api/credentials, ce qui exposait auparavant des aliases accidentels.
    app.register_blueprint(tcp_bp)
