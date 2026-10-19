"""Client XMLForge — API publique (Phase 7).

Exemple :

    from xmlforge import connect

    db = connect(host="localhost", port=3307, user="...", password="...")
    db.execute("USE Bibliotheque")
    result = db.query("SELECT * FROM books")
    for row in result.rows:
        print(row)
    db.close()
"""

from .connection import Connection


def connect(host="localhost", port=3307, user=None, password=None, database=None,
            timeout=10):
    """Ouvre et authentifie une connexion TCP XMLForge.

    ``user``/``password`` sont les credentials TCP (gérés via l'API REST
    ``/api/tcp/credentials``) — jamais les fichiers XML.
    """
    conn = Connection(host=host, port=port, timeout=timeout)
    conn.connect()
    conn.authenticate(user, password, database=database)
    return conn


__all__ = ["connect", "Connection"]
