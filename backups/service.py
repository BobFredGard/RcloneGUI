import json

def create_backup(name, source_path, dropbox_path, exclusions, schedule_type, bidirectional=False, night_only=False, destination_type='dropbox', destination_path=''):
    from models import Backup, db
    from datetime import datetime, timezone

    backup = Backup(
        name=name,
        source_path=source_path,
        dropbox_path=dropbox_path,
        destination_type=destination_type,
        destination_path=destination_path or dropbox_path,
        exclusions=json.dumps(exclusions),
        schedule_type=schedule_type,
        bidirectional=bidirectional,
        night_only=night_only
    )

    if schedule_type == 'on':
        backup.next_run = datetime.now(timezone.utc)

    db.session.add(backup)
    db.session.commit()
    return backup

def get_all_backups():
    from models import Backup
    return Backup.query.all()

def get_backup(backup_id):
    from models import Backup
    return Backup.query.get(backup_id)

def update_backup(backup_id, data):
    from models import Backup, db
    backup = Backup.query.get(backup_id)
    if not backup:
        return None

    if 'name' in data:
        backup.name = data['name']
    if 'source_path' in data:
        backup.source_path = data['source_path']
    if 'dropbox_path' in data:
        backup.dropbox_path = data['dropbox_path']
    if 'destination_type' in data:
        backup.destination_type = data['destination_type']
    if 'destination_path' in data:
        backup.destination_path = data['destination_path']
    if 'exclusions' in data:
        backup.exclusions = json.dumps(data['exclusions'])
    if 'schedule_type' in data:
        backup.schedule_type = data['schedule_type']
    if 'bidirectional' in data:
        backup.bidirectional = data['bidirectional']
    if 'night_only' in data:
        backup.night_only = data['night_only']
    if 'is_active' in data:
        backup.is_active = data['is_active']

    db.session.commit()
    return backup

def delete_backup(backup_id):
    from models import Backup, db
    backup = Backup.query.get(backup_id)
    if not backup:
        return False

    db.session.delete(backup)
    db.session.commit()
    return True
