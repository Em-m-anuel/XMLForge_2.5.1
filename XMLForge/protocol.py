"""Protocole TCP XMLForge — implémentation client (Phase 7).

Format de trame : ``[type:1 octet][longueur:4 octets big-endian][JSON UTF-8]``.
Compatible avec le serveur ``app/tcp/tcp_protocol.py``.
"""

import json
import struct

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


def pack_message(msg_type: int, data: dict) -> bytes:
    """Encode un message : [type(1)][len(4 BE)][JSON UTF-8]."""
    payload = json.dumps(data).encode("utf-8")
    return struct.pack("!B", msg_type) + struct.pack("!I", len(payload)) + payload


def unpack_message(data: bytes):
    """Décode un message. Retourne ``(msg_type, data_dict, consumed)``."""
    if len(data) < 5:
        raise ValueError("Message trop court")
    msg_type = struct.unpack("!B", data[:1])[0]
    length = struct.unpack("!I", data[1:5])[0]
    if len(data) < 5 + length:
        raise ValueError("Message incomplet")
    payload = data[5:5 + length].decode("utf-8")
    return msg_type, json.loads(payload), 5 + length


def auth_request(username, password, database=None):
    data = {"username": username, "password": password}
    if database is not None:
        data["database"] = database
    return pack_message(MSG_AUTH, data)


def query_request(sql, session_token, expected_version=None, table_key=None, engine=None):
    data = {"query": sql, "session_token": session_token}
    if expected_version is not None:
        data["expected_version"] = expected_version
    if table_key:
        data["table_key"] = table_key
    if engine:
        data["engine"] = engine
    return pack_message(MSG_QUERY, data)


def close_request(session_token):
    return pack_message(MSG_CLOSE, {"session_token": session_token})
