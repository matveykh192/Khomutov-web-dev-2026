from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db
from routes import register_routes
import os

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    register_routes(app)

    with app.app_context():
        db.create_all()
        # Создать роли, если их нет
        from models import Role
        if Role.query.count() == 0:
            roles = [
                Role(name='Администратор', description='Полный доступ'),
                Role(name='Модератор', description='Управление контентом'),
                Role(name='Пользователь', description='Обычный пользователь')
            ]
            db.session.add_all(roles)
            db.session.commit()
    return app