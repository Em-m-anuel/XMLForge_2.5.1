"""
Exemples d'utilisation du serveur TCP/IP XMLForge
"""

# ============================================================================
# EXEMPLE 1: Connexion simple
# ============================================================================

from app.tcp import XMLForgeClient, connect

# Méthode 1: Avec XMLForgeClient
print("=== Exemple 1: Connexion simple ===")
client = XMLForgeClient(host='localhost', port=3307)
client.connect(
    username='user@example.com',
    password='<VOTRE_MOT_DE_PASSE>'
)
print(f"✓ Connecté en tant que: {client.username}")
client.disconnect()

# Méthode 2: Avec fonction helper
print("\n=== Exemple 1b: Fonction helper ===")
client = connect(
    host='localhost',
    port=3307,
    username='user@example.com',
    password='<VOTRE_MOT_DE_PASSE>'
)
print(f"✓ Connecté: {client.authenticated}")
client.disconnect()


# ============================================================================
# EXEMPLE 2: Context manager (recommandé)
# ============================================================================

print("\n=== Exemple 2: Context manager ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    print("✓ Connecté à la base de données")
    # La déconnexion est automatique à la sortie du bloc

print("✓ Déconnecté automatiquement")


# ============================================================================
# EXEMPLE 3: Requêtes SELECT
# ============================================================================

print("\n=== Exemple 3: SELECT ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    # Requête simple
    users = client.select('users')
    print(f"✓ {len(users)} utilisateurs trouvés")
    
    # Avec WHERE
    active_users = client.select('users', where="status='active'")
    print(f"✓ {len(active_users)} utilisateurs actifs")
    
    # Colonnes spécifiques
    names = client.select('users', columns='id, name, email')
    print(f"✓ {len(names)} noms d'utilisateurs")


# ============================================================================
# EXEMPLE 4: INSERT
# ============================================================================

print("\n=== Exemple 4: INSERT ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    # Insérer une ligne
    inserted = client.insert('users', {
        'name': 'John Doe',
        'email': 'john@example.com',
        'status': 'active'
    })
    print(f"✓ {inserted} utilisateur inséré")
    
    # Insérer plusieurs lignes
    users_data = [
        {'name': 'Alice', 'email': 'alice@example.com', 'status': 'active'},
        {'name': 'Bob', 'email': 'bob@example.com', 'status': 'inactive'},
        {'name': 'Charlie', 'email': 'charlie@example.com', 'status': 'active'},
    ]
    
    for user in users_data:
        client.insert('users', user)
    print(f"✓ {len(users_data)} utilisateurs insérés")


# ============================================================================
# EXEMPLE 5: UPDATE
# ============================================================================

print("\n=== Exemple 5: UPDATE ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    # Mettre à jour un utilisateur
    updated = client.update('users', 
        {'status': 'active', 'last_login': '2026-01-11'},
        where="email='john@example.com'"
    )
    print(f"✓ {updated} utilisateur(s) mis à jour")
    
    # Mettre à jour plusieurs
    updated = client.update('users',
        {'status': 'archived'},
        where="status='inactive' AND last_login < '2025-01-11'"
    )
    print(f"✓ {updated} utilisateurs archivés")


# ============================================================================
# EXEMPLE 6: DELETE
# ============================================================================

print("\n=== Exemple 6: DELETE ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    # Supprimer un utilisateur
    deleted = client.delete('users', where="email='john@example.com'")
    print(f"✓ {deleted} utilisateur(s) supprimé(s)")
    
    # Supprimer les comptes inactifs
    deleted = client.delete('users', where="status='archived'")
    print(f"✓ {deleted} comptes archivés supprimés")


# ============================================================================
# EXEMPLE 7: Requête raw
# ============================================================================

print("\n=== Exemple 7: Requête raw ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    # Exécuter une requête brute
    result = client.execute("SELECT * FROM users WHERE status='active'")
    print(f"✓ Résultat: {result}")


# ============================================================================
# EXEMPLE 8: Test de connexion (ping)
# ============================================================================

print("\n=== Exemple 8: Ping ===")
with connect('localhost', 3307, 'user@example.com', '<VOTRE_MOT_DE_PASSE>') as client:
    is_alive = client.ping()
    print(f"✓ Serveur disponible: {is_alive}")


# ============================================================================
# EXEMPLE 9: Gestion des erreurs
# ============================================================================

print("\n=== Exemple 9: Gestion des erreurs ===")
from app.tcp import XMLForgeClient

try:
    client = XMLForgeClient(host='localhost', port=3307, timeout=5)
    client.connect('invalid@example.com', 'wrong_password')
except ConnectionError as e:
    print(f"✗ Erreur de connexion: {e}")

try:
    client = XMLForgeClient()
    # Ne pas se connecter
    client.execute("SELECT * FROM users")
except RuntimeError as e:
    print(f"✗ Erreur: {e}")


# ============================================================================
# EXEMPLE 10: Importation en masse
# ============================================================================

print("\n=== Exemple 10: Import en masse ===")
import csv
import json

def import_users_from_csv(csv_file, host, port, username, password):
    """Importe des utilisateurs depuis un fichier CSV"""
    with connect(host, port, username, password) as client:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                client.insert('users', row)
                count += 1
        print(f"✓ {count} utilisateurs importés depuis {csv_file}")

# Utilisation:
# import_users_from_csv('users.csv', 'localhost', 3307, 'user@example.com', 'password')


# ============================================================================
# EXEMPLE 11: Exportation en masse
# ============================================================================

print("\n=== Exemple 11: Export en masse ===")

def export_users_to_json(output_file, host, port, username, password):
    """Exporte tous les utilisateurs en JSON"""
    with connect(host, port, username, password) as client:
        users = client.select('users')
        with open(output_file, 'w') as f:
            json.dump(users, f, indent=2)
        print(f"✓ {len(users)} utilisateurs exportés vers {output_file}")

# Utilisation:
# export_users_to_json('users.json', 'localhost', 3307, 'user@example.com', 'password')


# ============================================================================
# EXEMPLE 12: Synchronisation de bases de données
# ============================================================================

print("\n=== Exemple 12: Synchronisation ===")

def sync_databases(source_config, target_config, table_name):
    """Synchronise une table d'une base à une autre"""
    with connect(**source_config) as source:
        with connect(**target_config) as target:
            # Récupérer les données source
            data = source.select(table_name)
            print(f"✓ {len(data)} lignes lues de la source")
            
            # Insérer dans la cible
            for row in data:
                target.insert(table_name, row)
            
            print(f"✓ {len(data)} lignes synchronisées")

# Utilisation:
# source = {'host': 'server1.com', 'port': 3307, 'username': 'user1@example.com', 'password': 'pass1'}
# target = {'host': 'server2.com', 'port': 3307, 'username': 'user2@example.com', 'password': 'pass2'}
# sync_databases(source, target, 'users')


# ============================================================================
# EXEMPLE 13: Backup
# ============================================================================

print("\n=== Exemple 13: Backup ===")

def backup_database(host, port, username, password, database, backup_file):
    """Fait un backup complet de la base de données"""
    import json
    from datetime import datetime
    
    with connect(host, port, username, password, database) as client:
        # Pour ce exemple, on suppose que client a une méthode pour lister les tables
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'database': database,
            'tables': {}
        }
        
        # Exemple avec une table
        backup_data['tables']['users'] = client.select('users')
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        print(f"✓ Backup sauvegardé dans {backup_file}")

# Utilisation:
# backup_database('localhost', 3307, 'user@example.com', 'password', 'my_db', 'backup.json')


# ============================================================================
# EXEMPLE 14: Avec gestion d'erreurs robuste
# ============================================================================

print("\n=== Exemple 14: Gestion robuste ===")

def safe_insert_user(host, port, username, password, user_data, max_retries=3):
    """Insère un utilisateur avec gestion d'erreurs et retry"""
    retries = 0
    while retries < max_retries:
        try:
            with connect(host, port, username, password) as client:
                client.insert('users', user_data)
                print("✓ Utilisateur inséré avec succès")
                return True
        except ConnectionError as e:
            retries += 1
            print(f"✗ Erreur de connexion (essai {retries}/{max_retries}): {e}")
            if retries < max_retries:
                import time
                time.sleep(2 ** retries)  # Backoff exponentiel
        except Exception as e:
            print(f"✗ Erreur inattendue: {e}")
            return False
    
    print(f"✗ Impossible d'insérer après {max_retries} essais")
    return False

# Utilisation:
# safe_insert_user('localhost', 3307, 'user@example.com', 'password', 
#                   {'name': 'Jane', 'email': 'jane@example.com'})
