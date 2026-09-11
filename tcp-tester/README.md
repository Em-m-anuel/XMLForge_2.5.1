# 🔗 XMLForge TCP Tester — outil d'étude du moteur de données

Application Express + interface web pour tester le serveur TCP/IP XMLForge et
comparer les deux moteurs de requêtes :

- **sqlite** (défaut) : projection SQLite — moteur historique ;
- **xml** : moteur XML natif (lecture/écriture directe sur le fichier XML) ;
- **compare** : exécute la requête sur les deux moteurs et compare les résultats.

## 🚀 Installation

```bash
npm install
cp .env.example .env   # renseigner TCP_HOST, TCP_PORT, TCP_USERNAME, TCP_PASSWORD
npm start              # Express sur http://localhost:3000
```

Les credentials TCP s'obtiennent dans XMLForge (page **API & TCP/IP**), pas avec
le mot de passe web.

## 🧪 Utilisation

1. **Configuration** : hôte, port, utilisateur/mot de passe TCP, base (nom ou ID).
   Le bouton **Tester la connexion** valide l'authentification TCP.
2. **Requête SQL** : saisir `SELECT/INSERT/UPDATE/DELETE`, choisir le moteur,
   cliquer **Exécuter**.
3. **Benchmark** : renseigner **Runs** (1–100), cliquer **Benchmark** → min / max /
   moyenne / médiane réels.
4. **Comparaison** : cliquer **Comparer SQLite ↔ XML** → équivalence, lignes,
   temps réels de chaque moteur.

Toutes les valeurs affichées (temps total, connexion, traitement serveur,
lecture/écriture XML, lignes, taille de réponse) proviennent de mesures réelles
(client Node ou backend) — aucune valeur n'est inventée.

## 🔌 Protocole TCP

```
[type:1 octet][longueur:4 octets big-endian][JSON UTF-8]
```

Le champ `engine` du message `MSG_QUERY` sélectionne le moteur
(`sqlite` | `xml` | `compare`). Le backend renvoie, pour `xml`, des métriques
serveur (total, lecture XML, écriture XML, lignes).

## 📄 API Express

| Route | Description |
|---|---|
| `GET /api/config` | configuration par défaut |
| `POST /api/test-connection` | test d'authentification TCP |
| `POST /api/query` | exécute une requête (`{query, engine, host, port, username, password, database}`) |
| `POST /api/benchmark` | N exécutions (`{query, engine, runs}`) |
| `POST /api/compare` | comparaison SQLite/XML (déléguée au backend) |

Documentation complète du moteur : `backend/XML_ENGINE.md`.
