from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

def utcnow():
    return datetime.now(timezone.utc)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    authy_secret = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    source_path = db.Column(db.String(500), nullable=False)
    dropbox_path = db.Column(db.String(500), nullable=False)
    destination_type = db.Column(db.String(20), default='dropbox')
    destination_path = db.Column(db.String(500), default='')
    exclusions = db.Column(db.Text, default='["Desktop.ini", "thumbs.db", "desktop.ini", ".DS_Store"]')
    schedule_type = db.Column(db.String(20), default='off')
    night_only = db.Column(db.Boolean, default=False)
    night_done = db.Column(db.Boolean, default=False)
    bidirectional = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    last_run = db.Column(db.DateTime, nullable=True)
    last_status = db.Column(db.String(20), nullable=True)
    next_run = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    pid = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source_path': self.source_path,
            'dropbox_path': self.dropbox_path,
            'destination_type': self.destination_type,
            'destination_path': self.destination_path,
            'exclusions': self.exclusions,
            'schedule_type': self.schedule_type,
            'night_only': self.night_only,
            'night_done': self.night_done,
            'is_active': self.is_active,
            'bidirectional': self.bidirectional,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'last_run': self.last_run.isoformat() + 'Z' if self.last_run else None,
            'last_status': self.last_status,
            'next_run': self.next_run.isoformat() + 'Z' if self.next_run else None,
            'started_at': self.started_at.isoformat() + 'Z' if self.started_at else None,
            'pid': self.pid
        }

class BackupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    backup_id = db.Column(db.Integer, db.ForeignKey('backup.id'), nullable=False)
    backup_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    error_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'backup_id': self.backup_id,
            'backup_name': self.backup_name,
            'message': self.message,
            'error_details': self.error_details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
