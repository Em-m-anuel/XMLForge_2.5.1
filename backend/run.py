"""
Point d'entrée principal Flask + SocketIO
Lancement: python run.py
"""
from app import create_app
from app.config import Config
from app.extensions import socketio

flask_app = create_app(Config)
app = flask_app

if __name__ == '__main__':
    socketio.run(flask_app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
