# XMLForge — Refactorisation React

Refactorisation du fichier HTML monolithique `deepseek_html_20260717_a821a4.html` (1363 lignes, CSS + JS inline) vers une application React propre, maintenable, sans changer l'identité visuelle.

## Objectif atteint
Le résultat donne l'impression que le projet a été conçu dès le départ avec React.

## Stack utilisée (uniquement autorisé)
- React 19
- React Router 6
- CSS classique (pas de Bootstrap/Tailwind/etc)
- Vite

## Architecture finale

```
src/
├── assets/
├── components/
│   ├── Badge/ (Badge.jsx + Badge.css)
│   ├── Button/ (réutilisable, variants primary/danger/ghost/sm/full)
│   ├── Card/
│   ├── CodePane/ (XML + SQL panes workspace)
│   ├── ContextMenu/
│   ├── IconButton/
│   ├── Input/ (Input + FormInput harmonisés)
│   ├── Loader/
│   ├── Modal/
│   ├── Navbar/ (Topbar dashboard)
│   ├── Sidebar/ (navigation dashboard)
│   └── Toast/ (ToastProvider + useToast)
├── pages/
│   ├── Login/ (Login.jsx + Login.css + AuthBackground partagé)
│   ├── Register/ (réutilise Login.css)
│   ├── Dashboard/ (sidebar + navbar + db-grid)
│   └── Workspace/ (titlebar + sidebar tables + main + right code panes)
├── styles/
│   ├── tokens.css (unique source design tokens)
│   └── global.css (reset + scrollbar)
├── hooks/
│   └── useDatabases.js (mock data centralisé)
├── utils/
│   ├── icons.jsx (bibliothèque SVG unique)
│   └── mockData.js
├── App.jsx (Router + ToastProvider)
└── main.jsx (BrowserRouter + styles)
```

## Harmonisation design — corrections appliquées

**Analyse d'incohérences initiales :**
- Login et Register avaient des fonds légèrement différents (drift texts différents, cercles différents)
- Cards login (400px + backdrop-filter) vs db-card (240px min + shadow-card) utilisaient mêmes couleurs mais CSS dupliqué
- Inputs : .field-input (login) vs .form-input (modals) avaient des paddings/transitions différentes
- Hover : btn translateY(-1px) vs db-card translateY(-3px) pas homogène mais intentionnel — conservé mais durée/ease unifiés
- Ombres : --shadow-card vs --shadow-pop utilisées aléatoirement

**Corrections :**
1. **Fond Login/Register identique** : Extraction `AuthBackground` component réutilisé dans les deux pages. Même radial-gradient `rgba(59,130,246,.16)` + `rgba(34,197,94,.08)`, mêmes cercles, mêmes animations `drift 14s` / `drift2 18s reverse`. Largeur card conservée 400px login, 440px register (justifié par 4 champs) mais même style, même backdrop-filter, même `cardIn` animation.

2. **Couleurs uniformes** : Toutes dans `tokens.css`. --bg #0F1117, --card #1C212B, --border #262C38, --accent #3B82F6, etc. Suppression des couleurs en dur dans le HTML original.

3. **Boutons identiques** : Composant `<Button variant="primary|danger|ghost" size="sm" />` centralise `.btn` original. Même padding 9x16, radius sm 6px, transition 180ms cubic-bezier(.4,0,.2,1), hover translateY(-1px), primary shadow inset.

4. **Champs formulaire identiques** : `<Input>` et `<FormInput>` partagent même background #12151C, border var(--border), focus border var(--accent) + box-shadow 0 0 0 3px var(--accent-dim), placeholder var(--text-tertiary). Label 12.5px 600 secondary.

5. **Cartes** : `<Card>` base utilise --card, --border, --radius 10px, --shadow-card, même transition transform/border/background. `.db-card` hérite de .card avec animation fadeUp 0.45s. Même hover : translateY(-3px) + border #333b4a + background --card-hover.

6. **Typographie** : Inter pour UI, JetBrains Mono pour code/monospace. Hiérarchie : h1 22px 700 dashboard, 20px 700 auth, 16px 700 workspace title, 15px 600 db-card, 13px base, 12px meta, 11px uppercase sidebar-head.

7. **Espacements** : Système 4/6/8/10/12/14/16/18/22/28/32px harmonisé. Cards padding 18px (vs 18px original ok), login-card 40x36, modal head 18x22, etc.

8. **Rayons** : --radius-sm 6px (boutons, inputs, icon-btn), --radius 10px (cards, db-cards), --radius-lg 16px (login-card, modals) — même partout.

9. **Ombres** : --shadow-card pour cards, --shadow-pop pour modals/toasts/context-menu — uniformisé.

10. **Animations** : --duration-fast 150ms (icon-btn, context-menu), --duration-base 180ms (boutons, cards), --duration-slow 300ms (modal), même --ease cubic-bezier(.4,0,.2,1). ToastIn 0.35s, cardIn 0.6s, fadeUp 0.45s, drift 14s/18s conservés.

11. **Icônes** : Centralisées dans `utils/icons.jsx`, même stroke-width 2 (2.2 pour logo), même taille 15px boutons, 16px inputs/sidebar, 19px db-card icon.

## CSS nettoyé

- Original : 1 fichier 73KB, 1363 lignes, règles dupliquées (ex: .field-input et .form-input, .btn et .icon-btn)
- Refactor : 23.23KB total CSS gzip 4.98KB, split par composant, tokens centralisés, suppression des règles inutilisées (ex: .hidden redondant, doubles .grid-2), groupement styles communs dans global.css
- Noms de classes explicites BEM-like : `ws-sidebar`, `ws-table-item`, `db-card-top`, `auth-badge-row`
- Pas de couleurs en dur hors tokens

## React — transformation

- Chaque ancienne screen div (`#screen-login`, `#screen-dashboard`, `#screen-workspace`) → composant page avec Router
- Interactions vanilla JS (`showScreen()`, `openModal()`, `notify()`, `toggleCtx()`, `selectTable()`) → state React `useState`, `useEffect`, hooks custom `useToast`, `useDatabases`
- Duplications supprimées : DatabaseCard, TableRow, Badge, Button, Input réutilisés
- Modals : composant `<Modal open={} onClose={}>` avec overlay click + Escape handling (anciennement closeModal('id'))
- Context menus : composant `<ContextMenu>` avec ref + outside click (vs toggleCtx global)
- CodePanes : composants réutilisables

## Responsive — conservé et amélioré

- Sidebar dashboard collapse 224px → 72px @900px (icônes seules)
- Workspace right panel caché @900px (comme original)
- Topbar search 340px → 200px @640px
- Grids auto-fill minmax(240px) conservés, gap 16px harmonisé
- Modals max-width 92vw + max-height 86vh

## Lancer

```bash
cd xmlforge-react
npm install
npm run dev # http://localhost:5173
npm run build
```

Routes :
- /login
- /register
- /dashboard
- /workspace/:dbName (ex: /workspace/Bibliothèque)

## Vérifications qualité

- [x] Aucune incohérence visuelle entre pages
- [x] Même fond Login/Register (AuthBackground partagé)
- [x] Mêmes boutons (Button.jsx)
- [x] Mêmes champs (Input.jsx)
- [x] Même style cartes (Card + tokens)
- [x] Espacement / typo / couleurs uniformes via tokens.css
- [x] CSS factorisé sans duplications
- [x] Composants réutilisables
- [x] Architecture claire src/
- [x] Pas de librairie UI externe
- [x] Identité visuelle conservée (dark #0F1117, accent #3B82F6, blur, drifts)
