"""
Bibliothèque cliente Python pour XMLForge TCP/IP
"""
import socket
import struct
import json
import uuid
from typing import Any, Dict, List, Optional, Union
from .tcp_protocol import TCPProtocol


class XMLForgeClient:
    """Client Python pour se connecter à XMLForge via TCP/IP"""
    
    def __init__(self, host: str = 'localhost', port: int = 3307, timeout: int = 30):
        """
        Initialise le client XMLForge
        
        Args:
            host: Adresse du serveur (défaut: localhost)
            port: Port du serveur (défaut: 3307)
            timeout: Timeout de connexion en secondes (défaut: 30)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.session_token = None
        self.user_id = None
        self.username = None
        self.database_id = None
        self.database_name = None
        self.authenticated = False
    
    def connect(self, username: str, password: str, database: str = None) -> bool:
        """
        Se connecte au serveur XMLForge
        
        Args:
            username: Nom d'utilisateur (email)
            password: Mot de passe
            database: Nom de la base de données (optionnel)
        
        Returns:
            True si la connexion est réussie, False sinon
        
        Raises:
            ConnectionError: Si la connexion au serveur échoue
        """
        try:
            # Créer la socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            
            # Envoyer la requête d'authentification
            auth_request = TCPProtocol.create_auth_request(username, password, database)
            self.socket.sendall(auth_request)
            
            # Recevoir la réponse
            response = self._receive_message()
            
            if response is None:
                raise ConnectionError("Aucune réponse du serveur")
            
            msg_type, data, _ = response
            
            if msg_type == TCPProtocol.MSG_ERROR:
                raise ConnectionError(f"Erreur authentification: {data.get('message')}")
            
            if msg_type != TCPProtocol.MSG_RESPONSE or data.get('status') != TCPProtocol.AUTH_SUCCESS:
                raise ConnectionError("Authentification échouée")
            
            # Stocker les données de session
            self.session_token = data.get('session_token')
            self.user_id = data.get('user_id')
            self.username = data.get('username')
            self.database_id = data.get('database_id')
            self.database_name = data.get('database_name')
            self.authenticated = True
            
            print(f"✓ Connecté à XMLForge en tant que {self.username}")
            if self.database_name:
                print(f"✓ Base de données sélectionnée: {self.database_name}")
            
            return True
        
        except socket.timeout:
            raise ConnectionError(f"Timeout de connexion après {self.timeout}s")
        except socket.error as e:
            raise ConnectionError(f"Erreur de connexion: {e}")
        except Exception as e:
            raise ConnectionError(f"Erreur: {e}")
    
    def disconnect(self):
        """Ferme la connexion"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.authenticated = False
        self.session_token = None
    
    def execute(self, query: str) -> Dict[str, Any]:
        """
        Exécute une requête sur le serveur
        
        Args:
            query: Requête à exécuter (SELECT, INSERT, UPDATE, DELETE)
        
        Returns:
            Dictionnaire avec les résultats
        
        Raises:
            RuntimeError: Si non authentifié
            ConnectionError: Si erreur de connexion
        """
        if not self.authenticated or not self.session_token:
            raise RuntimeError("Non authentifié. Appelez d'abord connect()")
        
        try:
            # Envoyer la requête
            query_request = TCPProtocol.create_query_request(query, self.session_token)
            self.socket.sendall(query_request)
            
            # Recevoir la réponse
            response = self._receive_message()
            
            if response is None:
                raise ConnectionError("Aucune réponse du serveur")
            
            msg_type, data, _ = response
            
            if msg_type == TCPProtocol.MSG_ERROR:
                error_code = data.get('code')
                error_message = data.get('message')
                
                if error_code == TCPProtocol.SESSION_EXPIRED:
                    self.authenticated = False
                    raise RuntimeError(f"Session expirée: {error_message}")
                else:
                    raise RuntimeError(f"Erreur serveur: {error_message}")
            
            if msg_type != TCPProtocol.MSG_RESPONSE:
                raise ConnectionError("Réponse invalide du serveur")
            
            return data.get('result', {})
        
        except socket.timeout:
            raise ConnectionError("Timeout lors de l'exécution")
        except socket.error as e:
            raise ConnectionError(f"Erreur de connexion: {e}")
    
    def ping(self) -> bool:
        """
        Teste la connexion avec un ping
        
        Returns:
            True si le serveur répond
        """
        try:
            ping = TCPProtocol.create_ping()
            self.socket.sendall(ping)
            
            response = self._receive_message()
            
            if response is None:
                return False
            
            msg_type, _, _ = response
            return msg_type == TCPProtocol.MSG_PONG
        
        except:
            return False
    
    def _receive_message(self) -> Optional[tuple]:
        """
        Reçoit et décode un message du serveur
        
        Returns:
            Tuple (msg_type, data_dict, consumed_bytes) ou None
        """
        try:
            buffer = b""
            
            while len(buffer) < 5:
                chunk = self.socket.recv(4096)
                if not chunk:
                    return None
                buffer += chunk
            
            # Lire la longueur du message
            length = struct.unpack('!I', buffer[1:5])[0]
            
            # Attendre le reste du message
            while len(buffer) < 5 + length:
                chunk = self.socket.recv(4096)
                if not chunk:
                    return None
                buffer += chunk
            
            # Décoder le message
            return TCPProtocol.unpack_message(buffer)
        
        except Exception as e:
            return None
    
    def select(self, table: str, columns: str = "*", where: str = None) -> List[Dict]:
        """
        Exécute une requête SELECT
        
        Args:
            table: Nom de la table
            columns: Colonnes à sélectionner (défaut: *)
            where: Clause WHERE (optionnel)
        
        Returns:
            Liste des lignes
        """
        query = f"SELECT {columns} FROM {table}"
        if where:
            query += f" WHERE {where}"
        
        result = self.execute(query)
        return result.get('data', [])
    
    def insert(self, table: str, data: Dict) -> int:
        """
        Insère une ligne dans la table
        
        Args:
            table: Nom de la table
            data: Dictionnaire avec les colonnes et valeurs
        
        Returns:
            Nombre de lignes insérées
        """
        columns = ', '.join(data.keys())
        values = ', '.join([f"'{v}'" if isinstance(v, str) else str(v) for v in data.values()])
        query = f"INSERT INTO {table} ({columns}) VALUES ({values})"
        
        result = self.execute(query)
        return result.get('inserted', 0)
    
    def update(self, table: str, data: Dict, where: str) -> int:
        """
        Met à jour des lignes dans la table
        
        Args:
            table: Nom de la table
            data: Dictionnaire avec les colonnes et valeurs
            where: Clause WHERE pour identifier les lignes
        
        Returns:
            Nombre de lignes mises à jour
        """
        set_clause = ', '.join([
            f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}"
            for k, v in data.items()
        ])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        
        result = self.execute(query)
        return result.get('updated', 0)
    
    def delete(self, table: str, where: str) -> int:
        """
        Supprime des lignes de la table
        
        Args:
            table: Nom de la table
            where: Clause WHERE pour identifier les lignes
        
        Returns:
            Nombre de lignes supprimées
        """
        query = f"DELETE FROM {table} WHERE {where}"
        
        result = self.execute(query)
        return result.get('deleted', 0)
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Fonction helper pour connexion rapide
def connect(host: str = 'localhost', port: int = 3307, 
            username: str = None, password: str = None, 
            database: str = None) -> XMLForgeClient:
    """
    Crée une connexion XMLForge rapidement
    
    Args:
        host: Adresse du serveur
        port: Port du serveur
        username: Nom d'utilisateur
        password: Mot de passe
        database: Base de données (optionnel)
    
    Returns:
        Client XMLForge connecté
    """
    client = XMLForgeClient(host, port)
    client.connect(username, password, database)
    return client
