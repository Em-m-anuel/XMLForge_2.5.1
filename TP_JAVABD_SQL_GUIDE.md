# Guide SQL - Base de données TP_JAVABD

Ce document contient les requêtes SQL pour interroger chaque table de la base de données TP_JAVABD via le serveur TCP/IP XMLForge.

## Configuration TCP
- **Host**: 127.0.0.1
- **Port**: 3307
- **Username**: essoya@gmail.com
- **Password**: 12345678

---

## 1. Table: departements
**Colonnes**: id, nom, description, code

```sql
-- Sélectionner tous les départements
SELECT * FROM departements;

-- Sélectionner un département par ID
SELECT * FROM departements WHERE id = 1;

-- Insérer un nouveau département
INSERT INTO departements (nom, description, code) VALUES ('Informatique', 'Département informatique', 'INFO');

-- Mettre à jour un département
UPDATE departements SET description = 'Nouvelle description' WHERE id = 1;

-- Supprimer un département
DELETE FROM departements WHERE id = 1;
```

---

## 2. Table: filieres
**Colonnes**: id, nom, description, code, departement_id

```sql
-- Sélectionner toutes les filières
SELECT * FROM filieres;

-- Sélectionner les filières d'un département
SELECT * FROM filieres WHERE departement_id = 1;

-- Insérer une nouvelle filière
INSERT INTO filieres (nom, description, code, departement_id) VALUES ('Génie Logiciel', 'Filière génie logiciel', 'GL', 1);

-- Mettre à jour une filière
UPDATE filieres SET description = 'Nouvelle description' WHERE id = 1;

-- Supprimer une filière
DELETE FROM filieres WHERE id = 1;
```

---

## 3. Table: classes
**Colonnes**: id, nom, niveau, filiere_id, annee_scolaire

```sql
-- Sélectionner toutes les classes
SELECT * FROM classes;

-- Sélectionner les classes d'une filière
SELECT * FROM classes WHERE filiere_id = 1;

-- Insérer une nouvelle classe
INSERT INTO classes (nom, niveau, filiere_id, annee_scolaire) VALUES ('GL1', 'L1', 1, '2024-2025');

-- Mettre à jour une classe
UPDATE classes SET annee_scolaire = '2025-2026' WHERE id = 1;

-- Supprimer une classe
DELETE FROM classes WHERE id = 1;
```

---

## 4. Table: etudiants
**Colonnes**: id, nom, prenom, email, telephone, mot_de_passe, role, classe_id, departement_id, choix_stage, photo_path

```sql
-- Sélectionner tous les étudiants
SELECT * FROM etudiants;

-- Sélectionner un étudiant par email
SELECT * FROM etudiants WHERE email = 'exemple@email.com';

-- Sélectionner les étudiants d'une classe
SELECT * FROM etudiants WHERE classe_id = 1;

-- Insérer un nouvel étudiant
INSERT INTO etudiants (nom, prenom, email, telephone, mot_de_passe, role, classe_id, departement_id) 
VALUES ('Dupont', 'Jean', 'jean.dupont@email.com', '0123456789', 'password123', 'etudiant', 1, 1);

-- Mettre à jour un étudiant
UPDATE etudiants SET choix_stage = 'Entreprise X' WHERE id = 1;

-- Supprimer un étudiant
DELETE FROM etudiants WHERE id = 1;
```

---

## 5. Table: themes
**Colonnes**: id, titre, description, domaine, difficulte, est_gele, filiere_id, pris_par_etudiant_id

```sql
-- Sélectionner tous les thèmes
SELECT * FROM themes;

-- Sélectionner les thèmes disponibles (non gelés)
SELECT * FROM themes WHERE est_gele = 0;

-- Sélectionner les thèmes par domaine
SELECT * FROM themes WHERE domaine = 'Informatique';

-- Insérer un nouveau thème
INSERT INTO themes (titre, description, domaine, difficulte, est_gele, filiere_id) 
VALUES ('IA pour la santé', 'Application de l''IA dans le domaine médical', 'Informatique', 'Moyen', 0, 1);

-- Mettre à jour un thème
UPDATE themes SET est_gele = 1 WHERE id = 1;

-- Supprimer un thème
DELETE FROM themes WHERE id = 1;
```

---

## 6. Table: sessions_academiques
**Colonnes**: id, libelle, active, date_limite_depot

```sql
-- Sélectionner toutes les sessions
SELECT * FROM sessions_academiques;

-- Sélectionner la session active
SELECT * FROM sessions_academiques WHERE active = 1;

-- Insérer une nouvelle session
INSERT INTO sessions_academiques (libelle, active, date_limite_depot) 
VALUES ('2024-2025', 1, '2025-06-30');

-- Mettre à jour une session
UPDATE sessions_academiques SET active = 0 WHERE id = 1;

-- Supprimer une session
DELETE FROM sessions_academiques WHERE id = 1;
```

---

## 7. Table: depots
**Colonnes**: id, etudiant_id, session_id, sujet_titre, description, nom_entreprise, adresse_entreprise, ville_entreprise, tuteur_entreprise, date_debut, date_fin, statut_validation, justificatif_modification, a_binome, nom_binome, statut_avant_demande, date_depot, type, theme_id

```sql
-- Sélectionner tous les dépôts
SELECT * FROM depots;

-- Sélectionner les dépôts d'un étudiant
SELECT * FROM depots WHERE etudiant_id = 1;

-- Sélectionner les dépôts par session
SELECT * FROM depots WHERE session_id = 1;

-- Insérer un nouveau dépôt
INSERT INTO depots (etudiant_id, session_id, sujet_titre, description, nom_entreprise, date_debut, date_fin, type) 
VALUES (1, 1, 'Stage IA', 'Développement IA', 'TechCorp', '2025-07-01', '2025-09-30', 'stage');

-- Mettre à jour un dépôt
UPDATE depots SET statut_validation = 'validé' WHERE id = 1;

-- Supprimer un dépôt
DELETE FROM depots WHERE id = 1;
```

---

## 8. Table: notifications
**Colonnes**: id, destinataire_utilisateur_id, destinataire_departement_id, type, titre, message, lu, depot_id, traite, demandeur_id, choix_demande, date_creation

```sql
-- Sélectionner toutes les notifications
SELECT * FROM notifications;

-- Sélectionner les notifications non lues d'un utilisateur
SELECT * FROM notifications WHERE destinataire_utilisateur_id = 1 AND lu = 0;

-- Insérer une nouvelle notification
INSERT INTO notifications (destinataire_utilisateur_id, type, titre, message, depot_id) 
VALUES (1, 'validation', 'Dépôt à valider', 'Un nouveau dépôt nécessite votre validation', 1);

-- Marquer une notification comme lue
UPDATE notifications SET lu = 1 WHERE id = 1;

-- Supprimer une notification
DELETE FROM notifications WHERE id = 1;
```

---

## 9. Table: messages_modification
**Colonnes**: id, depot_id, auteur_id, auteur_nom, auteur_role, contenu, date_creation

```sql
-- Sélectionner tous les messages de modification
SELECT * FROM messages_modification;

-- Sélectionner les messages d'un dépôt
SELECT * FROM messages_modification WHERE depot_id = 1;

-- Insérer un nouveau message
INSERT INTO messages_modification (depot_id, auteur_id, auteur_nom, auteur_role, contenu) 
VALUES (1, 1, 'Jean Dupont', 'etudiant', 'Demande de modification du sujet');

-- Supprimer un message
DELETE FROM messages_modification WHERE id = 1;
```

---

## 10. Table: candidats
**Colonnes**: id, nom, prenom, telephone, email, annee_bac, created_at

```sql
-- Sélectionner tous les candidats
SELECT * FROM candidats;

-- Sélectionner un candidat par email
SELECT * FROM candidats WHERE email = 'candidat@email.com';

-- Insérer un nouveau candidat
INSERT INTO candidats (nom, prenom, telephone, email, annee_bac) 
VALUES ('Martin', 'Sophie', '0987654321', 'sophie.martin@email.com', 2023);

-- Mettre à jour un candidat
UPDATE candidats SET telephone = '0123456789' WHERE id = 1;

-- Supprimer un candidat
DELETE FROM candidats WHERE id = 1;
```

---

## 11. Table: candidatures
**Colonnes**: id, candidat_id, filiere_id, date_soumission, statut

```sql
-- Sélectionner toutes les candidatures
SELECT * FROM candidatures;

-- Sélectionner les candidatures d'un candidat
SELECT * FROM candidatures WHERE candidat_id = 1;

-- Sélectionner les candidatures par filière
SELECT * FROM candidatures WHERE filiere_id = 1;

-- Insérer une nouvelle candidature
INSERT INTO candidatures (candidat_id, filiere_id, statut) 
VALUES (1, 1, 'en_attente');

-- Mettre à jour le statut d'une candidature
UPDATE candidatures SET statut = 'accepté' WHERE id = 1;

-- Supprimer une candidature
DELETE FROM candidatures WHERE id = 1;
```

---

## 12. Table: pieces_requises
**Colonnes**: id, ordre, libelle

```sql
-- Sélectionner toutes les pièces requises
SELECT * FROM pieces_requises;

-- Sélectionner les pièces dans l'ordre
SELECT * FROM pieces_requises ORDER BY ordre;

-- Insérer une nouvelle pièce requise
INSERT INTO pieces_requises (ordre, libelle) 
VALUES (1, 'Certificat de naissance');

-- Mettre à jour une pièce requise
UPDATE pieces_requises SET libelle = 'Nouveau libellé' WHERE id = 1;

-- Supprimer une pièce requise
DELETE FROM pieces_requises WHERE id = 1;
```

---

## 13. Table: sessions_concours
**Colonnes**: id, annee_academique, bacs_concernes, lieu, periode_inscription_debut, periode_inscription_fin, horaire_inscription, date_concours, heure_convocation, heure_debut_epreuves, date_affichage_resultats, frais_dossier

```sql
-- Sélectionner toutes les sessions de concours
SELECT * FROM sessions_concours;

-- Sélectionner la session de concours en cours
SELECT * FROM sessions_concours WHERE periode_inscription_debut <= NOW() AND periode_inscription_fin >= NOW();

-- Insérer une nouvelle session de concours
INSERT INTO sessions_concours (annee_academique, bacs_concernes, lieu, date_concours, frais_dossier) 
VALUES ('2024-2025', 'S, ES, L', 'Salle A', '2025-07-15', 50.00);

-- Mettre à jour une session de concours
UPDATE sessions_concours SET lieu = 'Salle B' WHERE id = 1;

-- Supprimer une session de concours
DELETE FROM sessions_concours WHERE id = 1;
```

---

## 14. Table: etapes_demarche
**Colonnes**: id, ordre, titre, description

```sql
-- Sélectionner toutes les étapes de démarche
SELECT * FROM etapes_demarche;

-- Sélectionner les étapes dans l'ordre
SELECT * FROM etapes_demarche ORDER BY ordre;

-- Insérer une nouvelle étape
INSERT INTO etapes_demarche (ordre, titre, description) 
VALUES (1, 'Inscription', 'Remplir le formulaire d''inscription');

-- Mettre à jour une étape
UPDATE etapes_demarche SET description = 'Nouvelle description' WHERE id = 1;

-- Supprimer une étape
DELETE FROM etapes_demarche WHERE id = 1;
```

---

## 15. Table: contacts
**Colonnes**: id, nom_structure, adresse, email, site_web

```sql
-- Sélectionner tous les contacts
SELECT * FROM contacts;

-- Sélectionner un contact par email
SELECT * FROM contacts WHERE email = 'contact@email.com';

-- Insérer un nouveau contact
INSERT INTO contacts (nom_structure, adresse, email, site_web) 
VALUES ('Université X', '123 Rue de l''Université', 'contact@univ-x.fr', 'www.univ-x.fr');

-- Mettre à jour un contact
UPDATE contacts SET adresse = 'Nouvelle adresse' WHERE id = 1;

-- Supprimer un contact
DELETE FROM contacts WHERE id = 1;
```

---

## 16. Table: telephones
**Colonnes**: id, contact_id, numero

```sql
-- Sélectionner tous les téléphones
SELECT * FROM telephones;

-- Sélectionner les téléphones d'un contact
SELECT * FROM telephones WHERE contact_id = 1;

-- Insérer un nouveau téléphone
INSERT INTO telephones (contact_id, numero) 
VALUES (1, '0123456789');

-- Mettre à jour un téléphone
UPDATE telephones SET numero = '0987654321' WHERE id = 1;

-- Supprimer un téléphone
DELETE FROM telephones WHERE id = 1;
```

---

## 17. Table: UTILISATEURS
**Colonnes**: ID, NomUtilisateur, Role, Email

```sql
-- Sélectionner tous les utilisateurs
SELECT * FROM UTILISATEURS;

-- Sélectionner un utilisateur par email
SELECT * FROM UTILISATEURS WHERE Email = 'user@email.com';

-- Sélectionner les utilisateurs par rôle
SELECT * FROM UTILISATEURS WHERE Role = 'admin';

-- Insérer un nouvel utilisateur
INSERT INTO UTILISATEURS (NomUtilisateur, Role, Email) 
VALUES ('Jean Dupont', 'admin', 'jean.dupont@email.com');

-- Mettre à jour un utilisateur
UPDATE UTILISATEURS SET Role = 'superadmin' WHERE ID = 1;

-- Supprimer un utilisateur
DELETE FROM UTILISATEURS WHERE ID = 1;
```

---

## 18. Table: FILIERES
**Colonnes**: ID, NomFiliere, Description, Duree, Debouches

```sql
-- Sélectionner toutes les filières
SELECT * FROM FILIERES;

-- Sélectionner une filière par nom
SELECT * FROM FILIERES WHERE NomFiliere = 'Informatique';

-- Insérer une nouvelle filière
INSERT INTO FILIERES (NomFiliere, Description, Duree, Debouches) 
VALUES ('Informatique', 'Formation en informatique', '3 ans', 'Développeur, Data Scientist');

-- Mettre à jour une filière
UPDATE FILIERES SET Description = 'Nouvelle description' WHERE ID = 1;

-- Supprimer une filière
DELETE FROM FILIERES WHERE ID = 1;
```

---

## 19. Table: MODULES_PEDAGOGIQUES
**Colonnes**: ID, NomModule, Filiere, Niveau, CeQueLonEtudie, AQuoiCaSert

```sql
-- Sélectionner tous les modules pédagogiques
SELECT * FROM MODULES_PEDAGOGIQUES;

-- Sélectionner les modules d'une filière
SELECT * FROM MODULES_PEDAGOGIQUES WHERE Filiere = 'Informatique';

-- Sélectionner les modules par niveau
SELECT * FROM MODULES_PEDAGOGIQUES WHERE Niveau = 'L1';

-- Insérer un nouveau module
INSERT INTO MODULES_PEDAGOGIQUES (NomModule, Filiere, Niveau, CeQueLonEtudie, AQuoiCaSert) 
VALUES ('Algorithmique', 'Informatique', 'L1', 'Algorithmes de base', 'Fondation pour la programmation');

-- Mettre à jour un module
UPDATE MODULES_PEDAGOGIQUES SET CeQueLonEtudie = 'Nouveau contenu' WHERE ID = 1;

-- Supprimer un module
DELETE FROM MODULES_PEDAGOGIQUES WHERE ID = 1;
```

---

## 20. Table: MAQUETTES_LMD
**Colonnes**: ID, UE_Nom, Credit, Vol_CM, Vol_TD, Vol_TP, Semestre

```sql
-- Sélectionner toutes les maquettes LMD
SELECT * FROM MAQUETTES_LMD;

-- Sélectionner les UE d'un semestre
SELECT * FROM MAQUETTES_LMD WHERE Semestre = 'S1';

-- Sélectionner les UE par nombre de crédits
SELECT * FROM MAQUETTES_LMD WHERE Credit >= 3;

-- Insérer une nouvelle UE
INSERT INTO MAQUETTES_LMD (UE_Nom, Credit, Vol_CM, Vol_TD, Vol_TP, Semestre) 
VALUES ('Mathématiques', 3, 24, 12, 0, 'S1');

-- Mettre à jour une UE
UPDATE MAQUETTES_LMD SET Credit = 4 WHERE ID = 1;

-- Supprimer une UE
DELETE FROM MAQUETTES_LMD WHERE ID = 1;
```

---

## 21. Table: partenaires
**Colonnes**: id, nom, type, statut, date_signature, description

```sql
-- Sélectionner tous les partenaires
SELECT * FROM partenaires;

-- Sélectionner les partenaires par type
SELECT * FROM partenaires WHERE type = 'entreprise';

-- Sélectionner les partenaires actifs
SELECT * FROM partenaires WHERE statut = 'actif';

-- Insérer un nouveau partenaire
INSERT INTO partenaires (nom, type, statut, date_signature, description) 
VALUES ('TechCorp', 'entreprise', 'actif', '2025-01-15', 'Partenariat pour les stages');

-- Mettre à jour un partenaire
UPDATE partenaires SET statut = 'inactif' WHERE id = 1;

-- Supprimer un partenaire
DELETE FROM partenaires WHERE id = 1;
```

---

## Requêtes avancées

### Jointures courantes

```sql
-- Étudiants avec leur classe et filière
SELECT e.*, c.nom as classe_nom, f.nom as filiere_nom 
FROM etudiants e
LEFT JOIN classes c ON e.classe_id = c.id
LEFT JOIN filieres f ON c.filiere_id = f.id;

-- Dépôts avec informations étudiant et thème
SELECT d.*, e.nom as etudiant_nom, e.prenom as etudiant_prenom, t.titre as theme_titre
FROM depots d
LEFT JOIN etudiants e ON d.etudiant_id = e.id
LEFT JOIN themes t ON d.theme_id = t.id;

-- Thèmes avec filière
SELECT t.*, f.nom as filiere_nom
FROM themes t
LEFT JOIN filieres f ON t.filiere_id = f.id;
```

### Agrégations

```sql
-- Nombre d'étudiants par classe
SELECT classe_id, COUNT(*) as nb_etudiants
FROM etudiants
GROUP BY classe_id;

-- Nombre de dépôts par session
SELECT session_id, COUNT(*) as nb_depots
FROM depots
GROUP BY session_id;

-- Thèmes les plus populaires
SELECT theme_id, COUNT(*) as nb_choix
FROM depots
WHERE theme_id IS NOT NULL
GROUP BY theme_id
ORDER BY nb_choix DESC;
```

---

## Notes importantes

1. **Connexion TCP**: Assurez-vous que le serveur TCP est démarré sur le port 3307
2. **Authentification**: Utilisez vos identifiants XMLForge pour la connexion TCP
3. **Base de données**: La base de données `TP_JAVABD` doit être spécifiée lors de la connexion
4. **Types de données**: Respectez les types de données définis dans chaque colonne
5. **Contraintes**: Certaines tables ont des clés étrangères, assurez-vous de l'intégrité référentielle
