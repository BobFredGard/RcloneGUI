from models import db, BackupLog

def add_log(backup_id, backup_name, message, error_details=None):
    log = BackupLog(
        backup_id=backup_id,
        backup_name=backup_name,
        message=message,
        error_details=error_details
    )
    db.session.add(log)
    db.session.commit()
    return log

def get_all_logs(limit=100):
    return BackupLog.query.order_by(BackupLog.created_at.desc()).limit(limit).all()

def get_logs_by_backup(backup_id):
    return BackupLog.query.filter_by(backup_id=backup_id).order_by(BackupLog.created_at.desc()).all()

def clear_logs():
    BackupLog.query.delete()
    db.session.commit()