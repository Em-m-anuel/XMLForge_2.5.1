import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../services/api';
import './TCPCredentials.css';

export const TCPCredentials = () => {
  const { user } = useAuth();
  const [credentials, setCredentials] = useState(null);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [fullCredentials, setFullCredentials] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    fetchCredentials();
  }, []);

  const fetchCredentials = async () => {
    try {
      setLoading(true);
      const response = await api.get('/tcp/credentials');
      setCredentials(response.data.data);
      setError(null);
    } catch (err) {
      setError('Impossible de récupérer les credentials');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleShowPassword = async () => {
    try {
      setLoading(true);
      const response = await api.post('/tcp/credentials/show-password', {
        current_password: password
      });
      setFullCredentials(response.data.data);
      setSuccess('Credentials affichés');
      setShowPassword(true);
      setError(null);
    } catch (err) {
      setError(err.response?.data?.message || 'Mot de passe incorrect');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    setSuccess(`${label} copié`);
    setTimeout(() => setSuccess(null), 2000);
  };

  const copyConnectionString = () => {
    if (fullCredentials?.connection_string) {
      copyToClipboard(fullCredentials.connection_string, 'Connection string');
    }
  };

  return (
    <div className="tcp-credentials-container">
      <div className="tcp-header">
        <h2>🔗 Connexion TCP/IP</h2>
        <p>Utilisez ces identifiants pour vous connecter à XMLForge via TCP/IP sur le port 3307</p>
      </div>

      {error && (
        <div className="tcp-alert alert-error">
          <span>{error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {success && (
        <div className="tcp-alert alert-success">
          <span>{success}</span>
        </div>
      )}

      {loading && <div className="tcp-loading">Chargement...</div>}

      {credentials && (
        <div className="tcp-credentials-box">
          {/* Informations de base */}
          <div className="tcp-info-grid">
            <div className="tcp-info-item">
              <label>Hôte</label>
              <div className="tcp-value">
                <input type="text" readOnly value={credentials.tcp_host} />
                <button 
                  onClick={() => copyToClipboard(credentials.tcp_host, 'Hôte')}
                  className="tcp-copy-btn"
                  title="Copier"
                >
                  📋
                </button>
              </div>
            </div>

            <div className="tcp-info-item">
              <label>Port</label>
              <div className="tcp-value">
                <input type="text" readOnly value={credentials.tcp_port} />
                <button 
                  onClick={() => copyToClipboard(credentials.tcp_port, 'Port')}
                  className="tcp-copy-btn"
                  title="Copier"
                >
                  📋
                </button>
              </div>
            </div>

            <div className="tcp-info-item">
              <label>Utilisateur</label>
              <div className="tcp-value">
                <input type="text" readOnly value={credentials.username} />
                <button 
                  onClick={() => copyToClipboard(credentials.username, 'Utilisateur')}
                  className="tcp-copy-btn"
                  title="Copier"
                >
                  📋
                </button>
              </div>
            </div>

            <div className="tcp-info-item">
              <label>Mot de passe</label>
              <div className="tcp-value">
                <input type="password" readOnly value="••••••••" />
                <span className="tcp-hint">{credentials.info}</span>
              </div>
            </div>
          </div>

          {/* Section pour afficher le mot de passe */}
          {!showPassword ? (
            <div className="tcp-password-section">
              <h3>Afficher le mot de passe</h3>
              <p>Pour voir votre mot de passe et la chaîne de connexion, entrez votre mot de passe actuel:</p>
              <div className="tcp-password-input-group">
                <input 
                  type="password"
                  placeholder="Mot de passe actuel"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleShowPassword()}
                />
                <button 
                  onClick={handleShowPassword}
                  className="tcp-action-btn tcp-primary"
                  disabled={!password || loading}
                >
                  {loading ? 'Vérification...' : 'Afficher'}
                </button>
              </div>
            </div>
          ) : fullCredentials && (
            <div className="tcp-full-credentials">
              <h3>✓ Credentials complètes</h3>
              
              <div className="tcp-info-grid">
                <div className="tcp-info-item tcp-highlight">
                  <label>Mot de passe</label>
                  <div className="tcp-value">
                    <input 
                      type="text" 
                      readOnly 
                      value={fullCredentials.password}
                      className="tcp-password-display"
                    />
                    <button 
                      onClick={() => copyToClipboard(fullCredentials.password, 'Mot de passe')}
                      className="tcp-copy-btn"
                      title="Copier"
                    >
                      📋
                    </button>
                  </div>
                </div>

                <div className="tcp-info-item tcp-highlight">
                  <label>Connection String</label>
                  <div className="tcp-value">
                    <input 
                      type="text" 
                      readOnly 
                      value={fullCredentials.connection_string}
                      className="tcp-connection-string"
                    />
                    <button 
                      onClick={copyConnectionString}
                      className="tcp-copy-btn"
                      title="Copier"
                    >
                      📋
                    </button>
                  </div>
                </div>
              </div>

              <button 
                onClick={() => {
                  setShowPassword(false);
                  setPassword('');
                  setFullCredentials(null);
                }}
                className="tcp-action-btn tcp-secondary"
              >
                Masquer
              </button>
            </div>
          )}

          {/* Code d'exemple */}
          <div className="tcp-examples">
            <h3>📚 Exemples de connexion</h3>
            
            <div className="tcp-example-item">
              <h4>Python</h4>
              <pre>{`import xmlforge

# Connexion au serveur
client = xmlforge.connect(
    host='${credentials.tcp_host}',
    port=${credentials.tcp_port},
    username='${credentials.username}',
    password='YOUR_PASSWORD'
)

# Requête
result = client.execute('SELECT * FROM your_table')
print(result)`}</pre>
            </div>

            <div className="tcp-example-item">
              <h4>Node.js</h4>
              <pre>{`const xmlforge = require('xmlforge');

// Connexion au serveur
const client = xmlforge.connect({
  host: '${credentials.tcp_host}',
  port: ${credentials.tcp_port},
  username: '${credentials.username}',
  password: 'YOUR_PASSWORD'
});

// Requête
client.execute('SELECT * FROM your_table', (err, result) => {
  if (err) console.error(err);
  console.log(result);
});`}</pre>
            </div>

            <div className="tcp-example-item">
              <h4>cURL</h4>
              <pre>{`curl -X POST http://${credentials.tcp_host}:${credentials.tcp_port}/query \\
  -H "Content-Type: application/json" \\
  -d '{
    "username": "${credentials.username}",
    "password": "YOUR_PASSWORD",
    "query": "SELECT * FROM your_table"
  }'`}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TCPCredentials;
