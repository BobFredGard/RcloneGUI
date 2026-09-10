from flask import Blueprint, request, jsonify, Response, stream_with_context
import os
from backups.service import create_backup, get_all_backups, get_backup, update_backup, delete_backup
from rclone_service import rclone_service
from models import db, Backup
from auth.utils import decode_jwt_token
from config import DEFAULT_EXCLUSIONS
from functools import wraps
from datetime import datetime, timezone
import json
import time

backups_bp = Blueprint('backups', __name__, url_prefix='/api/backups')

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        token = auth_header.split(' ')[1]
        user_id = decode_jwt_token(token)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@backups_bp.route('', methods=['GET'])
@require_auth
def list_backups():
    backups = get_all_backups()
    return jsonify([b.to_dict() for b in backups]), 200

@backups_bp.route('/running', methods=['GET'])
@require_auth
def get_running_backups():
    """Get list of running and recently finished backups with their PIDs"""
    running = []
    current_time = time.time()

    # Currently running processes
    for backup_id, process in rclone_service.running_processes.items():
        if process.poll() is None:
            running.append({'id': int(backup_id), 'pid': process.pid})

    # Recently finished (keep PID for 5 seconds after completion)
    for backup_id, info in rclone_service.recently_finished.items():
        if current_time - info['finish_time'] < 5:
            if not any(r['id'] == int(backup_id) for r in running):
                running.append({'id': int(backup_id), 'pid': info['pid']})

    return jsonify(running), 200

from config import DEFAULT_EXCLUSIONS

@backups_bp.route('', methods=['POST'])
@require_auth
def create():
    data = request.get_json()
    if not data.get('name') or not data.get('source_path'):
        return jsonify({'error': 'Missing required fields'}), 400

    # Backward compat: if only dropbox_path provided, treat as type=dropbox
    dropbox_path = data.get('dropbox_path', '')
    destination_type = data.get('destination_type', 'dropbox' if dropbox_path else 'local')
    destination_path = data.get('destination_path', dropbox_path)

    exclusions = data.get('exclusions') if data.get('exclusions') else DEFAULT_EXCLUSIONS

    backup = create_backup(
        name=data['name'],
        source_path=data['source_path'],
        dropbox_path=dropbox_path,
        destination_type=destination_type,
        destination_path=destination_path,
        exclusions=exclusions,
        schedule_type=data.get('schedule_type', 'off'),
        bidirectional=data.get('bidirectional', False),
        night_only=data.get('night_only', False)
    )

    from scheduler import scheduler_service
    scheduler_service.on_backup_created(backup.id)

    return jsonify(backup.to_dict()), 201

@backups_bp.route('/<int:backup_id>', methods=['GET'])
@require_auth
def get(backup_id):
    backup = get_backup(backup_id)
    if not backup:
        return jsonify({'error': 'Backup not found'}), 404
    return jsonify(backup.to_dict()), 200

@backups_bp.route('/<int:backup_id>', methods=['PUT'])
@require_auth
def modify(backup_id):
    data = request.get_json()
    backup = update_backup(backup_id, data)
    if not backup:
        return jsonify({'error': 'Backup not found'}), 404

    if data.get('schedule_type') == 'on':
        from scheduler import scheduler_service
        scheduler_service.on_schedule_enabled(backup_id)

    return jsonify(backup.to_dict()), 200

@backups_bp.route('/<int:backup_id>', methods=['DELETE'])
@require_auth
def remove(backup_id):
    from scheduler import scheduler_service
    scheduler_service.on_backup_deleted(backup_id)
    if delete_backup(backup_id):
        return jsonify({'message': 'Backup deleted'}), 200
    return jsonify({'error': 'Backup not found'}), 404

@backups_bp.route('/<int:backup_id>/run', methods=['POST'])
@require_auth
def run(backup_id):
    try:
        # Check how many backups are currently running
        all_backups = get_all_backups()
        now = datetime.now(timezone.utc)
        running_count = 0
        for b in all_backups:
            if b.pid:
                running_count += 1
            elif b.started_at:
                if b.started_at.tzinfo is None:
                    started = b.started_at.replace(tzinfo=timezone.utc)
                else:
                    started = b.started_at
                if (now - started).total_seconds() < 300:
                    running_count += 1

        if running_count >= 3:
            return jsonify({'error': 'Trop de sauvegardes en cours (maximum 3)'}), 429

        backup = get_backup(backup_id)
        if not backup:
            return jsonify({'error': 'Backup not found'}), 404

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
                return jsonify({'error': f'Impossible de créer le dossier destination: {str(e)}'}), 500

        backup.started_at = datetime.now(timezone.utc)
        db.session.commit()

        result = rclone_service.sync(source, destination, exclusions, backup.id, bidirectional=backup.bidirectional)

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
            add_log(backup.id, backup.name, 'Sauvegarde échouée', result.get('error', ''))

        if backup.schedule_type == 'on':
            backup.next_run = datetime.now(timezone.utc)
        else:
            backup.next_run = None

        db.session.commit()

        return jsonify({'success': result['success'], 'error': result.get('error')}), 200 if result['success'] else 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@backups_bp.route('/<int:backup_id>/cancel', methods=['POST'])
@require_auth
def cancel(backup_id):
    try:
        import psutil

        backup = get_backup(backup_id)
        if not backup:
            return jsonify({'error': 'Backup not found'}), 404

        print(f"Cancel backup {backup_id}: started_at={backup.started_at}, pid={backup.pid}")

        if backup.pid:
            try:
                parent = psutil.Process(backup.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.kill()
                    except:
                        pass
                parent.kill()
                try:
                    parent.wait(timeout=3)
                except:
                    pass
            except psutil.NoSuchProcess:
                print(f"Process {backup.pid} not found")
            except Exception as e:
                print(f"Error killing process: {e}")

        if backup_id in rclone_service.running_processes:
            proc = rclone_service.running_processes[backup_id]
            try:
                proc.kill()
            except:
                pass
            del rclone_service.running_processes[backup_id]

        backup.started_at = None
        backup.pid = None
        backup.last_status = 'cancelled'
        db.session.commit()

        print(f"Backup {backup_id} cancelled successfully")
        return jsonify({'success': True}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@backups_bp.route('/<int:backup_id>/stream', methods=['GET'])
def stream_progress(backup_id):
    def generate():
        while True:
            process = rclone_service.running_processes.get(backup_id)
            if not process:
                yield f"data: {json.dumps({'done': True})}\n\n"
                break

            data = rclone_service.get_progress_data(backup_id)
            if data:
                current_file = data.get('current_file')
                transfer_info = data.get('transfer')
                payload = {
                    'current_file': current_file,
                    'transfer': transfer_info,
                    'transferred': data.get('transferred', []),
                    'skipped': data.get('skipped', []),
                    'failed': data.get('failed', [])
                }
                yield f"data: {json.dumps(payload)}\n\n"

            if process.poll() is not None:
                final = rclone_service.get_progress_data(backup_id)
                payload = {
                    'done': True,
                    'success': process.returncode == 0,
                    'transferred': final.get('transferred', []) if final else [],
                    'skipped': final.get('skipped', []) if final else [],
                    'failed': final.get('failed', []) if final else []
                }
                yield f"data: {json.dumps(payload)}\n\n"
                break

            time.sleep(0.5)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@backups_bp.route('/connections', methods=['GET'])
@require_auth
def list_connections():
    remotes = rclone_service.list_remotes()
    return jsonify({'remotes': remotes}), 200

@backups_bp.route('/connections/check', methods=['POST'])
@require_auth
def check_connection():
    data = request.get_json()
    remote = data.get('remote')
    if not remote:
        return jsonify({'error': 'Remote name required'}), 400

    remotes = rclone_service.list_remotes()
    is_valid = remote in remotes or remote + ':' in remotes
    return jsonify({'valid': is_valid}), 200

@backups_bp.route('/dropbox/authorize', methods=['POST'])
@require_auth
def authorize_dropbox():
    data = request.get_json()
    authy_code = data.get('authy_code')

    if not authy_code:
        return jsonify({'error': 'Authy code required'}), 400

    result = rclone_service.authorize_dropbox(authy_code)
    return jsonify(result), 200

@backups_bp.route('/export', methods=['GET'])
@require_auth
def export_backups():
    backups = get_all_backups()
    export_data = []
    for b in backups:
        export_data.append({
            'name': b.name,
            'source_path': b.source_path,
            'dropbox_path': b.dropbox_path,
            'destination_type': b.destination_type,
            'destination_path': b.destination_path,
            'exclusions': b.exclusions,
            'schedule_type': b.schedule_type,
            'night_only': b.night_only,
            'bidirectional': b.bidirectional,
            'is_active': b.is_active
        })
    return jsonify(export_data), 200

@backups_bp.route('/import', methods=['POST'])
@require_auth
def import_backups():
    data = request.get_json()
    backups_data = data.get('backups', [])
    selected = data.get('selected', None)

    results = {'imported': 0, 'skipped': 0, 'errors': []}

    for i, b_data in enumerate(backups_data):
        if selected is not None and i not in selected:
            results['skipped'] += 1
            continue

        try:
            existing = Backup.query.filter_by(name=b_data['name']).first()
            if existing:
                results['errors'].append(f"'{b_data['name']}' existe déjà")
                results['skipped'] += 1
                continue

            backup = create_backup(
                name=b_data['name'],
                source_path=b_data['source_path'],
                dropbox_path=b_data.get('dropbox_path', ''),
                destination_type=b_data.get('destination_type', 'dropbox'),
                destination_path=b_data.get('destination_path', b_data.get('dropbox_path', '')),
                exclusions=b_data.get('exclusions'),
                schedule_type=b_data.get('schedule_type', 'off'),
                bidirectional=b_data.get('bidirectional', False),
                night_only=b_data.get('night_only', False)
            )
            results['imported'] += 1

        except Exception as e:
            results['errors'].append(f"Erreur pour '{b_data.get('name', 'inconnu')}': {str(e)}")

    return jsonify(results), 200

@backups_bp.route('/browse', methods=['POST'])
@require_auth
def browse_directories():
    data = request.get_json()
    path = data.get('path', '')

    try:
        if not path:
            drives = []
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            return jsonify({'drives': drives, 'entries': []}), 200

        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return jsonify({'entries': [], 'error': 'Not a directory'}), 200

        entries = []
        try:
            for entry in os.scandir(path):
                if entry.is_dir():
                    entries.append(entry.path)
        except PermissionError:
            pass

        entries.sort()
        parent = os.path.dirname(path)
        return jsonify({'current': path, 'parent': parent, 'entries': entries}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
