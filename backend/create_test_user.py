#!/usr/bin/env python
"""
Crée un utilisateur de test pour les connexions TCP/IP
"""
import sys
import os

# Ajouter le répertoire backend au path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User
from app.services.auth_service import AuthService

def create_test_user():
    """Crée un utilisateur de test"""
    app = create_app(Config)
    
    with app.app_context():
        # Vérifier si l'utilisateur existe déjà
        existing = User.query.filter_by(email='user@example.com').first()
        if existing:
            print(f"✓ L'utilisateur 'user@example.com' existe déjà")
            print(f"  ID: {existing.id}")
            print(f"  Nom: {existing.full_name}")
            print(f"  Actif: {existing.is_active}")
            return
        
        # Créer l'utilisateur
        user, error = AuthService.register(
            full_name='Test User',
            email='user@example.com',
            password='password'
        )
        
        if user:
            print(f"✓ Utilisateur créé avec succès")
            print(f"  Email: user@example.com")
            print(f"  Mot de passe: password")
            print(f"  ID: {user.id}")
            print(f"  Nom: {user.full_name}")
        else:
            print(f"✗ Erreur lors de la création: {error}")

if __name__ == '__main__':
    create_test_user()
