# 🔗 XMLForge TCP Server Tester - Express App

Petite application Express avec une interface web pour tester le serveur TCP/IP XMLForge.

## 🚀 Installation

### 1. Créer le fichier `.env`

Copiez `.env.example` vers `.env` et remplissez avec vos valeurs:

```bash
cp .env.example .env
```

Éditez `.env`:

```env
# Adresse et port du serveur TCP XMLForge
TCP_HOST=127.0.0.1
TCP_PORT=3307

# Votre email et mot de passe (obtenez-les depuis l'interface XMLForge)
TCP_USERNAME=user@example.com
TCP_PASSWORD=your_password_here

# Base de données (optionnel)
TCP_DATABASE=

# Port de cette app
APP_PORT=3000

# Mode debug
DEBUG=true
```

### 2. Installer les dépendances

```bash
npm install
```

ou

```bash
yarn install
```

### 3. Démarrer l'application

**Mode production:**
```bash
npm start
```

**Mode développement (avec auto-reload):**
```bash
npm run dev
```

L'app sera disponible sur **http://localhost:3000**

## 📖 Utilisation

### Interface Web

Ouvrez http://localhost:3000 dans votre navigateur.

Vous verrez:
- ✓ **Statut de connexion** - Vérifie que le serveur TCP est accessible
- ✓ **Configuration** - Affiche l'hôte, port et username
- ✓ **Éditeur de requête** - Deux onglets:
  - **Requête brute**: Entrez du SQL directement
  - **Builder**: Formulaire pour construire la requête

### Fonctionnalités

#### 1. Test de Connexion

Cliquez sur "Test Connexion" pour vérifier que le serveur est accessible.

#### 2. Requête Brute (Onglet 1)

Entrez n'importe quelle requête SQL:

```sql
SELECT * FROM users
INSERT INTO users (name, email) VALUES ('John', 'john@example.com')
UPDATE users SET status='active' WHERE id=1
DELETE FROM users WHERE id=999
```

#### 3. Query Builder (Onglet 2)

Utilisez le formulaire pour construire la requête:

**SELECT:**
- Table: `users`
- Colonnes: `*` ou `id, name, email`
- WHERE: `status='active'` (optionnel)

**INSERT:**
- Table: `users`
- Données (JSON): `{"name": "John", "email": "john@example.com"}`

**UPDATE:**
- Table: `users`
- Données: `{"status": "active"}`
- WHERE: `id=1`

**DELETE:**
- Table: `users`
- WHERE: `id=999`

## 🔌 API REST

L'app expose des endpoints REST que vous pouvez utiliser:

### Test Connexion
```bash
POST /api/test-connection
```

Response:
```json
{
  "success": true,
  "message": "Connexion réussie!",
  "config": {
    "host": "127.0.0.1",
    "port": 3307,
    "username": "user@example.com"
  }
}
```

### Requête brute
```bash
POST /api/query

{
  "query": "SELECT * FROM users"
}
```

Response:
```json
{
  "success": true,
  "query": "SELECT * FROM users",
  "result": { ... }
}
```

### SELECT
```bash
POST /api/select

{
  "table": "users",
  "columns": "*",
  "where": "status='active'"  // optionnel
}
```

### INSERT
```bash
POST /api/insert

{
  "table": "users",
  "data": {
    "name": "John",
    "email": "john@example.com"
  }
}
```

### UPDATE
```bash
POST /api/update

{
  "table": "users",
  "data": {
    "status": "active"
  },
  "where": "id=1"
}
```

### DELETE
```bash
POST /api/delete

{
  "table": "users",
  "where": "id=999"
}
```

## 📝 Exemples avec cURL

### Test connexion
```bash
curl -X POST http://localhost:3000/api/test-connection
```

### SELECT
```bash
curl -X POST http://localhost:3000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM users"
  }'
```

### INSERT
```bash
curl -X POST http://localhost:3000/api/insert \
  -H "Content-Type: application/json" \
  -d '{
    "table": "users",
    "data": {
      "name": "Alice",
      "email": "alice@example.com"
    }
  }'
```

### UPDATE
```bash
curl -X POST http://localhost:3000/api/update \
  -H "Content-Type: application/json" \
  -d '{
    "table": "users",
    "data": {
      "status": "active"
    },
    "where": "email=\"alice@example.com\""
  }'
```

### DELETE
```bash
curl -X POST http://localhost:3000/api/delete \
  -H "Content-Type: application/json" \
  -d '{
    "table": "users",
    "where": "id=999"
  }'
```

## 🐍 Exemples avec Python

```python
import requests

BASE_URL = 'http://localhost:3000/api'

# Test connexion
response = requests.post(f'{BASE_URL}/test-connection')
print(response.json())

# SELECT
response = requests.post(f'{BASE_URL}/select', json={
    'table': 'users',
    'where': "status='active'"
})
print(response.json())

# INSERT
response = requests.post(f'{BASE_URL}/insert', json={
    'table': 'users',
    'data': {
        'name': 'John',
        'email': 'john@example.com'
    }
})
print(response.json())

# UPDATE
response = requests.post(f'{BASE_URL}/update', json={
    'table': 'users',
    'data': {'status': 'active'},
    'where': "id=1"
})
print(response.json())

# DELETE
response = requests.post(f'{BASE_URL}/delete', json={
    'table': 'users',
    'where': 'id=999'
})
print(response.json())
```

## 🐛 Troubleshooting

### "Cannot import module"

```bash
npm install
```

### "Connection refused"

Vérifiez que:
1. Le serveur Flask XMLForge est en cours d'exécution: `python run.py`
2. Le port TCP 3307 est ouvert
3. Les credentials dans `.env` sont corrects

### "Authentification échouée"

Vérifiez:
1. `TCP_USERNAME` = votre email XMLForge
2. `TCP_PASSWORD` = votre mot de passe XMLForge
3. Votre compte est actif (not archived)

### "Port 3000 déjà en utilisation"

Changez le port dans `.env`:
```env
APP_PORT=3001
```

Puis redémarrez l'app.

## 📦 Structure

```
tcp-tester/
├── app.js              (Application Express)
├── package.json        (Dépendances)
├── .env.example        (Template de configuration)
├── .env                (Configuration - NE PAS commiter!)
├── .gitignore          (Ignorer node_modules, .env, etc)
├── README.md           (Ce fichier)
└── public/
    └── index.html      (Interface web)
```

## 🚀 Déploiement

Pour un déploiement en production:

1. **Configurez les variables d'environnement** sur le serveur
2. **Utilisez un gestionnaire de processus** (pm2, systemd, etc)
3. **Mettez en place un reverse proxy** (nginx, Apache)
4. **Activez le TLS/SSL** pour sécuriser les communications

Exemple avec PM2:

```bash
npm install -g pm2
pm2 start app.js --name "xmlforge-tester"
pm2 save
pm2 startup
```

Exemple de configuration nginx:

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Architecture

```
┌─────────────────────┐
│   Navigateur Web    │
│  (http://localhost)│
└──────────┬──────────┘
           │
    ┌──────▼──────────┐
    │  Express App    │
    │  (Port 3000)    │
    │                 │
    │ - API REST      │
    │ - Client TCP    │
    └──────┬──────────┘
           │
      ┌────▼─────────┐
      │ TCP Protocol │
      │ (Port 3307)  │
      └──────────────┘
           │
      ┌────▼────────────┐
      │ XMLForge Backend│
      │ (Python/Flask) │
      │                │
      │ Database (XML) │
      └────────────────┘
```

## 📚 Documentation

- [TCP_SERVER_README.md](../backend/TCP_SERVER_README.md) - Doc serveur TCP
- [QUICKSTART.md](../QUICKSTART.md) - Guide de démarrage rapide
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Architecture

## 🔐 Sécurité

⚠️ **Important:**

- Ne commitez jamais le fichier `.env` avec les vrais credentials
- Utilisez des variables d'environnement en production
- Activez TLS/SSL pour les communications en production
- Limitez l'accès à l'API avec un firewall ou authentification

## 💡 Astuces

### Debug mode

Activez le mode debug dans `.env`:
```env
DEBUG=true
```

Les logs afficheront plus de détails.

### Test rapide de la connexion

```bash
curl -X POST http://localhost:3000/api/test-connection | jq
```

### Utiliser avec Postman

Importez les endpoints REST dans Postman:
1. POST http://localhost:3000/api/test-connection
2. POST http://localhost:3000/api/query
3. POST http://localhost:3000/api/select
4. POST http://localhost:3000/api/insert
5. POST http://localhost:3000/api/update
6. POST http://localhost:3000/api/delete

## 🤝 Support

Problème? Consultez:
1. Les logs de la console Express
2. La barre de statut dans l'interface web
3. Les erreurs affichées dans les alerts

---

**Version**: 1.0.0  
**Status**: ✅ Production-ready  
**Dernière mise à jour**: 2026-08-11
