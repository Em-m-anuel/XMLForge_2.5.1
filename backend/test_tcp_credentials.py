#!/usr/bin/env python
"""
Script de test pour les credentials TCP
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User
from app.services.tcp_credential_service import TcpCredentialService

def test_tcp_credentials():
    """Teste la création et récupération des credentials TCP"""
    app = create_app(Config)
    
    with app.app_context():
        # Créer la table
        db.create_all()
        
        # Récupérer l'utilisateur de test
        user = User.query.filter_by(email='user@example.com').first()
        if not user:
            print("✗ Utilisateur de test introuvable")
            return
        
        print(f"✓ Utilisateur trouvé: {user.email} (ID: {user.id})")
        
        # Supprimer les credentials existants
        existing = TcpCredentialService.get_by_user_id(user.id)
        if existing:
            TcpCredentialService.delete_for_user(user.id)
            print("✓ Credentials existants supprimés")
        
        # Créer des credentials
        result, error = TcpCredentialService.create_for_user(user.id)
        if error:
            print(f"✗ Erreur création credentials: {error}")
            return
        
        print(f"✓ Credentials TCP créés")
        print(f"  Username: {result['credential']['tcp_username']}")
        print(f"  Host: {result['credential']['tcp_host']}")
        print(f"  Port: {result['credential']['tcp_port']}")
        print(f"  Mot de passe (à copier!): {result['plain_password']}")
        
        # Récupérer les credentials
        credential = TcpCredentialService.get_by_user_id(user.id)
        if credential:
            print(f"✓ Credentials récupérés depuis la base")
            print(f"  ID: {credential.id}")
            print(f"  User ID: {credential.user_id}")
        
        print("\n📝 Pour le fichier .env du tcp-tester:")
        print(f"TCP_HOST={result['credential']['tcp_host']}")
        print(f"TCP_PORT={result['credential']['tcp_port']}")
        print(f"TCP_USERNAME={result['credential']['tcp_username']}")
        print(f"TCP_PASSWORD={result['plain_password']}")

if __name__ == '__main__':
    test_tcp_credentials()
