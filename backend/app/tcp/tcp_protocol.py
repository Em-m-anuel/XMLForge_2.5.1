"""
Protocole TCP simple pour XMLForge
Format: JSON-based requests/responses
"""
import json
import struct


class TCPProtocol:
    """Protocole de communication TCP/IP pour XMLForge"""
    
    # Types de message
    MSG_AUTH = 1
    MSG_QUERY = 2
    MSG_RESPONSE = 3
    MSG_ERROR = 4
    MSG_PING = 5
    MSG_PONG = 6
    MSG_SELECT_DATABASE = 7
    MSG_UNLOCK_TABLE = 8
    MSG_CLOSE = 9
    
    # Codes de réponse
    AUTH_SUCCESS = 0
    AUTH_FAILED = 1
    QUERY_SUCCESS = 2
    QUERY_ERROR = 3
    SESSION_EXPIRED = 4
    INVALID_REQUEST = 5
    
    @staticmethod
    def pack_message(msg_type: int, data: dict) -> bytes:
        """Encode un message en bytes"""
        json_data = json.dumps(data).encode('utf-8')
        # Format: [type(1)][length(4)][data]
        message = struct.pack('!I', len(json_data)) + json_data
        return struct.pack('!B', msg_type) + message
    
    @staticmethod
    def unpack_message(data: bytes) -> tuple:
        """Décode un message en bytes
        Retourne (msg_type, data_dict)
        """
        if len(data) < 5:
            raise ValueError("Message trop court")
        
        msg_type = struct.unpack('!B', data[:1])[0]
        length = struct.unpack('!I', data[1:5])[0]
        
        if len(data) < 5 + length:
            raise ValueError("Message incomplet")
        
        json_data = data[5:5+length].decode('utf-8')
        data_dict = json.loads(json_data)
        
        return msg_type, data_dict, 5 + length
    
    @staticmethod
    def create_auth_request(username: str, password: str, db_name: str = None) -> bytes:
        """Crée une requête d'authentification"""
        data = {
            'username': username,
            'password': password,
        }
        if db_name:
            data['database'] = db_name
        return TCPProtocol.pack_message(TCPProtocol.MSG_AUTH, data)
    
    @staticmethod
    def create_query_request(query: str, session_token: str, expected_version=None, table_key=None, engine=None) -> bytes:
        data = {'query': query, 'session_token': session_token}
        if expected_version is not None:
            data['expected_version'] = expected_version
        if table_key:
            data['table_key'] = table_key
        if engine:
            data['engine'] = engine
        return TCPProtocol.pack_message(TCPProtocol.MSG_QUERY, data)

    @staticmethod
    def create_select_database(database, session_token: str) -> bytes:
        return TCPProtocol.pack_message(TCPProtocol.MSG_SELECT_DATABASE, {
            'database': database, 'session_token': session_token
        })

    @staticmethod
    def create_unlock_table(table, key: str, session_token: str) -> bytes:
        return TCPProtocol.pack_message(TCPProtocol.MSG_UNLOCK_TABLE, {
            'table': table, 'key': key, 'session_token': session_token
        })

    @staticmethod
    def create_close(session_token: str) -> bytes:
        return TCPProtocol.pack_message(TCPProtocol.MSG_CLOSE, {'session_token': session_token})
    
    @staticmethod
    def create_response(status: int, data: dict = None) -> bytes:
        """Crée une réponse"""
        response_data = {'status': status}
        if data:
            response_data.update(data)
        return TCPProtocol.pack_message(TCPProtocol.MSG_RESPONSE, response_data)
    
    @staticmethod
    def create_error(code: int, message: str, error_code: str = None) -> bytes:
        """Crée un message d'erreur.

        - ``code`` : code numérique du protocole (stable, rétrocompatible) ;
        - ``error_code`` : code métier XMLForge (ex. TABLE_NOT_FOUND,
          ACCESS_DENIED, CONSTRAINT_VIOLATION…) — ajouté sans casser les
          clients existants.
        """
        data = {
            'code': code,
            'message': message
        }
        if error_code:
            data['error_code'] = error_code
        return TCPProtocol.pack_message(TCPProtocol.MSG_ERROR, data)
    
    @staticmethod
    def create_ping() -> bytes:
        """Crée un ping"""
        return TCPProtocol.pack_message(TCPProtocol.MSG_PING, {})
    
    @staticmethod
    def create_pong() -> bytes:
        """Crée un pong"""
        return TCPProtocol.pack_message(TCPProtocol.MSG_PONG, {})
