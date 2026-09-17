from flask import Blueprint, request, jsonify, current_app
from models import db, User
from auth.utils import generate_jwt_token, decode_jwt_token, hash_password, verify_password

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    # Mode intranet : le 1er compte est libre (bootstrap), les suivants
    # sont bloqués sauf ALLOW_REGISTRATION=true. Empêche n'importe quel
    # poste du LAN de se créer un compte.
    if not current_app.config.get('ALLOW_REGISTRATION', False):
        if User.query.count() > 0:
            return jsonify({'error': 'Inscriptions désactivées'}), 403

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400

    user = User(
        username=username,
        password_hash=hash_password(password),
        authy_secret=''
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not verify_password(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    jwt_token = generate_jwt_token(user.id)
    return jsonify({'token': jwt_token, 'user': {'id': user.id, 'username': user.username}}), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logged out successfully'}), 200

@auth_bp.route('/check', methods=['GET'])
def check():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'authenticated': False}), 401

    token = auth_header.split(' ')[1]
    user_id = decode_jwt_token(token)
    if not user_id:
        return jsonify({'authenticated': False}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'authenticated': False}), 401

    return jsonify({'authenticated': True, 'user': {'id': user.id, 'username': user.username}}), 200
