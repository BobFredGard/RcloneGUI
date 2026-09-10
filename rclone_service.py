import subprocess
import json
import os
import re
import threading
import time
from collections import deque
from config import Config

CREATE_NO_WINDOW = 0x08000000

class RcloneService:
    def __init__(self):
        self.config_path = Config.RCLONE_CONFIG_PATH
        self.rclone_exe = Config.RCLONE_EXE_PATH
        self.running_processes = {}
        self.recently_finished = {}
        self.progress_buffers = {}
        self.progress_threads = {}

    def cleanup_stale_processes(self):
        stale = []
        for backup_id, process in self.running_processes.items():
            if process.poll() is not None:
                stale.append(backup_id)
        for backup_id in stale:
            del self.running_processes[backup_id]

    def get_config(self):
        if not os.path.exists(self.config_path):
            return None
        result = subprocess.run([self.rclone_exe, 'config', 'show', '--config', self.config_path],
                                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return None
        return result.stdout

    def list_remotes(self):
        result = subprocess.run([self.rclone_exe, 'listremotes', '--config', self.config_path],
                                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.split('\n') if line.strip()]

    def authorize_dropbox(self):
        try:
            result = subprocess.run([self.rclone_exe, 'authorize', 'dropbox', '--config', self.config_path],
                                    capture_output=True, text=True, timeout=120, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0:
                return {'success': True, 'output': 'Autorisation réussie'}
            return {'success': False, 'error': result.stderr or 'Erreur'}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def count_files(self, source):
        result = subprocess.run([self.rclone_exe, 'size', source, '--config', self.config_path, '--json'],
                                capture_output=True, text=True, timeout=60, creationflags=CREATE_NO_WINDOW)
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
            return data.get('count', 0)
        except:
            return None

    def is_process_running(self, pid):
        if pid is None:
            return False
        try:
            if os.name == 'nt':
                import psutil
                return psutil.pid_exists(pid)
            else:
                os.kill(pid, 0)
                return True
        except:
            return False

    def sync(self, source, destination, exclusions=None, backup_id=None, progress_callback=None, bidirectional=False, first_run=False):
        cmd = [
            self.rclone_exe,
            'bisync' if (bidirectional and not first_run) else ('copy' if bidirectional else 'sync'),
            source, destination,
            '--config', self.config_path,
            '--transfers', '2',
            '--checkers', '2',
            '--drive-chunk-size', '48M',
            '--progress',
            '--stats', '5s',
            '--verbose',
            '--timeout', '1h',
            '--retries', '10',
            '--no-update-modtime'
        ]
        if bidirectional and not first_run:
            cmd.append('--resync')
            source_name = source.replace('\\\\', '_').replace('\\', '_').replace(':', '_').replace('/', '_')
            dest_name = destination.replace(':', '_')
            # Portable: %LOCALAPPDATA%/rclone/bisync, créé si besoin
            bisync_dir = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'rclone', 'bisync')
            if os.path.isdir(bisync_dir):
                for f in os.listdir(bisync_dir):
                    if f.endswith('.lck') or f.endswith('.path1.lst') or f.endswith('.path2.lst'):
                        if source_name in f or dest_name in f:
                            try:
                                os.remove(os.path.join(bisync_dir, f))
                            except:
                                pass
        if exclusions:
            for exc in exclusions:
                cmd.extend(['--exclude', exc])

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, creationflags=CREATE_NO_WINDOW)

        pid = process.pid

        if backup_id:
            self.running_processes[backup_id] = process
            self.progress_buffers[backup_id] = {
                'stdout': deque(maxlen=5000),
                'progress': deque(maxlen=200),
                'transferred': deque(maxlen=200),
                'skipped': deque(maxlen=200),
                'failed': deque(maxlen=200)
            }
            t = threading.Thread(target=self._read_output, args=(backup_id, process), daemon=True)
            self.progress_threads[backup_id] = (t,)
            t.start()

        return {
            'success': None,
            'output': '',
            'error': '',
            'pid': pid
        }

    def _read_output(self, backup_id, process):
        buf = self.progress_buffers.get(backup_id)
        if not buf:
            return
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            stripped = line.rstrip('\n\r')
            buf['stdout'].append(stripped)
            if 'Transferred:' in line or 'ETA' in line or line.startswith('* '):
                buf['progress'].append(stripped)
            cat = self._categorize_line(stripped)
            if cat:
                buf[cat[0]].append(cat[1])

    @staticmethod
    def _categorize_line(line):
        if not line:
            return None
        # rclone verbose lines: "2024/07/30 11:00:00 INFO  : file.txt: Copied (new)"
        # or "2024/07/30 11:00:00 ERROR : file.txt: Failed ..."
        parts = line.split(' ', 3)
        if len(parts) < 4:
            return None
        level = parts[2].strip(':').strip().upper()
        rest = parts[3]
        if level in ('INFO', 'NOTICE'):
            if 'Copied' in rest or 'copied' in rest:
                return ('transferred', line)
            if 'Skipped' in rest or 'skipped' in rest or 'unchanged' in rest or 'same' in rest:
                return ('skipped', line)
            if 'Deleted' in rest or 'deleted' in rest:
                return ('transferred', line)
        if level in ('ERROR', 'WARNING'):
            return ('failed', line)
        return None

    def wait_for_backup(self, backup_id):
        if backup_id not in self.running_processes:
            return {'success': False, 'error': 'Backup not found'}
        process = self.running_processes[backup_id]
        process.wait()

        self.recently_finished[backup_id] = {
            'pid': process.pid,
            'finish_time': time.time()
        }

        current_time = time.time()
        self.recently_finished = {
            k: v for k, v in self.recently_finished.items()
            if current_time - v['finish_time'] < 5
        }

        buf = self.progress_buffers.pop(backup_id, None)
        stdout = ''.join(buf['stdout']) if buf else ''

        if backup_id in self.running_processes:
            del self.running_processes[backup_id]
        if backup_id in self.progress_threads:
            del self.progress_threads[backup_id]

        return {
            'success': process.returncode == 0,
            'output': stdout,
            'error': '',
            'pid': process.pid
        }

    def get_progress_data(self, backup_id):
        buf = self.progress_buffers.get(backup_id)
        if not buf:
            return None
        progress_lines = list(buf['progress'])
        current_file = None
        for line in reversed(progress_lines):
            if line.startswith('* '):
                current_file = line[2:].strip()
                break
        transfer_info = None
        for line in progress_lines:
            if 'Transferred:' in line:
                transfer_info = line.strip()
        return {
            'current_file': current_file,
            'transfer': transfer_info,
            'lines': progress_lines[-30:],
            'transferred': list(buf['transferred'])[-30:],
            'skipped': list(buf['skipped'])[-30:],
            'failed': list(buf['failed'])[-30:]
        }

    def is_backup_running(self, backup_id):
        if backup_id not in self.running_processes:
            return False
        process = self.running_processes[backup_id]
        return process.poll() is None

    def check_connection(self, remote):
        result = subprocess.run([self.rclone_exe, 'ls', remote, '--max-depth', '1', '--config', self.config_path, '--timeout', '30s'],
                                capture_output=True, text=True, timeout=60, creationflags=CREATE_NO_WINDOW)
        return result.returncode == 0

rclone_service = RcloneService()