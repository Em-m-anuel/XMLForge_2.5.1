#!/usr/bin/env python
"""
Vérifie si un utilisateur existe dans la base
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.user import User

def check_user():
    app = create_app(Config)
    
    with app.app_context():
        # Chercher l'utilisateur
        user = User.query.filter_by(email='yannpateyann@gmail.com').first()
        
        if user:
            print(f"✓ Utilisateur trouvé:")
            print(f"  ID: {user.id}")
            print(f"  Email: {user.email}")
            print(f"  Nom: {user.full_name}")
            print(f"  Actif: {user.is_active}")
        else:
            print("✗ Utilisateur yannpateyann@gmail.com introuvable")
            print("\nUtilisateurs dans la base:")
            users = User.query.all()
            for u in users:
                print(f"  - {u.email} (ID: {u.id}, Actif: {u.is_active})")

if __name__ == '__main__':
    check_user()
