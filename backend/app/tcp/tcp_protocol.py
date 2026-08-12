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
    def create_query_request(query: str, session_token: str) -> bytes:
        """Crée une requête de requête"""
        data = {
            'query': query,
            'session_token': session_token
        }
        return TCPProtocol.pack_message(TCPProtocol.MSG_QUERY, data)
    
    @staticmethod
    def create_response(status: int, data: dict = None) -> bytes:
        """Crée une réponse"""
        response_data = {'status': status}
        if data:
            response_data.update(data)
        return TCPProtocol.pack_message(TCPProtocol.MSG_RESPONSE, response_data)
    
    @staticmethod
    def create_error(code: int, message: str) -> bytes:
        """Crée un message d'erreur"""
        data = {
            'code': code,
            'message': message
        }
        return TCPProtocol.pack_message(TCPProtocol.MSG_ERROR, data)
    
    @staticmethod
    def create_ping() -> bytes:
        """Crée un ping"""
        return TCPProtocol.pack_message(TCPProtocol.MSG_PING, {})
    
    @staticmethod
    def create_pong() -> bytes:
        """Crée un pong"""
        return TCPProtocol.pack_message(TCPProtocol.MSG_PONG, {})
