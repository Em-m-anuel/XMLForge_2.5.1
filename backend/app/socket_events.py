"""
SocketIO helpers - émission d'événements temps réel
Prêt pour collaboration, sans modifier API REST
Events : nouvelle base, nouvelle table, nouvelle colonne, modification, suppression, import XML, export SQL
"""

def emit_event(event_name, payload):
    """
    Émet un événement SocketIO si disponible
    Ne casse pas si SocketIO non initialisé
    """
    try:
        from .extensions import socketio
        # Vérifier si socketio a été initialisé
        if socketio:
            socketio.emit(event_name, payload)
            # Aussi émettre un événement générique xmlforge_event pour frontend
            socketio.emit('xmlforge_event', {'type': event_name, 'data': payload})
    except Exception as e:
        # Ne pas faire échouer la requête si SocketIO échoue
        print(f"[SocketIO] Erreur émission {event_name}: {e}")

def emit_new_database(database_dict, user_name):
    emit_event('new_database', {'database': database_dict, 'by': user_name})

def emit_new_table(table_dict, user_name):
    emit_event('new_table', {'table': table_dict, 'by': user_name})

def emit_new_column(column_dict, user_name):
    emit_event('new_column', {'column': column_dict, 'by': user_name})

def emit_modification(element_type, element_dict, user_name):
    emit_event('modification', {'element_type': element_type, 'element': element_dict, 'by': user_name})

def emit_suppression(element_type, element_name, database_id, user_name):
    emit_event('suppression', {'element_type': element_type, 'element_name': element_name, 'database_id': database_id, 'by': user_name})

def emit_import_xml(database_dict, user_name):
    emit_event('import_xml', {'database': database_dict, 'by': user_name})

def emit_export_sql(database_id, user_name):
    emit_event('export_sql', {'database_id': database_id, 'by': user_name})

def emit_export_xml(database_id, user_name):
    emit_event('export_xml', {'database_id': database_id, 'by': user_name})
