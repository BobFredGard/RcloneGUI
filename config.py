import os

base_dir = os.path.dirname(os.path.abspath(__file__))
rclone_dir = os.path.join(base_dir, 'Rclone')

DEFAULT_EXCLUSIONS = ["Desktop.ini", "thumbs.db", "desktop.ini", ".DS_Store", "*.log", "*.log.*"]

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///backups.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS') or 24)
    RCLONE_CONFIG_PATH = os.environ.get('RCLONE_CONFIG_PATH') or os.path.join(base_dir, 'rclone.conf')
    RCLONE_EXE_PATH = os.environ.get('RCLONE_EXE_PATH') or os.path.join(rclone_dir, 'rclone.exe')
