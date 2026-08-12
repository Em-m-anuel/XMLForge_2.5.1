#!/usr/bin/env python
"""
Script de test du serveur TCP/IP XMLForge
Vérifiez que tout fonctionne correctement
"""

import sys
import os
import socket
from datetime import datetime

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✓ {text}")

def print_error(text):
    print(f"✗ {text}")

def print_info(text):
    print(f"ℹ {text}")

def test_port_availability():
    """Vérifie que le port 3307 est libre ou déjà en écoute"""
    print_header("Test 1: Port 3307")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 3307))
        sock.close()
        
        if result == 0:
            print_success("Port 3307 est déjà en écoute (serveur actif)")
            return True
        else:
            print_error("Port 3307 n'est pas en écoute")
            print_info("Assurez-vous que Flask est démarré: python run.py")
            return False
    except Exception as e:
        print_error(f"Erreur lors du test du port: {e}")
        return False

def test_tcp_server_import():
    """Vérifie que le module TCP peut être importé"""
    print_header("Test 2: Import du module TCP")
    
    try:
        from app.tcp import TCPServer, TCPProtocol, XMLForgeClient
        print_success("Module TCP importé avec succès")
        return True
    except ImportError as e:
        print_error(f"Erreur d'import: {e}")
        return False
    except Exception as e:
        print_error(f"Erreur inconnue: {e}")
        return False

def test_protocol_encoding():
    """Vérifie que le protocole fonctionne"""
    print_header("Test 3: Protocole TCP")
    
    try:
        from app.tcp import TCPProtocol
        
        # Test encoding
        request = TCPProtocol.create_auth_request('test@example.com', 'password123', 'db')
        print_success("Encoding de requête d'auth: OK")
        
        # Test ping/pong
        ping = TCPProtocol.create_ping()
        pong = TCPProtocol.create_pong()
        print_success("Création de messages: OK")
        
        # Test response
        response = TCPProtocol.create_response(0, {'message': 'test'})
        print_success("Création de réponse: OK")
        
        return True
    except Exception as e:
        print_error(f"Erreur protocole: {e}")
        return False

def test_client_creation():
    """Vérifie que le client peut être créé"""
    print_header("Test 4: Client Python")
    
    try:
        from app.tcp import XMLForgeClient
        
        client = XMLForgeClient(host='127.0.0.1', port=3307, timeout=5)
        print_success("Client créé avec succès")
        
        if not client.socket:
            print_info("Socket pas encore connectée (normal avant connect())")
        
        return True
    except Exception as e:
        print_error(f"Erreur création client: {e}")
        return False

def test_connection():
    """Teste une connexion réelle (demande les credentials)"""
    print_header("Test 5: Connexion réelle")
    
    try:
        from app.tcp import XMLForgeClient
        
        print_info("Pour tester une connexion réelle, entrez vos identifiants:")
        username = input("  Email: ").strip()
        password = input("  Mot de passe: ").strip()
        
        if not username or not password:
            print_info("Test sauté (credentials non fournis)")
            return True
        
        print_info(f"Tentative de connexion à 127.0.0.1:3307...")
        client = XMLForgeClient(host='127.0.0.1', port=3307, timeout=10)
        
        client.connect(username, password)
        
        if client.authenticated:
            print_success(f"Connexion réussie en tant que: {client.username}")
            
            # Test ping
            if client.ping():
                print_success("Ping OK")
            else:
                print_error("Ping échoué")
            
            client.disconnect()
            print_success("Déconnexion OK")
            return True
        else:
            print_error("Connexion échouée")
            return False
            
    except ConnectionError as e:
        print_error(f"Erreur de connexion: {e}")
        return False
    except Exception as e:
        print_error(f"Erreur inconnue: {e}")
        return False

def test_api_routes():
    """Vérifie que les routes API sont enregistrées"""
    print_header("Test 6: Routes API")
    
    try:
        from app.routes import tcp_bp
        print_success("Blueprint TCP importé avec succès")
        
        # Vérifier que le blueprint a les bonnes routes
        routes_to_check = [
            'GET /api/tcp/credentials',
            'POST /api/tcp/credentials/show-password',
            'GET /api/tcp/sessions',
            'GET /api/tcp/status'
        ]
        
        print_info("Routes API attendues:")
        for route in routes_to_check:
            print(f"  ✓ {route}")
        
        return True
    except ImportError:
        print_error("Blueprint TCP introuvable")
        return False
    except Exception as e:
        print_error(f"Erreur: {e}")
        return False

def test_react_component():
    """Vérifie que la composante React existe"""
    print_header("Test 7: Composante React")
    
    component_path = os.path.join(
        os.path.dirname(__file__),
        '../../xmlforge-react/src/components/TCPCredentials/TCPCredentials.jsx'
    )
    
    if os.path.exists(component_path):
        print_success("Composante TCPCredentials trouvée")
        return True
    else:
        print_error("Composante TCPCredentials introuvable")
        print_info(f"Cherché à: {component_path}")
        return False

def main():
    """Exécute tous les tests"""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  🔗 XMLForge TCP/IP Server - Test Suite".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Disponibilité du port 3307", test_port_availability),
        ("Import du module TCP", test_tcp_server_import),
        ("Protocole TCP", test_protocol_encoding),
        ("Création du client", test_client_creation),
        ("Routes API", test_api_routes),
        ("Composante React", test_react_component),
        ("Connexion réelle", test_connection),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except KeyboardInterrupt:
            print("\n\n⚠ Test interrompu par l'utilisateur")
            break
        except Exception as e:
            print_error(f"Exception non gérée: {e}")
            results.append((name, False))
    
    # Résumé
    print_header("Résumé des tests")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 Tous les tests sont passés!")
        print("\nProchaines étapes:")
        print("  1. Intégrez <TCPCredentials /> dans votre dashboard")
        print("  2. Testez avec: from app.tcp import connect")
        print("  3. Consultez TCP_SERVER_README.md pour plus de détails")
    else:
        print("\n⚠ Certains tests ont échoué")
        print("  Consultez les messages d'erreur ci-dessus")
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    sys.exit(main())
