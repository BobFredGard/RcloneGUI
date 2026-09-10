# RcloneGUI

Interface web Flask pour planifier et superviser des sauvegardes Rclone (Dropbox / local).

## Fonctionnalités

- Création de sauvegardes : source locale/réseau → Dropbox ou dossier local
- Exclusions par motifs (`*.log`, `thumbs.db`, …)
- Planification on/off + mode nuit, exécution manuelle, annulation
- Logs en base SQLite, progression en temps réel (SSE), export/import JSON des configs
- Auth par JWT (mot de passe hashé werkzeug)

## Prérequis

- Python 3.10+ (Windows)
- Rclone (binaire **non inclus** dans le repo) : https://rclone.org/downloads/
  - Placer `rclone.exe` dans `Rclone/` ou définir `RCLONE_EXE_PATH`

## Installation

```powershell
git clone https://github.com/BobFredGard/RcloneGUI.git
cd RcloneGUI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# éditer .env : mettre une vraie SECRET_KEY
copy rclone.conf.example rclone.conf
rclone config --config rclone.conf   # configurer le remote "dropbox"

python app.py
# http://localhost:5000
```

Créer le premier utilisateur via `POST /api/auth/register` :
```powershell
Invoke-RestMethod -Uri http://localhost:5000/api/auth/register -Method Post `
  -ContentType 'application/json' -Body '{"username":"admin","password":"..."}'
```

## Configuration (.env)

| Variable | Défaut | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-...` | Clé JWT/sessions — **obligatoire en prod** |
| `DATABASE_URL` | `sqlite:///backups.db` | SQLite (créé dans `instance/`) |
| `RCLONE_CONFIG_PATH` | `./rclone.conf` | Fichier rclone (jamais commité) |
| `RCLONE_EXE_PATH` | `./Rclone/rclone.exe` | Binaire rclone |
| `JWT_EXPIRATION_HOURS` | `24` | Durée session |

## Démarrage auto Windows

```powershell
.\create_task.ps1        # tâche au démarrage (utilisateur courant)
# ou
.\auto_start_system.ps1  # tâche SYSTEM au boot
```

## Structure

```
app.py  config.py  models.py  rclone_service.py  scheduler.py  logs_service.py
auth/  backups/  logs/  templates/  static/
```

## Sécurité

- Ne jamais commiter : `rclone.conf`, `.env`, `instance/*.db`, `*.log` (déjà dans `.gitignore`)
- Si un token a fuité : révoquer l'accès Dropbox, régénérer `SECRET_KEY`, supprimer le commit
- `SPEC.md` est une spec d'origine, peut différer du code

## Licence

MIT — voir `LICENSE`.
