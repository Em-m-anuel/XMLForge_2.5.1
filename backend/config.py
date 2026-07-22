"""
Compatibilité: config.py à la racine backend qui importe depuis app/config.py
"""
from app.config import Config, ProductionConfig, TestingConfig

__all__ = ['Config', 'ProductionConfig', 'TestingConfig']
