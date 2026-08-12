#!/usr/bin/env python
"""
Récupère les tables de la base TP_JAVABD
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config import Config
from app.extensions import db
from app.models.database import Database
from app.models.table import Table

def get_tables():
    app = create_app(Config)
    
    with app.app_context():
        # Récupérer la base TP_JAVABD
        database = Database.query.filter_by(name='TP_JAVABD').first()
        if not database:
            print("✗ Base TP_JAVABD introuvable")
            return
        
        print(f"✓ Base trouvée: {database.name} (ID: {database.id})")
        
        # Récupérer les tables
        tables = Table.query.filter_by(database_id=database.id).all()
        
        print(f"\n📋 Tables dans TP_JAVABD ({len(tables)} tables):")
        print("=" * 60)
        
        for table in tables:
            print(f"\n📌 Table: {table.name}")
            print(f"   ID: {table.id}")
            print(f"   UUID: {table.uuid}")
            print(f"   Commentaire: {table.comment or 'N/A'}")
            print(f"   Statut: {table.status}")
            print(f"   File Identifier: {table.file_identifier or 'N/A'}")
            
            # Récupérer les colonnes
            from app.models.column import Column
            columns = Column.query.filter_by(table_id=table.id).all()
            print(f"   Colonnes ({len(columns)}):")
            for col in columns:
                print(f"      - {col.name} ({col.type})")
            
            print("\n" + "-" * 60)

if __name__ == '__main__':
    get_tables()
