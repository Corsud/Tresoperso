from .app import app
from . import models
from werkzeug.security import check_password_hash
from flask_login import LoginManager, login_user, logout_user, current_user
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


login_manager = LoginManager()
login_manager.login_view = None
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    session = models.SessionLocal()
    user = session.query(models.User).get(int(user_id))
    session.close()
    return user


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid payload'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    session = models.SessionLocal()
    user = session.query(models.User).filter_by(username=username).first()
    session.close()

    if user and check_password_hash(user.password, password):
        login_user(user)
        logger.info("User %s logged in", username)
        return jsonify({'message': 'Logged in'})
    logger.info("Failed login for %s", username)
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/logout')
def logout():
    if current_user.is_authenticated:
        logger.info("User %s logged out", current_user.username)
    else:
        logger.info("Logout without authenticated user")
    logout_user()
    return jsonify({'message': 'Logged out'})


@app.route('/me')
def me():
    if current_user.is_authenticated:
        return jsonify({'username': current_user.username})
    return jsonify({'error': 'Unauthorized'}), 401
