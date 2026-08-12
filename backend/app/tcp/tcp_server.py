"""
Serveur TCP/IP pour XMLForge
Écoute sur le port 3307
"""
import threading
import socket
import uuid
import logging
from datetime import datetime, timedelta
from flask import current_app
from .tcp_protocol import TCPProtocol
from ..services.auth_service import AuthService
from ..services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class ClientSession:
    """Représente une session client connectée"""
    
    def __init__(self, client_socket, address):
        self.socket = client_socket
        self.address = address
        self.token = str(uuid.uuid4())
        self.user = None
        self.database = None
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.authenticated = False
    
    def is_expired(self, timeout_minutes=30):
        """Vérifie si la session a expiré"""
        return datetime.utcnow() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def update_activity(self):
        """Met à jour le timestamp de la dernière activité"""
        self.last_activity = datetime.utcnow()


class TCPServer:
    """Serveur TCP/IP pour connexion à XMLForge"""
    
    def __init__(self, host='0.0.0.0', port=3307, flask_app=None):
        self.host = host
        self.port = port
        self.flask_app = flask_app
        self.running = False
        self.socket = None
        self.sessions = {}  # {token: ClientSession}
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self):
        """Lance le serveur TCP/IP"""
        if self.running:
            logger.warning("TCP Server est déjà en cours d'exécution")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"TCP Server démarré sur {self.host}:{self.port}")
    
    def stop(self):
        """Arrête le serveur TCP/IP"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("TCP Server arrêté")
    
    def _run(self):
        """Boucle principale du serveur"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            logger.info(f"Serveur TCP écoute sur {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    logger.info(f"Nouvelle connexion de {address}")
                    # Créer un thread pour gérer le client
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Erreur lors de l'acceptation de connexion: {e}")
        
        except Exception as e:
            logger.error(f"Erreur du serveur TCP: {e}")
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
    
    def _handle_client(self, client_socket, address):
        """Gère la connexion d'un client"""
        try:
            client_socket.settimeout(60)  # 60 secondes de timeout
            session = None
            buffer = b""
            
            while self.running:
                try:
                    # Recevoir les données
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    buffer += data
                    
                    # Traiter les messages reçus
                    while len(buffer) >= 5:
                        try:
                            msg_type, msg_data, consumed = TCPProtocol.unpack_message(buffer)
                            buffer = buffer[consumed:]
                            
                            # Traiter le message
                            response = self._process_message(msg_type, msg_data, session)
                            
                            # Mettre à jour la session si nouvelle authentification
                            if msg_type == TCPProtocol.MSG_AUTH and response:
                                session_token = msg_data.get('session_token')
                                if session_token and session_token in self.sessions:
                                    session = self.sessions[session_token]
                            
                            # Envoyer la réponse
                            if response:
                                client_socket.sendall(response)
                        
                        except ValueError as e:
                            logger.debug(f"Erreur parsing: {e}")
                            break
                
                except socket.timeout:
                    # Vérifier si la session a expiré
                    if session and session.is_expired():
                        response = TCPProtocol.create_error(
                            TCPProtocol.SESSION_EXPIRED,
                            "Session expirée"
                        )
                        client_socket.sendall(response)
                        break
                    continue
                except Exception as e:
                    logger.error(f"Erreur client {address}: {e}")
                    break
        
        except Exception as e:
            logger.error(f"Erreur handler client {address}: {e}")
        
        finally:
            try:
                client_socket.close()
            except:
                pass
            logger.info(f"Connexion fermée: {address}")
    
    def _process_message(self, msg_type: int, data: dict, session: ClientSession) -> bytes:
        """Traite un message reçu du client"""
        
        if msg_type == TCPProtocol.MSG_PING:
            return TCPProtocol.create_pong()
        
        elif msg_type == TCPProtocol.MSG_AUTH:
            return self._handle_auth(data)
        
        elif msg_type == TCPProtocol.MSG_QUERY:
            # Récupérer la session à partir du session_token si pas déjà fournie
            if not session or not session.authenticated:
                session_token = data.get('session_token')
                if session_token and session_token in self.sessions:
                    session = self.sessions[session_token]
            
            if not session or not session.authenticated:
                return TCPProtocol.create_error(
                    TCPProtocol.SESSION_EXPIRED,
                    "Non authentifié"
                )
            return self._handle_query(data, session)
        
        else:
            return TCPProtocol.create_error(
                TCPProtocol.INVALID_REQUEST,
                f"Type de message inconnu: {msg_type}"
            )
    
    def _handle_auth(self, data: dict) -> bytes:
        """Gère l'authentification"""
        try:
            username = data.get('username')
            password = data.get('password')
            database_name = data.get('database')
            
            if not username or not password:
                return TCPProtocol.create_error(
                    TCPProtocol.AUTH_FAILED,
                    "Username et password requis"
                )
            
            # Utiliser le contexte d'application Flask
            if self.flask_app:
                with self.flask_app.app_context():
                    # Vérifier les identifiants
                    user = AuthService.verify_credentials(username, password)
                    
                    if not user:
                        return TCPProtocol.create_error(
                            TCPProtocol.AUTH_FAILED,
                            "Identifiants invalides"
                        )
                    
                    if not user.is_active:
                        return TCPProtocol.create_error(
                            TCPProtocol.AUTH_FAILED,
                            "Utilisateur désactivé"
                        )
                    
                    # Sélectionner la base de données si spécifiée
                    database = None
                    if database_name:
                        # Chercher la base sans vérifier le propriétaire (pour TCP)
                        database = DatabaseService.get_database_by_name_any_user(database_name)
                        
                        if not database:
                            logger.warning(f"Base de données '{database_name}' non trouvée, connexion sans base")
                            database = None
                    
                    # Créer une session
                    session = ClientSession(None, None)
                    session.user = user
                    session.database = database
                    session.authenticated = True
                    
                    with self.lock:
                        self.sessions[session.token] = session
                    
                    logger.info(f"Authentification réussie pour {username}")
                    
                    response_data = {
                        'session_token': session.token,
                        'user_id': user.id,
                        'username': user.email,
                        'full_name': user.full_name,
                    }
                    
                    if database:
                        response_data['database_id'] = database.id
                        response_data['database_name'] = database.name
                    
                    return TCPProtocol.create_response(TCPProtocol.AUTH_SUCCESS, response_data)
            
            else:
                # Fallback sans contexte (ne devrait pas arriver)
                return TCPProtocol.create_error(
                    TCPProtocol.AUTH_FAILED,
                    "Configuration serveur incorrecte"
                )
        
        except Exception as e:
            logger.error(f"Erreur authentification: {e}", exc_info=True)
            return TCPProtocol.create_error(
                TCPProtocol.AUTH_FAILED,
                f"Erreur interne: {str(e)}"
            )
    
    def _handle_query(self, data: dict, session: ClientSession) -> bytes:
        """Gère une requête de données"""
        try:
            session.update_activity()
            
            query = data.get('query', '').strip()
            
            if not query:
                return TCPProtocol.create_error(
                    TCPProtocol.INVALID_REQUEST,
                    "Query vide"
                )
            
            # Parser la requête simple
            # Format: SELECT * FROM table_name
            # Format: INSERT INTO table_name VALUES (...)
            # Format: UPDATE table_name SET ...
            # Format: DELETE FROM table_name WHERE ...
            
            query_upper = query.upper()
            
            try:
                if query_upper.startswith('SELECT'):
                    result = self._handle_select(query, session)
                elif query_upper.startswith('INSERT'):
                    result = self._handle_insert(query, session)
                elif query_upper.startswith('UPDATE'):
                    result = self._handle_update(query, session)
                elif query_upper.startswith('DELETE'):
                    result = self._handle_delete(query, session)
                else:
                    return TCPProtocol.create_error(
                        TCPProtocol.QUERY_ERROR,
                        "Type de requête non supporté"
                    )
                
                return TCPProtocol.create_response(
                    TCPProtocol.QUERY_SUCCESS,
                    {'result': result}
                )
            
            except Exception as e:
                logger.error(f"Erreur requête: {e}")
                return TCPProtocol.create_error(
                    TCPProtocol.QUERY_ERROR,
                    str(e)
                )
        
        except Exception as e:
            logger.error(f"Erreur handler query: {e}")
            return TCPProtocol.create_error(
                TCPProtocol.QUERY_ERROR,
                "Erreur interne"
            )
    
    def _handle_select(self, query: str, session: ClientSession):
        """Traite une requête SELECT"""
        try:
            # Parser la requête SQL simple
            # Format: SELECT * FROM table_name
            # Format: SELECT col1, col2 FROM table_name
            # Format: SELECT * FROM table_name WHERE condition
            
            import re
            query_upper = query.upper()
            
            # Extraire le nom de la table
            match = re.search(r'FROM\s+(\w+)', query_upper)
            if not match:
                return {"data": [], "count": 0, "error": "Syntaxe invalide: table non trouvée"}
            
            table_name = match.group(1).lower()
            
            # Extraire les colonnes
            columns_match = re.search(r'SELECT\s+(.+?)\s+FROM', query_upper)
            if columns_match:
                columns_str = columns_match.group(1)
                if columns_str.strip() == '*':
                    columns = None  # Toutes les colonnes
                else:
                    columns = [col.strip() for col in columns_str.split(',')]
            else:
                columns = None
            
            # Extraire la clause WHERE (optionnelle)
            where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|\s+GROUP\s+BY|$)', query_upper, re.IGNORECASE)
            where_clause = where_match.group(1) if where_match else None
            
            # Récupérer les données de la table depuis XMLForge
            if not session.database:
                return {"data": [], "count": 0, "error": "Aucune base de données sélectionnée"}
            
            with self.flask_app.app_context():
                from ..models.table import Table
                from ..models.column import Column
                from ..models.table_row import TableRow
                
                # Trouver la table par nom
                table = Table.query.filter_by(
                    database_id=session.database.id,
                    name=table_name,
                    status="ACTIVE"
                ).first()
                
                if not table:
                    return {"data": [], "count": 0, "error": f"Table '{table_name}' non trouvée"}
                
                # Récupérer les colonnes
                column_objs = Column.query.filter_by(table_id=table.id, status="ACTIVE").all()
                column_map = {col.name: col for col in column_objs}
                
                # Récupérer les lignes
                rows = TableRow.query.filter_by(table_id=table.id).all()
                
                # Convertir en format de résultat
                result_data = []
                for row in rows:
                    row_dict = {}
                    if row.data_json:
                        # row.data_json est un JSON string
                        import json
                        try:
                            row_data = json.loads(row.data_json)
                            if columns:
                                # Filtrer les colonnes demandées
                                for col in columns:
                                    row_dict[col] = row_data.get(col)
                            else:
                                row_dict = row_data
                        except:
                            row_dict = {}
                    result_data.append(row_dict)
                
                # Appliquer le filtre WHERE (basique)
                if where_clause and result_data:
                    # Parser simple: col = 'value' ou col = value
                    where_match = re.match(r'(\w+)\s*=\s*[\'"]?([^\'"]+)[\'"]?', where_clause)
                    if where_match:
                        col_name = where_match.group(1).lower()
                        col_value = where_match.group(2)
                        result_data = [row for row in result_data if str(row.get(col_name)) == col_value]
                
                return {
                    "data": result_data,
                    "count": len(result_data),
                    "table": table_name,
                    "columns": [col.name for col in column_objs]
                }
        
        except Exception as e:
            logger.error(f"Erreur SELECT: {e}", exc_info=True)
            return {"data": [], "count": 0, "error": str(e)}
    
    def _handle_insert(self, query: str, session: ClientSession):
        """Traite une requête INSERT"""
        # TODO: Implémenter
        return {"inserted": 0}
    
    def _handle_update(self, query: str, session: ClientSession):
        """Traite une requête UPDATE"""
        # TODO: Implémenter
        return {"updated": 0}
    
    def _handle_delete(self, query: str, session: ClientSession):
        """Traite une requête DELETE"""
        # TODO: Implémenter
        return {"deleted": 0}
    
    def get_sessions_info(self) -> list:
        """Retourne les informations sur les sessions actives"""
        with self.lock:
            sessions_info = []
            for token, session in list(self.sessions.items()):
                if session.is_expired():
                    del self.sessions[token]
                    continue
                
                sessions_info.append({
                    'token': token[:8] + '...',
                    'user': session.user.email if session.user else None,
                    'database': session.database.name if session.database else None,
                    'connected_at': session.created_at.isoformat(),
                    'last_activity': session.last_activity.isoformat()
                })
            return sessions_info
