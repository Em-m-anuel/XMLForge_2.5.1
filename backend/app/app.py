"""
Wrapper app.py à l'intérieur du package app pour compatibilité
"""
from . import create_app
from .config import Config
from .extensions import socketio

flask_app = create_app(Config)
app = flask_app  # alias pour compatibilité

if __name__ == '__main__':
    socketio.run(
        flask_app, host='0.0.0.0', port=5000,
        debug=bool(flask_app.config.get('DEBUG', False)),
        allow_unsafe_werkzeug=bool(flask_app.config.get('ALLOW_UNSAFE_WERKZEUG', False)),
    )
