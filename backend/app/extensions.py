"""
Extensions Flask centralisées pour éviter imports circulaires
V2 : ajout SocketIO pour temps réel
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_socketio import SocketIO

db = SQLAlchemy()
jwt = JWTManager()
bcrypt = Bcrypt()
cors = CORS()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')  # threading pour simplicité, compatible sans eventlet
