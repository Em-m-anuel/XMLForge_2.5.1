#!/usr/bin/env python
"""
Crée l'utilisateur yannpateyann@gmail.com
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User
from app.services.auth_service import AuthService

def create_yann_user():
    app = create_app(Config)
    
    with app.app_context():
        # Vérifier si l'utilisateur existe déjà
        existing = User.query.filter_by(email='yannpateyann@gmail.com').first()
        if existing:
            print(f"✓ L'utilisateur existe déjà:")
            print(f"  Email: {existing.email}")
            print(f"  Nom: {existing.full_name}")
            print(f"  ID: {existing.id}")
            return
        
        # Créer l'utilisateur
        user, error = AuthService.register(
            full_name='Yann Pate',
            email='yannpateyann@gmail.com',
            password='12345678'
        )
        
        if user:
            print(f"✓ Utilisateur créé avec succès")
            print(f"  Email: yannpateyann@gmail.com")
            print(f"  Mot de passe: 12345678")
            print(f"  ID: {user.id}")
            print(f"  Nom: {user.full_name}")
            print(f"\n🔑 Vous pouvez maintenant utiliser ces identifiants pour TCP/IP")
        else:
            print(f"✗ Erreur lors de la création: {error}")

if __name__ == '__main__':
    create_yann_user()
