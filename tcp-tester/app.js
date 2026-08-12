/**
 * Application Express pour tester le serveur TCP XMLForge
 * Port: 3000 (configurable via .env)
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');

const app = express();

// ============================================================================
// Middleware
// ============================================================================

app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));
app.use(bodyParser.urlencoded({ limit: '10mb', extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// ============================================================================
// Vérifier les variables d'environnement
// ============================================================================

const requiredEnvVars = [
  'TCP_HOST',
  'TCP_PORT',
  'TCP_USERNAME',
  'TCP_PASSWORD'
];

const missingEnvVars = requiredEnvVars.filter(varName => !process.env[varName]);

if (missingEnvVars.length > 0) {
  console.error('❌ Variables d\'environnement manquantes:');
  missingEnvVars.forEach(v => console.error(`   - ${v}`));
  console.error('\nCopiez .env.example vers .env et remplissez les valeurs:');
  console.error('  cp .env.example .env');
  process.exit(1);
}

// ============================================================================
// Configuration
// ============================================================================

const TCP_CONFIG = {
  host: process.env.TCP_HOST,
  port: parseInt(process.env.TCP_PORT),
  username: process.env.TCP_USERNAME,
  password: process.env.TCP_PASSWORD,
  database: process.env.TCP_DATABASE || null
};

const DEBUG = process.env.DEBUG === 'true';
const APP_PORT = process.env.APP_PORT || 3000;

if (DEBUG) {
  console.log('🔧 Configuration TCP:');
  console.log(`   Host: ${TCP_CONFIG.host}`);
  console.log(`   Port: ${TCP_CONFIG.port}`);
  console.log(`   Username: ${TCP_CONFIG.username}`);
  console.log(`   Database: ${TCP_CONFIG.database || '(none)'}`);
}

// ============================================================================
// Client TCP Node.js (implémentation simple)
// ============================================================================

const net = require('net');
const { Buffer } = require('buffer');

// Pool de connexions pour réutiliser les sockets
const connectionPool = new Map();

class XMLForgeClient {
  constructor(config) {
    this.config = config;
    this.socket = null;
    this.sessionToken = null;
    this.authenticated = false;
    this.buffer = Buffer.alloc(0);
    this.poolKey = `${config.host}:${config.port}:${config.username}`;
  }

  async connect() {
    return new Promise((resolve, reject) => {
      // Vérifier si une connexion existe déjà dans le pool
      if (connectionPool.has(this.poolKey)) {
        const pooled = connectionPool.get(this.poolKey);
        if (pooled.authenticated && pooled.socket && !pooled.socket.destroyed) {
          this.socket = pooled.socket;
          this.sessionToken = pooled.sessionToken;
          this.authenticated = true;
          console.log('🔄 Réutilisation connexion existante');
          resolve(true);
          return;
        } else {
          // Connexion invalide, supprimer du pool
          connectionPool.delete(this.poolKey);
        }
      }

      this.socket = net.createConnection(
        this.config.port,
        this.config.host,
        async () => {
          try {
            // Envoyer requête d'auth
            const authMsg = this.createAuthMessage(
              this.config.username,
              this.config.password,
              this.config.database
            );
            
            this.socket.write(authMsg);
            
            // Attendre la réponse
            const response = await this.receiveMessage();
            
            if (response && response.status === 0) {
              this.sessionToken = response.session_token;
              this.authenticated = true;
              
              // Ajouter au pool
              connectionPool.set(this.poolKey, {
                socket: this.socket,
                sessionToken: this.sessionToken,
                authenticated: true,
                timestamp: Date.now()
              });
              
              resolve(true);
            } else {
              reject(new Error('Authentification échouée'));
            }
          } catch (err) {
            reject(err);
          }
        }
      );

      this.socket.on('error', reject);
      this.socket.setTimeout(10000);
    });
  }

  createAuthMessage(username, password, database = null) {
    const data = {
      username,
      password,
      ...(database && { database })
    };
    return this.packMessage(1, data);
  }

  createQueryMessage(query) {
    const data = {
      query,
      session_token: this.sessionToken
    };
    return this.packMessage(2, data);
  }

  packMessage(type, data) {
    const jsonStr = JSON.stringify(data);
    const jsonBuffer = Buffer.from(jsonStr, 'utf-8');
    const lengthBuffer = Buffer.alloc(4);
    lengthBuffer.writeUInt32BE(jsonBuffer.length, 0);
    
    const typeBuffer = Buffer.alloc(1);
    typeBuffer.writeUInt8(type, 0);
    
    return Buffer.concat([typeBuffer, lengthBuffer, jsonBuffer]);
  }

  async receiveMessage() {
    return new Promise((resolve, reject) => {
      const onData = (data) => {
        this.buffer = Buffer.concat([this.buffer, data]);
        console.log('📥 Données reçues:', this.buffer.length, 'octets');
        
        if (this.buffer.length >= 5) {
          try {
            const type = this.buffer.readUInt8(0);
            const length = this.buffer.readUInt32BE(1);
            console.log('📦 Message type:', type, 'length:', length);
            
            if (this.buffer.length >= 5 + length) {
              const jsonStr = this.buffer.toString('utf-8', 5, 5 + length);
              const parsed = JSON.parse(jsonStr);
              console.log('✅ Message parsé:', parsed);
              this.buffer = this.buffer.slice(5 + length);
              
              this.socket.removeListener('data', onData);
              resolve(parsed);
            }
          } catch (err) {
            console.error('❌ Erreur parsing message:', err);
            this.socket.removeListener('data', onData);
            reject(err);
          }
        }
      };

      this.socket.on('data', onData);
      this.socket.setTimeout(5000, () => {
        this.socket.removeListener('data', onData);
        reject(new Error('Timeout'));
      });
    });
  }

  async execute(query) {
    if (!this.authenticated) {
      throw new Error('Non authentifié');
    }

    return new Promise((resolve, reject) => {
      try {
        const msg = this.createQueryMessage(query);
        this.socket.write(msg);

        const onData = (data) => {
          this.buffer = Buffer.concat([this.buffer, data]);
          
          if (this.buffer.length >= 5) {
            try {
              const type = this.buffer.readUInt8(0);
              const length = this.buffer.readUInt32BE(1);
              
              if (this.buffer.length >= 5 + length) {
                const jsonStr = this.buffer.toString('utf-8', 5, 5 + length);
                const parsed = JSON.parse(jsonStr);
                this.buffer = this.buffer.slice(5 + length);
                
                this.socket.removeListener('data', onData);
                
                if (parsed.status === 2) {
                  resolve(parsed.result || {});
                } else {
                  reject(new Error(parsed.message || 'Erreur requête'));
                }
              }
            } catch (err) {
              this.socket.removeListener('data', onData);
              reject(err);
            }
          }
        };

        this.socket.on('data', onData);
        this.socket.setTimeout(5000);
      } catch (err) {
        reject(err);
      }
    });
  }

  close() {
    // Ne pas fermer la socket si elle est dans le pool
    // Elle sera réutilisée pour les prochaines requêtes
    if (this.socket && !connectionPool.has(this.poolKey)) {
      this.socket.end();
      this.socket = null;
    }
    // Si dans le pool, ne rien faire - la socket reste ouverte
  }
}

// ============================================================================
// Routes
// ============================================================================

// Page d'accueil
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Tester la connexion
app.post('/api/test-connection', async (req, res) => {
  try {
    console.log('🔍 Test de connexion TCP...');
    console.log('Config:', TCP_CONFIG);
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();
    client.close();
    
    console.log('✅ Connexion TCP réussie');
    res.json({
      success: true,
      message: 'Connexion réussie!',
      config: {
        host: TCP_CONFIG.host,
        port: TCP_CONFIG.port,
        username: TCP_CONFIG.username
      }
    });
  } catch (err) {
    console.error('❌ Erreur connexion TCP:', err);
    console.error('Stack:', err.stack);
    res.status(500).json({
      success: false,
      error: err.message,
      stack: err.stack
    });
  }
});

// Exécuter une requête
app.post('/api/query', async (req, res) => {
  const { query } = req.body;

  if (!query || typeof query !== 'string') {
    return res.status(400).json({
      success: false,
      error: 'Query requise (string)'
    });
  }

  try {
    console.log('🔍 Exécution requête:', query);
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();
    
    const result = await client.execute(query);
    client.close();

    console.log('✅ Requête exécutée avec succès');
    res.json({
      success: true,
      result,
      query
    });
  } catch (err) {
    console.error('❌ Erreur exécution requête:', err);
    res.status(500).json({
      success: false,
      error: err.message,
      query
    });
  }
});

// SELECT
app.post('/api/select', async (req, res) => {
  const { table, columns = '*', where = null } = req.body;

  if (!table) {
    return res.status(400).json({
      success: false,
      error: 'Table requise'
    });
  }

  try {
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();
    
    let query = `SELECT ${columns} FROM ${table}`;
    if (where) {
      query += ` WHERE ${where}`;
    }

    const result = await client.execute(query);
    client.close();

    res.json({
      success: true,
      result,
      query
    });
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message
    });
  }
});

// INSERT
app.post('/api/insert', async (req, res) => {
  const { table, data } = req.body;

  if (!table || !data) {
    return res.status(400).json({
      success: false,
      error: 'Table et data requises'
    });
  }

  try {
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();

    const columns = Object.keys(data).join(', ');
    const values = Object.values(data)
      .map(v => typeof v === 'string' ? `'${v}'` : v)
      .join(', ');
    
    const query = `INSERT INTO ${table} (${columns}) VALUES (${values})`;

    const result = await client.execute(query);
    client.close();

    res.json({
      success: true,
      result,
      query
    });
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message
    });
  }
});

// UPDATE
app.post('/api/update', async (req, res) => {
  const { table, data, where } = req.body;

  if (!table || !data || !where) {
    return res.status(400).json({
      success: false,
      error: 'Table, data et where requises'
    });
  }

  try {
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();

    const set = Object.entries(data)
      .map(([k, v]) => `${k}='${v}'`)
      .join(', ');
    
    const query = `UPDATE ${table} SET ${set} WHERE ${where}`;

    const result = await client.execute(query);
    client.close();

    res.json({
      success: true,
      result,
      query
    });
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message
    });
  }
});

// DELETE
app.post('/api/delete', async (req, res) => {
  const { table, where } = req.body;

  if (!table || !where) {
    return res.status(400).json({
      success: false,
      error: 'Table et where requises'
    });
  }

  try {
    const client = new XMLForgeClient(TCP_CONFIG);
    await client.connect();

    const query = `DELETE FROM ${table} WHERE ${where}`;
    const result = await client.execute(query);
    client.close();

    res.json({
      success: true,
      result,
      query
    });
  } catch (err) {
    res.status(500).json({
      success: false,
      error: err.message
    });
  }
});

// ============================================================================
// Démarrage du serveur
// ============================================================================

app.listen(APP_PORT, () => {
  console.log('\n✅ Serveur Express démarré');
  console.log(`🌐 URL: http://localhost:${APP_PORT}`);
  console.log(`📡 TCP Server: ${TCP_CONFIG.host}:${TCP_CONFIG.port}`);
  console.log(`👤 Username: ${TCP_CONFIG.username}`);
  console.log('\n📝 Documentation: http://localhost:3000');
});
