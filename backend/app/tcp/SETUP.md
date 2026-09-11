"""
Setup Guide pour le serveur TCP/IP XMLForge

Ce fichier explique comment configurer et utiliser le serveur TCP/IP.
"""

# ============================================================================
# 1. BACKEND - Démarrage automatique
# ============================================================================

"""
Le serveur TCP/IP démarre automatiquement avec l'application Flask.

Dans app/__init__.py, le code suivant est exécuté au démarrage:

    # Initialiser le serveur TCP/IP
    try:
        tcp_server = TCPServer(host='0.0.0.0', port=3307)
        tcp_server.start()
        flask_app.tcp_server = tcp_server
        logger.info("Serveur TCP/IP démarré sur le port 3307")
    except Exception as e:
        logger.error(f"Erreur démarrage serveur TCP: {e}")
        flask_app.tcp_server = None

Cela signifie:
- Le serveur écoute sur 0.0.0.0:3307 (toutes les interfaces)
- Le serveur démarre dans un thread daemon
- Les erreurs sont loggées mais ne bloquent pas l'application
"""

# ============================================================================
# 2. BACKEND - Routes API disponibles
# ============================================================================

"""
Les routes suivantes sont disponibles sous /api/tcp:

GET /api/tcp/credentials
  - Retourne les credentials TCP pour l'utilisateur connecté
  - Nécessite: JWT token
  - Retourne: host, port, username

POST /api/tcp/credentials/show-password
  - Retourne le mot de passe en clair (avec vérification)
  - Nécessite: JWT token + current_password
  - Retourne: password, connection_string

GET /api/tcp/sessions
  - Liste les sessions TCP actives de l'utilisateur
  - Nécessite: JWT token
  - Retourne: liste des sessions

GET /api/tcp/status
  - État du serveur TCP
  - Retourne: running, host, port, active_sessions
"""

# ============================================================================
# 3. FRONTEND - Intégration de la composante
# ============================================================================

"""
Pour utiliser la composante TCPCredentials dans votre interface:

1. Importer la composante:
   import TCPCredentials from './components/TCPCredentials/TCPCredentials';

2. L'utiliser dans votre page:
   <TCPCredentials />

3. Les fichiers créés:
   - src/components/TCPCredentials/TCPCredentials.jsx
   - src/components/TCPCredentials/TCPCredentials.css

Exemple complet pour une page Paramètres:

export function SettingsPage() {
  return (
    <div className="settings-page">
      <h1>Paramètres</h1>
      
      <section>
        <h2>Profil</h2>
        {/* Autres paramètres de profil */}
      </section>

      <section>
        <TCPCredentials />
      </section>
    </div>
  );
}
"""

# ============================================================================
# 4. CLIENT PYTHON - Installation
# ============================================================================

"""
Le client Python XMLForge est inclus dans le package backend:

De votre code Python, vous pouvez faire:

    from app.tcp import connect, XMLForgeClient

Ou, pour une installation externe (future), créer un package séparé:

    pip install xmlforge-tcp-client
    
    from xmlforge import connect
"""

# ============================================================================
# 5. CONFIGURATION DE SÉCURITÉ
# ============================================================================

"""
PRODUCTION - IMPORTANT:

Le serveur TCP actuel fonctionne en clair (pas de chiffrement).
Pour la production, recommandations:

1. VPN ou SSH Tunnel
   ssh -L 3307:localhost:3307 user@server.com

2. Pare-feu
   - Restreindre l'accès au port 3307
   - Utiliser whitelist d'IP

3. TLS/SSL (future implémentation)
   - Certificats SSL
   - Authentification mutuelle

4. Credentials
   - Stocker dans des variables d'environnement
   - Pas dans le code source
   - Rotation régulière

Exemple avec environment variables:

    import os
    from app.tcp import connect
    
    client = connect(
        host=os.getenv('XMLFORGE_HOST', 'localhost'),
        port=int(os.getenv('XMLFORGE_PORT', 3307)),
        username=os.getenv('XMLFORGE_USER'),
        password=os.getenv('XMLFORGE_PASS')
    )
"""

# ============================================================================
# 6. MONITORING
# ============================================================================

"""
Monitoring du serveur TCP:

1. Sessions actives:
   GET /api/tcp/status

2. Logs serveur:
   tail -f backend/logs/app.log | grep TCP

3. Port en écoute:
   netstat -an | grep 3307
   lsof -i :3307

4. Processus:
   ps aux | grep python
"""

# ============================================================================
# 7. TROUBLESHOOTING
# ============================================================================

"""
Problèmes courants:

Port déjà en utilisation:
    ERROR: Address already in use
    Solution: tuer le processus existant
    lsill -i :3307 | grep LISTEN
    kill -9 <PID>

Impossible de se connecter:
    ConnectionError: Connection refused
    Vérifier: 1) Serveur démarré? 2) Port correct? 3) Host correct?

Authentification échouée:
    ConnectionError: Identifiants invalides
    Vérifier: username/password corrects
    Vérifier: compte actif (not archived)

Session expirée:
    RuntimeError: Session expirée
    Se reconnecter avec connect()

Performance lente:
    Vérifier latence réseau: ping <host>
    Vérifier charge serveur
    Optimiser requêtes
"""

# ============================================================================
# 8. TESTS
# ============================================================================

"""
Tests du serveur TCP:

1. Test basic de connexion:
   python
   >>> from app.tcp import connect
   >>> with connect('localhost', 3307, 'user@example.com', 'password') as c:
   ...     print(c.ping())
   True

2. Test SELECT:
   >>> users = c.select('users')
   >>> print(len(users))

3. Test INSERT:
   >>> c.insert('users', {'name': 'Test', 'email': 'test@example.com'})
   1

4. Avec pytest (future):
   pytest tests/tcp/ -v
"""

# ============================================================================
# 9. PERFORMANCE OPTIMIZATIONS
# ============================================================================

"""
Pour optimiser les performances:

1. Connection pooling (à venir):
   pool = ConnectionPool(host, port, size=10)
   client = pool.get_connection()

2. Prepared statements (à venir):
   stmt = client.prepare("SELECT * FROM users WHERE id=?")
   result = stmt.execute(1)

3. Batch operations:
   for row in rows:
       client.insert('table', row)  # Optimiser avec transactions

4. Caching:
   @cache.cache(timeout=300)
   def get_users():
       with connect(...) as c:
           return c.select('users')

5. Async/await (à venir):
   async with connect_async(...) as c:
       result = await c.execute_async(query)
"""

# ============================================================================
# 10. MIGRER DEPUIS MYSQL
# ============================================================================

"""
Si vous migrez depuis MySQL:

Remplacement simple:
    # Avant (MySQL):
    import mysql.connector
    conn = mysql.connector.connect(
        host='localhost',
        user='user',
        password='<VOTRE_MOT_DE_PASSE>',
        database='db'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")

    # Après (XMLForge TCP):
    from app.tcp import connect
    with connect('localhost', 3307, 'user@example.com', 'password', 'db') as c:
        users = c.select('users')

Les requêtes SQL standard fonctionnent de la même façon!
"""

print(__doc__)
