#!/usr/bin/env python
"""
Crée les credentials TCP pour essoya@gmail.com
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User
from app.services.tcp_credential_service import TcpCredentialService

def create_essoya_tcp():
    app = create_app(Config)
    
    with app.app_context():
        # Récupérer l'utilisateur
        user = User.query.filter_by(email='essoya@gmail.com').first()
        if not user:
            print("✗ Utilisateur essoya@gmail.com introuvable")
            return
        
        print(f"✓ Utilisateur trouvé: {user.email} (ID: {user.id})")
        
        # Supprimer les credentials existants
        existing = TcpCredentialService.get_by_user_id(user.id)
        if existing:
            TcpCredentialService.delete_for_user(user.id)
            print("✓ Anciens credentials TCP supprimés")
        
        # Créer des credentials TCP
        result, error = TcpCredentialService.create_for_user(
            user.id,
            tcp_username='essoya@gmail.com',
            tcp_password='tcp_essoya_password_123'  # Mot de passe spécifique pour TCP
        )
        
        if error:
            print(f"✗ Erreur création credentials: {error}")
            return
        
        print(f"✓ Credentials TCP créés avec succès")
        print(f"\n📝 Pour le fichier .env du tcp-tester:")
        print(f"TCP_HOST=127.0.0.1")
        print(f"TCP_PORT=3307")
        print(f"TCP_USERNAME={result['credential']['tcp_username']}")
        print(f"TCP_PASSWORD={result['plain_password']}")
        print(f"TCP_DATABASE=TP_JAVABD")

if __name__ == '__main__':
    create_essoya_tcp()
