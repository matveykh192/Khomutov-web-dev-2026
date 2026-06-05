import pytest
from app import create_app
from models import db, User, Role
from utils import hash_password

# ------------------ Fixtures ------------------
@pytest.fixture(scope='function')
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        db.create_all()
        # Создаём роли
        roles = ['Администратор', 'Модератор', 'Пользователь']
        for name in roles:
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name))
        db.session.commit()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_user_id(app):
    """Возвращает id администратора, создавая его в БД."""
    with app.app_context():
        admin_role = Role.query.filter_by(name='Администратор').first()
        admin = User(
            login='admin',
            password_hash=hash_password('Admin123!'),
            last_name='Иванов',
            first_name='Иван',
            middle_name='Иванович',
            role_id=admin_role.id
        )
        db.session.add(admin)
        db.session.commit()
        return admin.id

@pytest.fixture
def logged_in_client(client, admin_user_id):
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user_id
    return client

@pytest.fixture
def another_user(app):
    with app.app_context():
        user = User(
            login='testuser',
            password_hash=hash_password('Test123!'),
            last_name='Петров',
            first_name='Пётр',
            role_id=None
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        yield user_id
        db.session.delete(user)
        db.session.commit()


# ------------------ Тесты аутентификации (8) ------------------
def test_login_page_GET(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert 'Логин' in response.get_data(as_text=True)

def test_login_POST_valid(client, admin_user_id):
    response = client.post('/login', data={
        'login': 'admin',
        'password': 'Admin123!'
    }, follow_redirects=True)
    assert 'Вы успешно вошли' in response.get_data(as_text=True)

def test_login_POST_invalid_password(client):
    response = client.post('/login', data={
        'login': 'admin',
        'password': 'wrong'
    }, follow_redirects=True)
    assert 'Неверный логин или пароль' in response.get_data(as_text=True)

def test_login_POST_nonexistent_user(client):
    response = client.post('/login', data={
        'login': 'nobody',
        'password': '123'
    }, follow_redirects=True)
    assert 'Неверный логин или пароль' in response.get_data(as_text=True)

def test_logout(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    response = client.get('/logout', follow_redirects=True)
    assert 'Вы вышли из системы' in response.get_data(as_text=True)

def test_protected_page_redirects_to_login(client):
    response = client.get('/users/create')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_protected_edit_redirects_to_login(client):
    response = client.get('/users/1/edit')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']

def test_change_password_requires_login(client):
    response = client.get('/change-password', follow_redirects=True)
    assert 'Необходимо войти' in response.get_data(as_text=True)


# ------------------ Тесты просмотра (5) ------------------
def test_index_page_contains_user_list(client, admin_user_id):
    response = client.get('/')
    assert 'Иванов Иван Иванович' in response.get_data(as_text=True)

def test_view_user_page_accessible_without_login(client, admin_user_id):
    response = client.get('/users/1')
    assert response.status_code == 200
    assert 'Иванов' in response.get_data(as_text=True)

def test_view_user_shows_correct_data(client, admin_user_id):
    response = client.get('/users/1')
    text = response.get_data(as_text=True)
    assert 'admin' in text
    assert 'Иванов' in text
    assert 'Иван' in text

def test_view_user_404_for_nonexistent(client):
    response = client.get('/users/999')
    assert response.status_code == 404

def test_index_shows_roles(client, admin_user_id):
    response = client.get('/')
    assert 'Администратор' in response.get_data(as_text=True)


# ------------------ Тесты создания пользователя (15) ------------------
def test_create_page_accessible_only_when_logged_in(logged_in_client):
    response = logged_in_client.get('/users/create')
    assert response.status_code == 200
    assert 'Создание пользователя' in response.get_data(as_text=True)

def test_create_user_success(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'newuser',
        'password': 'StrongP@ss1',
        'last_name': 'Сидоров',
        'first_name': 'Сидор',
        'middle_name': 'Сидорович',
        'role': 2
    }, follow_redirects=True)
    assert 'Пользователь успешно создан' in response.get_data(as_text=True)
    assert 'Сидоров Сидор Сидорович' in response.get_data(as_text=True)

def test_create_user_without_role(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'norole',
        'password': 'StrongP@ss1',
        'last_name': 'Безролев',
        'first_name': 'Без',
        'middle_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'Пользователь успешно создан' in response.get_data(as_text=True)
    assert 'Безролев Без' in response.get_data(as_text=True)

def test_create_duplicate_login_fails(logged_in_client):
    logged_in_client.post('/users/create', data={
        'login': 'duplicate',
        'password': 'StrongP@ss1',
        'last_name': 'Дубль',
        'first_name': 'Дуб',
        'role': 0
    })
    response = logged_in_client.post('/users/create', data={
        'login': 'duplicate',
        'password': 'StrongP@ss1',
        'last_name': 'Дубль2',
        'first_name': 'Дуб2',
        'role': 0
    }, follow_redirects=True)
    assert 'Этот логин уже занят' in response.get_data(as_text=True)

def test_create_login_too_short(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'ab',
        'password': 'StrongP@ss1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'Логин должен быть не менее 5 символов' in response.get_data(as_text=True)

def test_create_login_contains_bad_chars(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'login!@#',
        'password': 'StrongP@ss1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'должен содержать только латинские буквы и цифры' in response.get_data(as_text=True)

def test_create_password_too_short(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'Sh1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'должен быть от 8 до 128 символов' in response.get_data(as_text=True)

def test_create_password_no_uppercase(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'strongpass1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'одну заглавную букву' in response.get_data(as_text=True)

def test_create_password_no_digit(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'StrongPass',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'одну цифру' in response.get_data(as_text=True)

def test_create_password_with_space(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'Strong Pass1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'не должен содержать пробелов' in response.get_data(as_text=True)

def test_create_password_invalid_char(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'StrongP@ss1§',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'недопустимые символы' in response.get_data(as_text=True)

def test_create_missing_last_name(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'StrongP@ss1',
        'last_name': '',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)

def test_create_missing_first_name(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'validlogin',
        'password': 'StrongP@ss1',
        'last_name': 'Иванов',
        'first_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)

def test_create_empty_login(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': '',
        'password': 'StrongP@ss1',
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)

def test_create_password_cyrillic_allowed(logged_in_client):
    response = logged_in_client.post('/users/create', data={
        'login': 'cyrillicuser',
        'password': 'Пароль123!',
        'last_name': 'Кириллов',
        'first_name': 'Кирилл',
        'role': 0
    }, follow_redirects=True)
    assert 'Пользователь успешно создан' in response.get_data(as_text=True)


# ------------------ Тесты редактирования (10) ------------------
def test_edit_page_accessible_when_logged_in(logged_in_client):
    response = logged_in_client.get('/users/1/edit')
    assert response.status_code == 200
    assert 'Редактирование' in response.get_data(as_text=True)

def test_edit_user_success(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Петров',
        'first_name': 'Петр',
        'middle_name': 'Петрович',
        'role': 2
    }, follow_redirects=True)
    assert 'Данные пользователя обновлены' in response.get_data(as_text=True)
    assert 'Петров Петр Петрович' in response.get_data(as_text=True)

def test_edit_missing_last_name(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': '',
        'first_name': 'Петр',
        'middle_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)

def test_edit_missing_first_name(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Петров',
        'first_name': '',
        'middle_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)

def test_edit_remove_role(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Петров',
        'first_name': 'Петр',
        'middle_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'обновлены' in response.get_data(as_text=True)
    with logged_in_client.application.app_context():
        user = db.session.get(User, 1)
        assert user.role_id is None

def test_edit_set_role(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Петров',
        'first_name': 'Петр',
        'middle_name': '',
        'role': 1
    }, follow_redirects=True)
    assert 'обновлены' in response.get_data(as_text=True)
    with logged_in_client.application.app_context():
        user = db.session.get(User, 1)
        assert user.role_id == 1

def test_edit_nonexistent_user(logged_in_client):
    response = logged_in_client.get('/users/999/edit')
    assert response.status_code == 404

def test_edit_form_contains_current_data(logged_in_client):
    response = logged_in_client.get('/users/1/edit')
    html = response.get_data(as_text=True)
    assert 'Иванов' in html or 'Петров' in html

def test_edit_middle_name_optional(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Тестов',
        'first_name': 'Тест',
        'middle_name': '',
        'role': 0
    }, follow_redirects=True)
    assert 'обновлены' in response.get_data(as_text=True)

def test_edit_redirects_to_index(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'Иванов',
        'first_name': 'Иван',
        'role': 0
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'Список пользователей' in response.get_data(as_text=True)


# ------------------ Тесты удаления (5) ------------------
def test_delete_user_success(logged_in_client, another_user):
    user_id = another_user
    response = logged_in_client.post(f'/users/{user_id}/delete', follow_redirects=True)
    assert 'Пользователь удалён' in response.get_data(as_text=True)
    with logged_in_client.application.app_context():
        user = db.session.get(User, user_id)
        assert user is None

def test_delete_nonexistent_user(logged_in_client):
    response = logged_in_client.post('/users/999/delete', follow_redirects=True)
    assert response.status_code == 404

def test_delete_not_allowed_for_anonymous(client):
    response = client.post('/users/1/delete', follow_redirects=True)
    assert 'Необходимо войти' in response.get_data(as_text=True)

def test_delete_requires_post(logged_in_client):
    response = logged_in_client.get('/users/1/delete')
    assert response.status_code == 405

def test_delete_redirects_to_index(logged_in_client, another_user):
    response = logged_in_client.post(f'/users/{another_user}/delete', follow_redirects=True)
    assert 'Список пользователей' in response.get_data(as_text=True)


# ------------------ Тесты смены пароля (10) ------------------
def test_change_password_page_accessible_when_logged_in(logged_in_client):
    response = logged_in_client.get('/change-password')
    assert response.status_code == 200
    assert 'Смена пароля' in response.get_data(as_text=True)

def test_change_password_success(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'NewPass456!',
        'confirm_password': 'NewPass456!'
    }, follow_redirects=True)
    assert 'Пароль успешно изменён' in response.get_data(as_text=True)

def test_change_password_wrong_old(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'WrongOld!',
        'new_password': 'NewPass456!',
        'confirm_password': 'NewPass456!'
    }, follow_redirects=True)
    assert 'Старый пароль неверен' in response.get_data(as_text=True)

def test_change_password_mismatch(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'NewPass456!',
        'confirm_password': 'DifferentPass!'
    }, follow_redirects=True)
    assert 'Пароли не совпадают' in response.get_data(as_text=True)

def test_change_password_too_short(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'Sh1',
        'confirm_password': 'Sh1'
    }, follow_redirects=True)
    assert 'должен быть от 8 до 128 символов' in response.get_data(as_text=True)

def test_change_password_no_uppercase(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'weakpass1',
        'confirm_password': 'weakpass1'
    }, follow_redirects=True)
    assert 'заглавную букву' in response.get_data(as_text=True)

def test_change_password_no_digit(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'NoDigitHere!',
        'confirm_password': 'NoDigitHere!'
    }, follow_redirects=True)
    assert 'одну цифру' in response.get_data(as_text=True)

def test_change_password_with_space(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'Space Bad!1',
        'confirm_password': 'Space Bad!1'
    }, follow_redirects=True)
    assert 'не должен содержать пробелов' in response.get_data(as_text=True)

def test_change_password_cyrillic_allowed(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': 'Admin123!',
        'new_password': 'НовыйПароль123!',
        'confirm_password': 'НовыйПароль123!'
    }, follow_redirects=True)
    assert 'Пароль успешно изменён' in response.get_data(as_text=True)

def test_change_password_old_blank(logged_in_client):
    response = logged_in_client.post('/change-password', data={
        'old_password': '',
        'new_password': 'NewPass123!',
        'confirm_password': 'NewPass123!'
    }, follow_redirects=True)
    assert 'This field is required' in response.get_data(as_text=True)


# ------------------ Тесты ролей и отображения (6) ------------------
def test_index_shows_edit_button_only_for_auth(logged_in_client):
    response = logged_in_client.get('/')
    assert 'Редактировать' in response.get_data(as_text=True)
    assert 'Удалить' in response.get_data(as_text=True)

def test_index_no_edit_button_for_anonymous(client):
    response = client.get('/')
    assert 'Редактировать' not in response.get_data(as_text=True)
    assert 'Удалить' not in response.get_data(as_text=True)

def test_role_select_in_create_form(logged_in_client):
    response = logged_in_client.get('/users/create')
    html = response.get_data(as_text=True)
    assert 'Администратор' in html
    assert 'Модератор' in html
    assert 'Пользователь' in html
    assert 'Без роли' in html

def test_role_display_in_view(client, admin_user_id):
    response = client.get('/users/1')
    assert 'Администратор' in response.get_data(as_text=True)

def test_role_null_in_list(client):
    with client.application.app_context():
        user = User(login='norole2', password_hash=hash_password('Pass123!'), last_name='No', first_name='Role')
        db.session.add(user)
        db.session.commit()
    response = client.get('/')
    assert 'No Role' in response.get_data(as_text=True)
    assert '—' in response.get_data(as_text=True) or 'Без роли' in response.get_data(as_text=True)

def test_role_edit_keeps_original_role(logged_in_client):
    response = logged_in_client.post('/users/1/edit', data={
        'last_name': 'НоваяФам',
        'first_name': 'НовоеИмя',
        'role': 1
    }, follow_redirects=True)
    assert 'обновлены' in response.get_data(as_text=True)


# ------------------ Тесты доступа (6) ------------------
def test_create_button_visible_to_auth(logged_in_client):
    response = logged_in_client.get('/')
    assert 'Создание пользователя' in response.get_data(as_text=True)

def test_create_button_hidden_from_anonymous(client):
    response = client.get('/')
    assert 'Создание пользователя' not in response.get_data(as_text=True)

def test_edit_other_users_allowed_for_auth(logged_in_client, another_user):
    response = logged_in_client.get(f'/users/{another_user}/edit')
    assert response.status_code == 200

def test_delete_other_users_allowed_for_auth(logged_in_client, another_user):
    response = logged_in_client.post(f'/users/{another_user}/delete', follow_redirects=True)
    assert 'Пользователь удалён' in response.get_data(as_text=True)

def test_anonymous_cannot_edit_any(client):
    response = client.get('/users/1/edit', follow_redirects=True)
    assert 'Необходимо войти' in response.get_data(as_text=True)

def test_anonymous_cannot_delete_any(client):
    response = client.post('/users/1/delete', follow_redirects=True)
    assert 'Необходимо войти' in response.get_data(as_text=True)