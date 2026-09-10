# RcloneGUI

Interface web (Flask) pour planifier, exécuter et superviser des sauvegardes **Rclone** vers **Dropbox** ou vers un **dossier local**.

L'application expose une API REST + une interface web permettant de définir des sauvegardes
(source → destination), de les lancer manuellement ou automatiquement (planificateur intégré),
et de suivre leur progression en temps réel.

## Interface
<img width="1427" height="806" alt="image" src="https://github.com/user-attachments/assets/d0e5d35a-acb5-49ec-b54e-c35170ddc589" />

## Fonctionnalités

- Sauvegardes : dossier local / réseau (ex. `D:\Docs`, `\\SERVEUR\Partage`) → Dropbox ou dossier local
- Motifs d'exclusion par sauvegarde (`*.log`, `thumbs.db`, `Desktop.ini`, …)
- Planification `on/off`, mode « nuit uniquement » (20h → 6h), exécution manuelle, annulation
- Sauvegardes bidirectionnelles (bisync) ou unidirectionnelles (sync/copy)
- Progression en temps réel (SSE), logs en base, export / import JSON des configurations
- Authentification par JWT (mot de passe hashé avec Werkzeug)

## Prérequis

- **Windows** avec **Python 3.10+** (testé en 3.14)
- **Rclone** — binaire **non inclus** dans ce dépôt :
  1. Télécharger : https://rclone.org/downloads/ (prendre `rclone.exe` Windows 64 bits)
  2. Créer le dossier `Rclone/` à la racine du projet et y placer `rclone.exe`
     (ou définir un autre chemin via `RCLONE_EXE_PATH`, voir ci-dessous)

## Mise en route (pas à pas)

### 1. Cloner et installer les dépendances

```powershell
git clone https://github.com/BobFredGard/RcloneGUI.git
cd RcloneGUI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configurer l'environnement

```powershell
copy .env.example .env
```

Éditer `.env` et mettre au minimum une vraie clé secrète :

```
SECRET_KEY=une-chaine-longue-et-aleatoire-a-generer
```

Variables reconnues (toutes optionnelles sauf `SECRET_KEY` en production) :

| Variable | Défaut | Rôle |
|---|---|---|
| `SECRET_KEY` | `dev-secret-...` | Clé de signature JWT / sessions Flask — **à changer obligatoirement** |
| `DATABASE_URL` | `sqlite:///backups.db` | Base SQLite (fichier créé dans `instance/`) |
| `RCLONE_CONFIG_PATH` | `./rclone.conf` | Fichier de config Rclone (**jamais commité**) |
| `RCLONE_EXE_PATH` | `./Rclone/rclone.exe` | Chemin du binaire Rclone |
| `JWT_EXPIRATION_HOURS` | `24` | Durée de validité des sessions |

### 3. Configurer Rclone (remote Dropbox)

Le code attend un remote nommé exactement **`dropbox`** (les destinations sont construites
sous la forme `dropbox:chemin`). Créer le fichier puis configurer :

```powershell
copy rclone.conf.example rclone.conf
.\Rclone\rclone.exe config --config rclone.conf
```

Dans l'assistant interactif : `n` (nouveau remote) → nom `dropbox` → type `dropbox` →
suivre l'authentification OAuth dans le navigateur. Vérifier ensuite :

```powershell
.\Rclone\rclone.exe listremotes --config rclone.conf
# doit afficher : dropbox:
.\Rclone\rclone.exe ls dropbox: --max-depth 1 --config rclone.conf
```

> ⚠️ `rclone.conf` contient vos tokens : **ne jamais le commiter** (il est dans `.gitignore`).
> En cas de fuite, révoquer l'accès côté Dropbox (Paramètres → Applications connectées),
> puis refaire `config reconnect`.

### 4. Lancer l'application

```powershell
python app.py
# ou (serveur WSGI waitress) :
python launcher.py
```

Ouvrir http://localhost:5000 — l'application écoute sur `0.0.0.0:5000`.

### 5. Créer le premier utilisateur

Il n'y a pas de compte par défaut. Créer le compte admin via l'API :

```powershell
Invoke-RestMethod -Uri http://localhost:5000/api/auth/register -Method Post `
  -ContentType 'application/json' `
  -Body '{"username":"admin","password":"VOTRE_MOT_DE_PASSE"}'
```

Puis se connecter via l'interface web (le login `POST /api/auth/login` renvoie un token JWT
utilisé ensuite en en-tête `Authorization: Bearer <token>`).

> 🔒 Recommandation : l'endpoint `/api/auth/register` est ouvert. Après création du
> premier compte, restreignez-le ou désactivez-le si l'appli est exposée au réseau.

### 6. Créer une sauvegarde

Dans l'interface : **Nouvelle sauvegarde** → renseigner :
- **Nom** (unique), **source** (ex. `\\SERVEUR\Docs` ou `D:\Photos`)
- **Destination** : type `dropbox` (chemin ex. `/Sauvegardes/Docs`) ou `local` (dossier)
- **Exclusions** (défaut : `Desktop.ini`, `thumbs.db`, `.DS_Store`, `*.log`…)
- **Planification** : `off` (manuel) ou `on` (planificateur) + option nuit / bidirectionnel

Lancer avec **Exécuter**, suivre la progression, consulter les **logs**.

### 7. (Optionnel) Démarrage automatique Windows

```powershell
.\create_task.ps1        # tâche planifiée au démarrage (utilisateur courant)
.\auto_start_system.ps1  # tâche SYSTEM au boot (droits élevés)
# ou
.\service_install.bat    # via schtasks (voir service_uninstall.bat pour retirer)
```

Les scripts détectent `python` dans le `PATH` et utilisent le dossier du projet :
aucun chemin en dur à modifier.

### 8. (Optionnel) Migrer une base existante

Si vous réutilisez un `backups.db` ancien (sans les colonnes `destination_type` /
`destination_path`) :

```powershell
python migrate_db.py
```

## Utilisation au quotidien

- **Exécuter** : lance une sauvegarde immédiatement (max 3 simultanées)
- **Annuler** : tue le processus Rclone et marque la sauvegarde `cancelled`
- **Export / Import** : `GET /api/backups/export`, `POST /api/backups/import` (JSON)
- **Parcourir** : `POST /api/backups/browse` liste les lecteurs / dossiers (Windows)
- **Connexions** : `GET /api/backups/connections` vérifie les remotes Rclone
- **Logs** : `GET /api/logs`, `POST /api/logs/clear`

## Structure du projet

```
app.py               # fabrique Flask + enregistrement des blueprints
config.py            # Config (env + défauts relatifs au projet)
models.py            # User, Backup, BackupLog (SQLAlchemy / SQLite)
rclone_service.py    # wrapper subprocess autour de rclone.exe
scheduler.py         # planificateur (file circulaire, thread fond)
logs_service.py      # helpers de logs en base
auth/                # login / register / JWT
backups/             # CRUD sauvegardes, run/cancel, SSE, export/import
logs/                # lecture / purge des logs
templates/index.html # interface web
static/              # css/js (app_v12.js)
```

## Dépannage

| Symptôme | Piste |
|---|---|
| `rclone.exe introuvable` | Vérifier `Rclone/rclone.exe` ou `RCLONE_EXE_PATH` |
| `remote dropbox introuvable` | Le remote doit s'appeler `dropbox` (`listremotes` pour vérifier) |
| Page inaccessible | Port 5000 occupé ? pare-feu ? `python app.py` affiche les erreurs |
| 401 sur l'API | Token expiré (`JWT_EXPIRATION_HOURS`) → se reconnecter |
| Sauvegarde `failed` | Voir `GET /api/logs` + `scheduler.log` + sortie verbose Rclone |
| Base vide après màj | Lancer `python migrate_db.py` |

## Sécurité — à lire avant d'exposer l'appli

- Ne jamais commiter : `rclone.conf`, `.env`, `instance/*.db`, `*.log` (couverts par `.gitignore`)
- Changer `SECRET_KEY` en production (sinon sessions falsifiables)
- Protéger `/api/auth/register` après création du 1er compte
- La 2FA TOTP (`pyotp`) est une dépendance prévue mais **non enforced** côté login actuellement
- Le endpoint SSE `/api/backups/<id>/stream` n'exige pas de JWT : ne pas exposer tel quel sur Internet

## Licence

MIT — voir `LICENSE`.
