from flask import request, jsonify
from flask_login import LoginManager, login_user, logout_user, current_user
from werkzeug.security import check_password_hash

from .models import SessionLocal, User
from .app import app

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    session = SessionLocal()
    user = session.query(User).get(int(user_id))
    session.close()
    return user


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid payload'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    session = SessionLocal()
    user = session.query(User).filter_by(username=username).first()
    session.close()

    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({'message': 'Logged in'})
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout')
def logout():
    logout_user()
    return jsonify({'message': 'Logged out'})


@app.route('/me')
def me():
    if current_user.is_authenticated:
        return jsonify({'username': current_user.username})
    return jsonify({'error': 'Unauthorized'}), 401
