# Adaptation finale au modèle `xmlforge (4).html`

## 1. Pages adaptées au modèle

- Login et Register : cartes, arrière-plan SVG, champs, erreurs inline, badges.
- Dashboard : topbar, titre, actions, tabs Toutes/Personnelles/Communes, grille et cartes du modèle.
- History : header, filtres et timeline du modèle.
- Audit : header, filtre et table du modèle.
- Users : titre, info-box, table et modals du modèle.
- API & TCP/IP : screen API, sections TCP, Clés API et endpoints du modèle.
- Workspace : titlebar, explorateur, actions, tabs Structure/Données/Relations, panneaux XML/SQL et modals.

## 2. Composants adaptés

- Sidebar : ordre, libellés, icônes et visibilité du modèle.
- TCPCredentials : replacé dans l’`api-card` sombre du modèle.
- MonacoEditor : conservé dans les code panes du modèle.
- Toast : composant du modèle conservé.
- ConflictDialog : modal utilisant strictement les classes visuelles du modèle.
- Modals bases/tables/colonnes/users/import/export/protection : structures du modèle.

## 3. Logique backend conservée

Tous les services existants restent utilisés : API centralisée, auth/JWT, bases, accès, tables, colonnes, rows, sync XML, converters, import/export/projet, users, audit, history, unlocks et TCP REST. `expected_version`, 401/403/404/409, rôles et permissions restent inchangés.

## 4. Éléments du modèle intégrés

- CSS inline du modèle copié à l’identique dans `maquette.css`.
- Sidebar/nav exacte.
- Dashboard et scope tabs.
- DB cards et menus contextuels.
- Workspace à trois colonnes.
- Tabs Structure/Données/Relations.
- Code panes, fullscreen, actions XML/SQL.
- API card, table API keys et endpoint list.
- Tables Audit/Users.
- Timeline History.
- Tous les modals et responsive du modèle.

## 5. Éléments impossibles à intégrer tels quels

- Astuce « email admin » : fausse avec le backend actuel, donc omise.
- Rôles VIEWER/EDITOR : backend limité à USER/ADMIN ; les valeurs réelles sont affichées.
- Génération de clés API : aucun endpoint backend ; section conservée visuellement mais désactivée et explicitée.
- Export global de toutes les bases : backend exporte un projet par base ; le modal du modèle demande donc une base.
- Placeholder « aucune base MySQL » : remplacé par les rows réelles XML/SQLite, car le backend les fournit désormais.
- History pour USER : backend réserve History à ADMIN ; la sidebar respecte cette autorité.

## 6. Tests

- CSS du modèle comparé byte-à-byte : correspondance exacte.
- `npm run build` : succès.
- `npm run lint` : 0 erreur, 3 warnings Fast Refresh historiques.
- `npm test` : 10 tests réussis, live test désactivé par défaut.
- test services ↔ Flask réel : réussi.
- Playwright Chromium : register/login, dashboard modèle, COMMON, workspace, table/row, conflit 409, API/TCP — réussi.
- backend : tests réussis ; aucune logique backend déplacée dans le frontend.
