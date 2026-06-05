# create_admin.py
from app import create_app
from models import db, User, Role
from utils import hash_password

app = create_app()
with app.app_context():
    admin_role = Role.query.filter_by(name='Администратор').first()
    if not admin_role:
        admin_role = Role(name='Администратор', description='Полный доступ')
        db.session.add(admin_role)
        print("Роль 'Администратор' добавлена")
    else:
        print("Роль уже существует")
    
    if not User.query.filter_by(login='admin').first():
        admin = User(
            login='admin',
            password_hash=hash_password('Admin123!'),
            last_name='Администратор',
            first_name='Системный',
            role_id=admin_role.id if admin_role else None
        )
        db.session.add(admin)
        db.session.commit()
        print("Пользователь admin создан")
    else:
        print("Пользователь admin уже есть")
    
    print("Готово!")