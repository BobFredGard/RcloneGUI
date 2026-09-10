# Rclone Backup Manager - Spécification

## 1. Projet Overview

**Nom du projet:** Rclone Backup Manager
**Type:** Application HTML + Python (Flask) + JavaScript
**Fonction:** Gestion de sauvegardes réseau vers Dropbox avec authentification Authy 2FA
**Direction:** Uniquement depuis répertoires réseau vers Dropbox (sens unique)

## 2. Stack Technique

- **Backend:** Flask (Python)
- **Frontend:** HTML5 + JavaScript (Vanilla)
- **Base de données:** SQLite
- **Gestionnaire de fichiers:** Rclone
- **Authentification:** Authy 2FA (6 chiffres)
- **Exécution:** CLI (ligne de commande)

## 3. Fonctionnalités

### 3.1 Authentification
- Connexion par mot de passe + code Authy 6 chiffres
- Session gérée par token JWT

### 3.2 Gestion des Connexions
- Connexion à Dropbox via Rclone (authentification OAuth)
- Support futur: répertoires réseau Windows (UNC paths)

### 3.3 Gestion des Sauvegardes
- Créer un nombre illimité de sauvegardes
- Chaque sauvegarde définie par:
  - Nom (unique)
  - Répertoire source (réseau)
  - Destination Dropbox fixe
  - Configuration d'exclusions (fichiers/types)
  - Fréquence de planification

### 3.4 Planification
- Options de fréquence:
  - Toutes les 15 minutes
  - Toutes les 1 heure
  - Toutes les 6 heures
  - Toutes les 12 heures
  - Toutes les 24 heures
- Exécution via thread en arrière-plan

### 3.5 Exclusions par Sauvegarde
- Exclure des fichiers/dossiers spécifiques (patterns)
- Exclure par extension (*.log, *.tmp, etc.)

## 4. Architecture

```
/rclone-backup-manager
├── app.py                 # Point d'entrée Flask
├── config.py              # Configuration
├── models.py              # Modèles SQLAlchemy
├── rclone_service.py      # Wrapper Rclone
├── scheduler.py           # Planificateur
├── auth/
│   ├── routes.py          # Routes auth
│   └── utils.py           # Utils auth
├── backups/
│   ├── routes.py          # Routes backups
│   └── service.py         # Logique备份
├── static/
│   ├── css/
│   └── js/
└── templates/
    └── index.html         # Interface principale
```

## 5. API Endpoints

### Auth
- `POST /api/auth/login` - Connexion (password + code Authy)
- `POST /api/auth/logout` - Déconnexion
- `GET /api/auth/check` - Vérifier session

### Connexions
- `GET /api/connections` - Liste des connexions Rclone
- `POST /api/connections/authorize` - Authoriser Dropbox

### Sauvegardes
- `GET /api/backups` - Liste des sauvegardes
- `POST /api/backups` - Créer sauvegarde
- `PUT /api/backups/:id` - Modifier sauvegarde
- `DELETE /api/backups/:id` - Supprimer sauvegarde
- `POST /api/backups/:id/run` - Exécuter sauvegarde manuelle
- `GET /api/backups/:id/logs` - Voir logs

## 6. Modèle de Données

### User
- id, username, password_hash, authy_secret

### Backup
- id, name, source_path, dropbox_path, exclusions (JSON)
- schedule_type (15min/1h/6h/12h/24h/none), is_active
- created_at, updated_at, last_run, last_status

## 7. Sécurité
- Mots de passe hashés (werkzeug)
- Sessions JWT avec expiration
- Validation des chemins (pas d'accès arbitraire)
