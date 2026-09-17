import threading
import time
import json
import os
from datetime import datetime, timezone
from rclone_service import rclone_service
import logging

logging.basicConfig(filename='D:/ServerFolders/RcloneGUI/scheduler.log', level=logging.DEBUG)

class SchedulerService:
    def __init__(self):
        self.running = False
        self.thread = None
        self.app = None
        self.backup_queue = []  # Circular queue of backup IDs
        self.current_index = 0   # Current position in queue
        self.lock = threading.Lock()

    def set_app(self, app):
        self.app = app

    def build_queue(self):
        """Build the queue from active backups in creation order"""
        with self.app.app_context():
            from models import db, Backup
            backups = Backup.query.filter_by(is_active=True, schedule_type='on').order_by(Backup.id).all()
            self.backup_queue = [b.id for b in backups]
            self.current_index = 0

    def add_to_queue(self, backup_id):
        """Add a backup to the end of the queue"""
        with self.lock:
            if backup_id not in self.backup_queue:
                self.backup_queue.append(backup_id)

    def remove_from_queue(self, backup_id):
        """Remove a backup from the queue"""
        with self.lock:
            if backup_id in self.backup_queue:
                self.backup_queue.remove(backup_id)
                if self.current_index >= len(self.backup_queue):
                    self.current_index = 0

    def get_next_backup_id(self):
        """Get next backup ID in circular manner"""
        if not self.backup_queue:
            print("DEBUG: backup_queue is empty")
            return None
        
        # Get current hour in local time
        current_hour = datetime.now().hour
        is_night_hours = current_hour >= 20 or current_hour < 6
        is_morning = current_hour >= 6 and current_hour < 7
        
        # Reset night_done at 6am (start of day)
        if is_morning:
            with self.app.app_context():
                from models import db, Backup
                db.session.query(Backup).filter_by(night_only=True).update({'night_done': False})
                db.session.commit()
        
        print(f"DEBUG: hour={current_hour}, night={is_night_hours}, queue_size={len(self.backup_queue)}")
        
        # Find next active backup
        attempts = 0
        while attempts < len(self.backup_queue):
            backup_id = self.backup_queue[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.backup_queue)
            attempts += 1
            
            with self.app.app_context():
                from models import db, Backup
                backup = db.session.get(Backup, backup_id)
                if not backup or not backup.is_active or backup.schedule_type != 'on':
                    print(f"DEBUG: skipping {backup_id} - active={backup.is_active if backup else None}, schedule={backup.schedule_type if backup else None}")
                    continue
                # Check night_only restriction
                if backup.night_only:
                    if not is_night_hours:
                        print(f"DEBUG: skipping {backup_id} - night_only but not night hours")
                        continue
                    if backup.night_done:
                        print(f"DEBUG: skipping {backup_id} - night_done already")
                        continue
                    # Mark as done so it won't run again tonight
                    backup.night_done = True
                    db.session.commit()
                print(f"DEBUG: returning backup_id={backup_id}")
                return backup_id
        
        print("DEBUG: no valid backup found")
        return None

    def run_backup(self, backup_id):
        if not self.app:
            return

        with self.app.app_context():
            from models import db, Backup

            backup = db.session.get(Backup, backup_id)
            if not backup or not backup.is_active or backup.schedule_type != 'on':
                return

            backup.started_at = datetime.now(timezone.utc)
            db.session.commit()

            exclusions = []
            if backup.exclusions:
                try:
                    exclusions = json.loads(backup.exclusions)
                except:
                    pass

            source = backup.source_path
            if backup.destination_type == 'dropbox':
                destination = f"dropbox:{backup.destination_path or backup.dropbox_path}"
            else:
                destination = backup.destination_path or backup.dropbox_path
                try:
                    os.makedirs(destination, exist_ok=True)
                except Exception as e:
                    print(f"DEBUG: cannot create destination directory {destination}: {e}")
            is_first_run = backup.last_run is None

            result = rclone_service.sync(source, destination, exclusions, backup.id, bidirectional=backup.bidirectional, first_run=is_first_run)
            
            if result.get('pid'):
                backup.pid = result['pid']
                db.session.commit()
            
            result = rclone_service.wait_for_backup(backup.id)

            backup.last_run = datetime.now(timezone.utc)
            backup.last_status = 'success' if result['success'] else 'failed'
            backup.started_at = None
            backup.pid = None
            db.session.commit()

            if not result['success']:
                from logs_service import add_log
                add_log(backup.id, backup.name, 'Sauvegarde echouee', result.get('error', ''))

            db.session.commit()

    def start(self):
        self.running = True
        self.build_queue()
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False

    def _run_loop(self):
        rebuild_counter = 0
        while self.running:
            try:
                rebuild_counter += 1
                # Rebuild queue every 60 iterations (~5 minutes) to pick up new backups
                if rebuild_counter >= 60:
                    print("DEBUG: rebuilding queue...")
                    self.build_queue()
                    rebuild_counter = 0
                
                print("DEBUG: _run_loop running")
                if self.app and self.backup_queue:
                    backup_id = self.get_next_backup_id()
                    if backup_id:
                        print(f"DEBUG: running backup {backup_id}")
                        self.run_backup(backup_id)
                    else:
                        print("DEBUG: no backup to run, waiting...")
                else:
                    print(f"DEBUG: no queue or no app, queue={self.backup_queue}, app={bool(self.app)}")
            except Exception as e:
                import traceback
                print(f"DEBUG ERROR: {e}")
                traceback.print_exc()
            time.sleep(5)  # Wait 5 seconds between backups

    def on_backup_created(self, backup_id):
        """Called when a new backup is created"""
        with self.app.app_context():
            from models import db, Backup
            backup = db.session.get(Backup, backup_id)
            if backup and backup.is_active and backup.schedule_type == 'on':
                self.add_to_queue(backup_id)

    def on_backup_deleted(self, backup_id):
        """Called when a backup is deleted"""
        self.remove_from_queue(backup_id)

    def on_schedule_enabled(self, backup_id):
        """Called when a backup's schedule_type is set to 'on'"""
        with self.app.app_context():
            from models import db, Backup
            backup = db.session.get(Backup, backup_id)
            if backup and backup.is_active and backup.schedule_type == 'on':
                self.add_to_queue(backup_id)

scheduler_service = SchedulerService()