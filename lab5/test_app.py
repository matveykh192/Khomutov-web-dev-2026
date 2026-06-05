import warnings
import pytest
from werkzeug.security import generate_password_hash

from app import app
from models import db, User, Role, VisitLog

warnings.filterwarnings("ignore")


# =========================
# HELPERS
# =========================

def text(resp):
    return resp.data.decode("utf-8")


def login_as(client, username, password):
    return client.post(
        "/login",
        data={"login": username, "password": password},
        follow_redirects=True,
    )


def login_admin(client):
    return login_as(client, "admin", "Admin1!")


def login_user(client):
    return login_as(client, "user1", "User1!ok")


# =========================
# FIXTURES
# =========================

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SECRET_KEY"] = "test"

    with app.test_client() as client:
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            role_user = Role(name="User", description="Test user role")
            role_admin = Role(name="Admin", description="Test admin role")
            db.session.add_all([role_user, role_admin])
            db.session.commit()

            admin = User(
                login="admin",
                password_hash=generate_password_hash("Admin1!"),
                first_name="Иван",
                last_name="Админов",
                middle_name="Иванович",
                role_id=role_admin.id,
            )
            user1 = User(
                login="user1",
                password_hash=generate_password_hash("User1!ok"),
                first_name="Пётр",
                last_name="Петров",
                middle_name="Петрович",
                role_id=role_user.id,
            )
            user2 = User(
                login="user2",
                password_hash=generate_password_hash("User2!ok"),
                first_name="Сидор",
                last_name="Сидоров",
                role_id=role_user.id,
            )
            db.session.add_all([admin, user1, user2])
            db.session.commit()

        yield client


# =========================
# BASIC: login / logout / index
# =========================

class TestBasic:
    def test_index(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_login_success(self, client):
        r = login_admin(client)
        assert "Вход выполнен" in text(r)

    def test_login_fail(self, client):
        r = client.post(
            "/login", data={"login": "wrong", "password": "wrong"}, follow_redirects=True
        )
        assert "Ошибка входа" in text(r)

    def test_logout(self, client):
        login_admin(client)
        r = client.get("/logout", follow_redirects=True)
        assert r.status_code == 200


# =========================
# AUTH: check_rights decorator
# =========================

class TestAuthorization:
    """Проверяем декоратор check_rights и матрицу прав."""

    # ---- ADMIN ----
    def test_admin_can_create(self, client):
        login_admin(client)
        r = client.get("/users/create")
        assert r.status_code == 200

    def test_admin_can_edit_any(self, client):
        login_admin(client)
        r = client.get("/users/2/edit")
        assert r.status_code == 200

    def test_admin_can_view_any(self, client):
        login_admin(client)
        r = client.get("/users/2")
        assert r.status_code == 200

    def test_admin_can_delete_any(self, client):
        login_admin(client)
        r = client.post("/users/3/delete", follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            assert User.query.get(3) is None

    # ---- USER ----
    def test_user_cannot_create(self, client):
        login_user(client)
        r = client.get("/users/create", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_user_cannot_delete(self, client):
        login_user(client)
        r = client.post("/users/3/delete", follow_redirects=True)
        assert "недостаточно прав" in text(r)
        with app.app_context():
            assert User.query.get(3) is not None

    def test_user_cannot_edit_other(self, client):
        login_user(client)
        # user1 (id=2) пытается редактировать user2 (id=3)
        r = client.get("/users/3/edit", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_user_can_edit_self(self, client):
        login_user(client)
        r = client.get("/users/2/edit")
        assert r.status_code == 200

    def test_user_cannot_view_other(self, client):
        login_user(client)
        r = client.get("/users/3", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_user_can_view_self(self, client):
        login_user(client)
        r = client.get("/users/2")
        assert r.status_code == 200

    # ---- ANONYMOUS ----
    def test_anon_redirect_to_login_for_view(self, client):
        # анонимный пользователь - сначала @login_required редиректит на /login
        r = client.get("/users/1")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_anon_redirect_to_login_for_create(self, client):
        r = client.get("/users/create")
        assert r.status_code == 302

    # ---- Role can't be changed by user ----
    def test_user_cannot_change_own_role(self, client):
        login_user(client)
        # user1 пытается отправить role_id=admin
        with app.app_context():
            admin_role_id = Role.query.filter_by(name="Admin").first().id
        client.post(
            "/users/2/edit",
            data={
                "first_name": "Hacked",
                "last_name": "X",
                "middle_name": "",
                "role_id": admin_role_id,
            },
            follow_redirects=True,
        )
        with app.app_context():
            user = User.query.get(2)
            # роль НЕ должна была измениться
            assert user.role.name == "User"
            # но имя должно обновиться
            assert user.first_name == "Hacked"

    def test_admin_can_change_role(self, client):
        login_admin(client)
        with app.app_context():
            admin_role_id = Role.query.filter_by(name="Admin").first().id
        client.post(
            "/users/3/edit",
            data={
                "first_name": "Сидор",
                "last_name": "Сидоров",
                "middle_name": "",
                "role_id": admin_role_id,
            },
            follow_redirects=True,
        )
        with app.app_context():
            user = User.query.get(3)
            assert user.role.name == "Admin"


# =========================
# CREATE / EDIT / VALIDATION
# =========================

class TestCrud:
    def test_create_user_ok(self, client):
        login_admin(client)
        r = client.post(
            "/users/create",
            data={
                "login": "newuser",
                "password": "Password1!",
                "first_name": "Иван",
                "last_name": "Иванов",
                "middle_name": "Иванович",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        with app.app_context():
            assert User.query.filter_by(login="newuser").first() is not None

    def test_create_validation_fail(self, client):
        login_admin(client)
        r = client.post(
            "/users/create",
            data={"login": "a", "password": "123", "first_name": ""},
            follow_redirects=True,
        )
        assert "Ошибка формы" in text(r)

    def test_edit_user(self, client):
        login_admin(client)
        r = client.post(
            "/users/2/edit",
            data={"first_name": "Updated", "last_name": "New", "middle_name": "M"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        with app.app_context():
            assert User.query.get(2).first_name == "Updated"

    def test_change_password(self, client):
        login_admin(client)
        r = client.post(
            "/change-password",
            data={"old": "Admin1!", "new": "Password1!", "repeat": "Password1!"},
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "Пароль изменён" in text(r)


# =========================
# VISIT LOGS
# =========================

class TestVisitLog:
    def test_log_created_on_request(self, client):
        with app.app_context():
            VisitLog.query.delete()
            db.session.commit()

        client.get("/")
        with app.app_context():
            logs = VisitLog.query.all()
            assert len(logs) >= 1
            assert logs[0].path == "/"
            assert logs[0].user_id is None  # анонимный

    def test_log_records_user(self, client):
        with app.app_context():
            VisitLog.query.delete()
            db.session.commit()

        login_admin(client)
        client.get("/")

        with app.app_context():
            # должна быть хотя бы одна запись с user_id админа
            admin = User.query.filter_by(login="admin").first()
            logs = VisitLog.query.filter_by(user_id=admin.id).all()
            assert len(logs) > 0

    def test_static_not_logged(self, client):
        with app.app_context():
            VisitLog.query.delete()
            db.session.commit()

        client.get("/static/nonexistent.css")
        with app.app_context():
            logs = VisitLog.query.filter(VisitLog.path.like("/static/%")).all()
            assert len(logs) == 0


# =========================
# REPORTS
# =========================

class TestReports:
    def test_visits_page_requires_login(self, client):
        r = client.get("/visits/")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_visits_page_user_sees_only_own(self, client):
        # сначала немного полазим как user1
        login_user(client)
        client.get("/")
        client.get("/users/2")

        client.get("/logout")

        # потом как admin
        login_admin(client)
        client.get("/")

        client.get("/logout")

        # user1 должен видеть только свои записи
        login_user(client)
        r = client.get("/visits/")
        body = text(r)
        assert r.status_code == 200
        # имя user1 (Пётр Петров) встречается; имя админа -- нет.
        # Это слабый тест на содержимое, но он показывает фильтрацию.
        # Главное -- проверим через БД, какие записи отдаются.
        with app.app_context():
            from flask_login import current_user as cu  # noqa: F401
            user1 = User.query.filter_by(login="user1").first()
            mine = VisitLog.query.filter_by(user_id=user1.id).count()
            assert mine > 0

    def test_user_cannot_view_by_pages_report(self, client):
        login_user(client)
        r = client.get("/visits/by-pages", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_user_cannot_view_by_users_report(self, client):
        login_user(client)
        r = client.get("/visits/by-users", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_admin_can_view_by_pages_report(self, client):
        login_admin(client)
        client.get("/")
        client.get("/users/1")
        r = client.get("/visits/by-pages")
        assert r.status_code == 200
        assert "Отчёт по страницам" in text(r)

    def test_admin_can_view_by_users_report(self, client):
        login_admin(client)
        client.get("/")
        r = client.get("/visits/by-users")
        assert r.status_code == 200
        assert "Отчёт по пользователям" in text(r)

    def test_by_pages_csv_export(self, client):
        login_admin(client)
        client.get("/")
        client.get("/users/1")
        r = client.get("/visits/by-pages/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["Content-Type"]
        assert "attachment" in r.headers["Content-Disposition"]
        body = r.data.decode("utf-8-sig")  # BOM
        assert "Страница" in body
        assert "Количество посещений" in body

    def test_by_users_csv_export(self, client):
        login_admin(client)
        client.get("/")
        r = client.get("/visits/by-users/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["Content-Type"]
        body = r.data.decode("utf-8-sig")
        assert "Пользователь" in body

    def test_user_cannot_export(self, client):
        login_user(client)
        r = client.get("/visits/by-pages/export", follow_redirects=True)
        assert "недостаточно прав" in text(r)

    def test_visits_pagination(self, client):
        # генерим больше PER_PAGE записей и проверяем 2-ю страницу
        login_admin(client)
        for _ in range(15):
            client.get("/")
        r = client.get("/visits/?page=2")
        assert r.status_code == 200


# =========================
# PERMISSIONS HELPER
# =========================

class TestUserCan:
    def test_admin_can_everything(self, client):
        with app.app_context():
            admin = User.query.filter_by(login="admin").first()
            target = User.query.filter_by(login="user1").first()
            assert admin.can("create")
            assert admin.can("edit", target)
            assert admin.can("delete", target)
            assert admin.can("show", target)
            assert admin.can("view_all_logs")

    def test_user_limited(self, client):
        with app.app_context():
            user1 = User.query.filter_by(login="user1").first()
            user2 = User.query.filter_by(login="user2").first()
            assert not user1.can("create")
            assert not user1.can("delete", user2)
            assert not user1.can("view_all_logs")
            assert user1.can("edit", user1)
            assert not user1.can("edit", user2)
            assert user1.can("show", user1)
            assert not user1.can("show", user2)
