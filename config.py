import os

base_dir = os.path.dirname(os.path.abspath(__file__))
rclone_dir = os.path.join(base_dir, 'Rclone')

DEFAULT_EXCLUSIONS = ["Desktop.ini", "thumbs.db", "desktop.ini", ".DS_Store", "*.log", "*.log.*"]

def _load_secret_key():
    # 1. Variable d'environnement (prioritaire, ex: tâche planifiée SYSTEM)
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key, False
    # 2. Fichier local secret.key (généré une fois, survit aux reboots,
    #    visible par SYSTEM comme par l'utilisateur interactif)
    key_file = os.path.join(base_dir, 'secret.key')
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r') as f:
                file_key = f.read().strip()
            if len(file_key) >= 32:
                return file_key, False
    except Exception:
        pass
    # 3. Repli dev (intranet uniquement, warning au démarrage)
    return 'dev-secret-key-change-in-production', True

_SECRET, _IS_DEV = _load_secret_key()

class Config:
    SECRET_KEY = _SECRET
    # True si la clé par défaut (dev) est utilisée -> log un warning au démarrage (voir app.py)
    USING_DEV_SECRET = _IS_DEV
    SQLALCHEMY_DATABASE_URI = 'sqlite:///backups.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_EXPIRATION_HOURS = 24
    RCLONE_CONFIG_PATH = os.path.join(base_dir, 'rclone.conf')
    RCLONE_EXE_PATH = os.path.join(rclone_dir, 'rclone.exe')
    # Intranet : inscriptions ouvertes uniquement pour le 1er compte,
    # sauf si ALLOW_REGISTRATION=true dans l'environnement.
    ALLOW_REGISTRATION = os.environ.get('ALLOW_REGISTRATION', 'false').lower() == 'true'
    # Intranet : racines navigables via /api/backups/browse, séparées par ';'.
    # Ex: BROWSE_ALLOWED_ROOTS=D:\ServerFolders;\\NAS\partage
    # Vide = pas de restriction (comportement historique, à resserrer).
    BROWSE_ALLOWED_ROOTS = [
        r.strip() for r in os.environ.get('BROWSE_ALLOWED_ROOTS', '').split(';') if r.strip()
    ]
