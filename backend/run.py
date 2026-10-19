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
    socketio.run(
        flask_app,
        host=flask_app.config.get('HTTP_HOST', '0.0.0.0'),
        port=flask_app.config.get('HTTP_PORT', 5000),
        debug=bool(flask_app.config.get('DEBUG', False)),
        allow_unsafe_werkzeug=bool(flask_app.config.get('ALLOW_UNSAFE_WERKZEUG', False)),
    )
