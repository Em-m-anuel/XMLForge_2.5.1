# XMLForge React

Interface du template XMLForge connectée au backend Flask réel.

## Lancement

```bash
npm install
cp .env.example .env
npm run dev
```

Le backend doit écouter sur 5000. Vite proxifie `/api` et `/socket.io`.

## Validation

```bash
npm run lint
npm run build
npm test
npm run test:e2e   # backend + Vite déjà lancés
```

Test live contre Flask :

```bash
VITE_API_URL=http://127.0.0.1:5000/api XMLFORGE_LIVE_E2E=1 \
npm test -- src/test/liveBackend.test.js
```

Documentation complète : `FRONTEND_DOCUMENTATION.md`.
