import pytest
from app import app, user_visits

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"
    # Очищаем хранилище счётчиков перед каждым тестом
    user_visits.clear()
    with app.test_client() as client:
        yield client

def login(client, username="user", password="qwerty", remember=False):
    return client.post("/login", data={
        "username": username,
        "password": password,
        "remember": "on" if remember else ""
    }, follow_redirects=True)

def logout(client):
    return client.get("/logout", follow_redirects=True)

# 1. Счётчик для одного пользователя
def test_counter_increments_for_authenticated_user(client):
    login(client)
    r1 = client.get("/counter")
    assert b"1" in r1.data
    r2 = client.get("/counter")
    assert b"2" in r2.data

# 2. Разные пользователи имеют разные счётчики
def test_counter_separate_for_different_users(client):
    # Первый пользователь
    login(client, username="user", password="qwerty")
    client.get("/counter")
    r1 = client.get("/counter")
    assert b"2" in r1.data

    # Выход
    logout(client)

    # Второй пользователь
    login(client, username="user1", password="qwerty")
    r2 = client.get("/counter")
    assert b"1" in r2.data  # Счётчик начинается с 1

# 3. Неавторизованный не видит счётчик (редирект)
def test_counter_redirects_for_guest(client):
    response = client.get("/counter", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

# 4. Успешный вход с редиректом на главную
def test_login_success(client):
    response = login(client)
    assert b"Success" in response.data
    assert b"Main Page" in response.data

# 5. Неудачный вход
def test_login_fail(client):
    response = client.post("/login", data={
        "username": "user",
        "password": "wrong"
    }, follow_redirects=True)
    assert b"Wrong login or password" in response.data

# 6. Редирект на запрашиваемую страницу после логина
def test_redirect_to_secret_after_login(client):
    response = client.get("/secret")
    assert response.status_code == 302
    login(client)
    response = client.get("/secret")
    assert b"Secret Page" in response.data

# 7. Доступ к секретной странице только для авторизованных
def test_secret_requires_login(client):
    response = client.get("/secret", follow_redirects=True)
    assert b"You need to authenticate to get access" in response.data

# 8. Авторизованный имеет доступ к секретной странице
def test_secret_access_authenticated(client):
    login(client)
    response = client.get("/secret")
    assert response.status_code == 200
    assert b"Secret Page" in response.data

# 9. Remember me устанавливает куку
def test_remember_me(client):
    response = client.post("/login", data={
        "username": "user",
        "password": "qwerty",
        "remember": "on"
    }, follow_redirects=False)
    cookies = response.headers.getlist("Set-Cookie")
    assert any("remember_token" in c for c in cookies)

# 10. Навбар для гостя
def test_navbar_for_guest(client):
    response = client.get("/")
    assert b"Log in" in response.data
    assert b"Secret" not in response.data

# 11. Навбар для пользователя
def test_navbar_for_user(client):
    login(client)
    response = client.get("/")
    assert b"Secret" in response.data
    assert b"Log in" not in response.data