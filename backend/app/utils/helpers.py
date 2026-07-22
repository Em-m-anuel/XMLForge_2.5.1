"""
Helpers réutilisables - pas de dépendance Flask
"""
import secrets
import re
from datetime import datetime

def generate_key_identifier():
    """
    Génère une clé unique format XML-9F4A-28BD-71A2
    4 groupes de 4 hex chars uppercase
    """
    groups = [secrets.token_hex(2).upper() for _ in range(3)]
    # token_hex(2) => 4 hex chars
    return f"XML-{groups[0]}-{groups[1]}-{groups[2]}"

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def now_utc():
    return datetime.utcnow()

def is_valid_email(email):
    return re.match(r'^[^@]+@[^@]+\.[^@]+$', email) is not None
