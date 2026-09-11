#!/usr/bin/env python
import os
os.environ['DB_USER'] = 'mokawlat_user'
os.environ['DB_PASSWORD'] = open('.db_password').read().strip()
os.environ['DB_HOST'] = '127.0.0.1'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'test_db'
os.environ['SECRET_KEY'] = 'test-application-secret-key-for-testing-only'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-testing-only-32chars!!'
os.environ['DYNAMICPRO_ENV'] = 'test'

from app import create_app
from database import db
from models import User
from werkzeug.security import check_password_hash

app = create_app()
with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        print(f'User found: id={user.id}, username={user.username}')
        print(f'password_hash exists: {user.password_hash is not None}')
        print(f'must_change_password: {user.must_change_password}')
        test_pw = 'admin123'
        result = check_password_hash(user.password_hash, test_pw)
        print(f'Password check admin123: {result}')
        wrong_result = check_password_hash(user.password_hash, 'wrong')
        print(f'Password check wrong: {wrong_result}')
    else:
        print('User admin not found in DB')
        all_users = User.query.all()
        print(f'All users: {[u.username for u in all_users]}')