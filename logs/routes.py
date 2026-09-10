from flask import Blueprint, jsonify
from auth.utils import decode_jwt_token
from logs_service import get_all_logs, clear_logs
from functools import wraps
from flask import request

logs_bp = Blueprint('logs', __name__, url_prefix='/api/logs')

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

@logs_bp.route('', methods=['GET'])
@require_auth
def list_logs():
    logs = get_all_logs()
    return jsonify([log.to_dict() for log in logs]), 200

@logs_bp.route('/clear', methods=['POST'])
@require_auth
def clear():
    clear_logs()
    return jsonify({'message': 'Logs cleared'}), 200