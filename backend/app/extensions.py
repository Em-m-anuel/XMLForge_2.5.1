"""Extensions Flask — architecture XML-only (Phase 6J-B).

Plus aucune dépendance SQLAlchemy : seuls JWT, bcrypt, CORS et SocketIO.
"""

from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_socketio import SocketIO

jwt = JWTManager()
bcrypt = Bcrypt()
cors = CORS()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')
