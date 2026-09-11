/**
 * XMLForge TCP Tester — outil d'étude du moteur de données (SQLite / XML Engine).
 *
 * Sert une interface web (public/index.html) et expose des routes Express qui
 * dialoguent avec le serveur TCP XMLForge via le protocole binaire JSON :
 *
 *   [type:1 octet][longueur:4 octets BE][JSON UTF-8]
 *
 * Capacités :
 *   - configuration hôte / port / identifiants / base / moteur ;
 *   - exécution d'une requête SQL (moteur 'sqlite', 'xml' ou 'compare') ;
 *   - benchmark (plusieurs exécutions, min/max/moyenne/médiane) ;
 *   - comparaison SQLite ↔ moteur XML (délégée au backend via engine=compare).
 *
 * Aucune valeur de performance n'est inventée : tout est mesuré côté client
 * (temps aller-retour, temps de connexion, taille de réponse) et/ou renvoyé
 * par le backend (temps de traitement, lecture/écriture XML).
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const net = require('net');

const app = express();
app.use(cors());
app.use(bodyParser.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, 'public')));

const APP_PORT = process.env.APP_PORT || 3000;

// ---------------------------------------------------------------------------
// Protocole TCP XMLForge (encodage binaire JSON)
// ---------------------------------------------------------------------------
const MSG_AUTH = 1;
const MSG_QUERY = 2;

function packMessage(type, data) {
  const json = Buffer.from(JSON.stringify(data), 'utf-8');
  const len = Buffer.alloc(4);
  len.writeUInt32BE(json.length, 0);
  const typeBuffer = Buffer.alloc(1);
  typeBuffer.writeUInt8(type, 0);
  return Buffer.concat([typeBuffer, len, json]);
}

function unpackMessage(buffer) {
  if (buffer.length < 5) return null;
  const type = buffer.readUInt8(0);
  const length = buffer.readUInt32BE(1);
  if (buffer.length < 5 + length) return null;
  const data = JSON.parse(buffer.toString('utf-8', 5, 5 + length));
  return { type, data, consumed: 5 + length };
}

// ---------------------------------------------------------------------------
// Client TCP de test (une connexion par session d'étude)
// ---------------------------------------------------------------------------
class StudyClient {
  constructor(cfg) {
    this.cfg = cfg;
    this.socket = null;
    this.buffer = Buffer.alloc(0);
    this.sessionToken = null;
    this.connectedAt = null;
  }

  _connectSocket() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection(Number(this.cfg.port), this.cfg.host, () => resolve());
      this.socket.on('error', reject);
    });
  }

  _send(type, data) {
    this.buffer = Buffer.alloc(0);
    this.socket.write(packMessage(type, data));
  }

  _receive() {
    return new Promise((resolve, reject) => {
      let timer = null;
      const onData = (chunk) => {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        const message = unpackMessage(this.buffer);
        if (message) {
          if (timer) clearTimeout(timer);
          this.buffer = this.buffer.slice(message.consumed);
          this.socket.removeListener('data', onData);
          resolve(message.data);
        }
      };
      this.socket.on('data', onData);
      timer = setTimeout(() => {
        this.socket.removeListener('data', onData);
        reject(new Error('Timeout TCP (15s)'));
      }, 15000);
    });
  }

  async connect() {
    const t0 = Date.now();
    await this._connectSocket();
    this._send(MSG_AUTH, {
      username: this.cfg.username,
      password: this.cfg.password,
      ...(this.cfg.database ? { database: this.cfg.database } : {}),
    });
    const response = await this._receive();
    const connectMs = Date.now() - t0;
    if (response && response.status === 0) {
      this.sessionToken = response.session_token;
      return { connectMs, server: response };
    }
    throw new Error((response && response.message) || 'Authentification TCP échouée');
  }

  async executeRaw(query, engine) {
    const t0 = Date.now();
    this._send(MSG_QUERY, { query, session_token: this.sessionToken, ...(engine ? { engine } : {}) });
    const response = await this._receive();
    const totalMs = Date.now() - t0;
    return { response, totalMs };
  }

  disconnect() {
    if (this.socket) {
      try { this.socket.end(); } catch (e) { /* ignore */ }
      this.socket = null;
    }
  }
}

function resolveConfig(overrides = {}) {
  return {
    host: overrides.host || process.env.TCP_HOST || '127.0.0.1',
    port: Number(overrides.port || process.env.TCP_PORT || 3307),
    username: overrides.username || process.env.TCP_USERNAME || '',
    password: overrides.password || process.env.TCP_PASSWORD || '',
    database: overrides.database || process.env.TCP_DATABASE || null,
  };
}

function extractRows(result) {
  if (!result) return null;
  if (Array.isArray(result.rows)) return result.rows.length;
  if (typeof result.count === 'number') return result.count;
  if (typeof result.inserted === 'number') return result.inserted;
  if (typeof result.updated === 'number') return result.updated;
  if (typeof result.deleted === 'number') return result.deleted;
  if (result.row) return 1;
  return null;
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------
app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

app.get('/api/config', (req, res) => {
  const cfg = resolveConfig();
  res.json({
    host: cfg.host,
    port: cfg.port,
    username: cfg.username,
    hasPassword: Boolean(cfg.password),
    database: cfg.database,
    engines: ['sqlite', 'xml', 'compare'],
  });
});

app.post('/api/test-connection', async (req, res) => {
  try {
    const cfg = resolveConfig(req.body || {});
    const client = new StudyClient(cfg);
    const { connectMs, server } = await client.connect();
    client.disconnect();
    res.json({
      success: true,
      connect_ms: connectMs,
      server: {
        host: cfg.host,
        port: cfg.port,
        username: cfg.username,
        session_token: server.session_token,
        database_id: server.database_id || null,
        database_name: server.database_name || null,
      },
    });
  } catch (err) {
    res.status(502).json({ success: false, error: err.message });
  }
});

app.post('/api/query', async (req, res) => {
  const { query } = req.body || {};
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ success: false, error: 'Query requise (string)' });
  }
  try {
    const cfg = resolveConfig(req.body || {});
    const engine = req.body.engine || 'sqlite';
    const client = new StudyClient(cfg);
    const { connectMs } = await client.connect();
    const { response, totalMs } = await client.executeRaw(query, engine);
    client.disconnect();

    if (response.status !== 2) {
      return res.status(200).json({
        success: false,
        error: response.message || 'Erreur requête',
        code: response.code,
        engine,
        metrics: { total_ms: totalMs, connect_ms: connectMs, response_bytes: 0 },
      });
    }
    const result = response.result;
    const serverMetrics = response.metrics || null;
    const comparison = response.comparison || null;
    res.json({
      success: true,
      engine: response.engine || engine,
      result,
      comparison,
      metrics: {
        total_ms: totalMs,
        connect_ms: connectMs,
        network_ms: serverMetrics ? Math.max(0, totalMs - serverMetrics.total_ms) : null,
        server_ms: serverMetrics ? serverMetrics.total_ms : null,
        parse_ms: serverMetrics ? serverMetrics.parse_ms : null,
        exec_ms: serverMetrics ? serverMetrics.exec_ms : null,
        read_xml_ms: serverMetrics ? serverMetrics.read_ms : null,
        write_xml_ms: serverMetrics ? serverMetrics.write_ms : null,
        rows: extractRows(result),
        response_bytes: JSON.stringify(response).length,
        engine: serverMetrics ? serverMetrics.engine : engine,
      },
    });
  } catch (err) {
    res.status(502).json({ success: false, error: err.message });
  }
});

app.post('/api/benchmark', async (req, res) => {
  const { query, engine, runs } = req.body || {};
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ success: false, error: 'Query requise' });
  }
  const nRuns = Math.max(1, Math.min(Number(runs) || 10, 100));
  try {
    const cfg = resolveConfig(req.body || {});
    const eng = engine || 'sqlite';
    const client = new StudyClient(cfg);
    await client.connect();
    const perRun = [];
    let rows = null;
    for (let i = 0; i < nRuns; i++) {
      const { response, totalMs } = await client.executeRaw(query, eng);
      if (response.status !== 2) {
        client.disconnect();
        return res.status(200).json({ success: false, error: response.message, run: i + 1 });
      }
      const serverMetrics = response.metrics || null;
      rows = extractRows(response.result);
      perRun.push({
        run: i + 1,
        total_ms: totalMs,
        server_ms: serverMetrics ? serverMetrics.total_ms : null,
        parse_ms: serverMetrics ? serverMetrics.parse_ms : null,
        exec_ms: serverMetrics ? serverMetrics.exec_ms : null,
        read_xml_ms: serverMetrics ? serverMetrics.read_ms : null,
        write_xml_ms: serverMetrics ? serverMetrics.write_ms : null,
      });
    }
    client.disconnect();

    const totals = perRun.map(r => r.total_ms).sort((a, b) => a - b);
    const avg = totals.reduce((s, v) => s + v, 0) / totals.length;
    const median = totals.length % 2
      ? totals[(totals.length - 1) / 2]
      : (totals[totals.length / 2 - 1] + totals[totals.length / 2]) / 2;
    res.json({
      success: true,
      engine: eng,
      runs: nRuns,
      rows,
      min_ms: totals[0],
      max_ms: totals[totals.length - 1],
      avg_ms: avg,
      median_ms: median,
      per_run: perRun,
    });
  } catch (err) {
    res.status(502).json({ success: false, error: err.message });
  }
});

app.post('/api/compare', async (req, res) => {
  const { query } = req.body || {};
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ success: false, error: 'Query requise' });
  }
  try {
    const cfg = resolveConfig(req.body || {});
    const client = new StudyClient(cfg);
    const { connectMs } = await client.connect();
    const { response, totalMs } = await client.executeRaw(query, 'compare');
    client.disconnect();
    if (response.status !== 2 || !response.comparison) {
      return res.status(200).json({
        success: false,
        error: (response.message || 'Comparaison indisponible (moteur compare non supporté)'),
        engine: 'compare',
      });
    }
    res.json({ success: true, comparison: response.comparison, total_ms: totalMs, connect_ms: connectMs });
  } catch (err) {
    res.status(502).json({ success: false, error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Suite de benchmark par catégories (lecture sur les deux moteurs, écriture
// sur table de travail temporaire — les données réelles ne sont pas altérées).
// ---------------------------------------------------------------------------
const BENCH_READ_CATEGORIES = [
  ['SELECT simple', 'SELECT * FROM books LIMIT 50'],
  ['SELECT filtré', 'SELECT * FROM books WHERE category_id = 1'],
  ['ORDER BY', 'SELECT * FROM books ORDER BY price DESC LIMIT 100'],
  ['Pagination', 'SELECT * FROM books LIMIT 25 OFFSET 100'],
  ['COUNT', 'SELECT COUNT(*) FROM books'],
  ['JOIN', 'SELECT b.title, c.name FROM books b JOIN categories c ON b.category_id = c.id LIMIT 100'],
  ['Complexe (GROUP BY + HAVING)', 'SELECT category_id, COUNT(*) AS n, SUM(price) AS total FROM books GROUP BY category_id HAVING COUNT(*) > 5 ORDER BY total DESC'],
];

function statsOf(arr) {
  const s = [...arr].sort((a, b) => a - b);
  return {
    min_ms: s[0],
    max_ms: s[s.length - 1],
    avg_ms: s.reduce((x, y) => x + y, 0) / s.length,
    median_ms: s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2,
    runs: s.length,
  };
}

app.post('/api/benchmark-suite', async (req, res) => {
  const cfg = resolveConfig(req.body || {});
  const runs = Math.max(1, Math.min(Number(req.body.runs) || 5, 30));
  const client = new StudyClient(cfg);
  try {
    await client.connect();
    const read = {};
    for (const [label, query] of BENCH_READ_CATEGORIES) {
      read[label] = {};
      for (const engine of ['sqlite', 'xml']) {
        const perRun = [];
        for (let i = 0; i < runs; i++) {
          const { response, totalMs } = await client.executeRaw(query, engine);
          if (response.status !== 2) {
            read[label][engine] = { error: response.message };
            break;
          }
          perRun.push(totalMs);
        }
        if (perRun.length) read[label][engine] = statsOf(perRun);
      }
    }

    // Écritures sur une table de travail, supprimée en fin de suite.
    await client.executeRaw('CREATE TABLE bench_scratch (id INT PRIMARY KEY AUTO_INCREMENT NOT NULL, label VARCHAR)', 'sqlite');
    const write = {};
    for (const engine of ['sqlite', 'xml']) {
      await client.executeRaw("INSERT INTO bench_scratch (label) VALUES ('target')", engine);
      const ins = [], upd = [], del = [];
      for (let i = 0; i < runs; i++) {
        ins.push((await client.executeRaw("INSERT INTO bench_scratch (label) VALUES ('x')", engine)).totalMs);
        upd.push((await client.executeRaw("UPDATE bench_scratch SET label = 'u' WHERE label = 'target'", engine)).totalMs);
        del.push((await client.executeRaw("DELETE FROM bench_scratch WHERE label = 'x'", engine)).totalMs);
      }
      write[engine] = { insert: statsOf(ins), update: statsOf(upd), delete: statsOf(del) };
    }
    await client.executeRaw('DROP TABLE bench_scratch', 'sqlite');
    client.disconnect();
    res.json({ success: true, runs, read, write });
  } catch (err) {
    try { client.disconnect(); } catch (e) { /* ignore */ }
    res.status(502).json({ success: false, error: err.message });
  }
});

// ---------------------------------------------------------------------------
app.listen(APP_PORT, () => {
  console.log(`\n✅ XMLForge TCP Tester démarré`);
  console.log(`🌐 Interface: http://localhost:${APP_PORT}`);
  console.log(`📡 TCP par défaut: ${process.env.TCP_HOST || '127.0.0.1'}:${process.env.TCP_PORT || 3307}`);
  console.log('   Moteurs supportés: sqlite (défaut), xml, compare');
});
