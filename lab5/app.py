import re

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Role, VisitLog
from auth import check_rights
from reports import bp as reports_bp


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
app.config["SECRET_KEY"] = "secret"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Авторизуйтесь"

app.register_blueprint(reports_bp)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


SKIP_LOG_PREFIXES = ("/static/", "/favicon.ico")


@app.before_request
def log_visit():
    path = request.path

    if any(path.startswith(p) for p in SKIP_LOG_PREFIXES):
        return
    if request.method != "GET":
        return

    try:
        entry = VisitLog(
            path=path,
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def validate_login(login):
    if not login:
        return "Логин пуст"
    if len(login) < 5:
        return "Минимум 5 символов"
    if not re.match(r"^[a-zA-Z0-9]+$", login):
        return "Только латиница и цифры"
    return None


def validate_password(password):
    if len(password) < 8 or len(password) > 128:
        return "Длина 8-128 символов"
    if " " in password:
        return "Без пробелов"
    if not re.search(r"[A-Z]", password):
        return "Нет заглавной буквы"
    if not re.search(r"[a-z]", password):
        return "Нет строчной буквы"
    if not re.search(r"\d", password):
        return "Нет цифры"
    if not re.search(r"[~!?@#\$%\^&\*\_\-\+\(\)\[\]\{\}<>\/\\\|\"'\.,:;]", password):
        return "Нужен хотя бы 1 спецсимвол"

    allowed = r"^[A-Za-zА-Яа-я0-9~!?@#\$%\^&\*\_\-\+\(\)\[\]\{\}<>\/\\\|\"'\.,:;]+$"
    if not re.match(allowed, password):
        return "Недопустимые символы в пароле"
    return None



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(login=request.form["login"]).first()

        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            flash("Вход выполнен")
            return redirect(url_for("index"))
        else:
            flash("Ошибка входа")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))



@app.route("/")
def index():
    return render_template("index.html", users=User.query.all())


@app.route("/users/<int:id>")
@login_required
@check_rights("show")
def view_user(id):
    user = User.query.get_or_404(id)
    return render_template("user_view.html", user=user)


@app.route("/users/create", methods=["GET", "POST"])
@login_required
@check_rights("create")
def create_user():
    roles = Role.query.all()

    if request.method == "POST":
        login_val = request.form["login"]
        password = request.form["password"]

        errors = {}
        err = validate_login(login_val)
        if err:
            errors["login"] = err
        err = validate_password(password)
        if err:
            errors["password"] = err
        if not request.form.get("first_name"):
            errors["first_name"] = "Введите имя"

        if errors:
            flash("Ошибка формы")
            return render_template("user_form.html", user=None, roles=roles, errors=errors)

        # роль берётся из формы; если не задана -- по умолчанию User
        role_id = request.form.get("role_id")
        if not role_id:
            default_role = Role.query.filter_by(name="User").first()
            role_id = default_role.id if default_role else None

        user = User(
            login=login_val,
            password_hash=generate_password_hash(password),
            first_name=request.form["first_name"],
            last_name=request.form.get("last_name"),
            middle_name=request.form.get("middle_name"),
            role_id=role_id,
        )
        db.session.add(user)
        db.session.commit()

        flash("Создано")
        return redirect(url_for("index"))

    return render_template("user_form.html", user=None, roles=roles, errors={})


@app.route("/users/<int:id>/edit", methods=["GET", "POST"])
@login_required
@check_rights("edit")
def edit_user(id):
    user = User.query.get_or_404(id)
    roles = Role.query.all()

    if request.method == "POST":
        user.first_name = request.form["first_name"]
        user.last_name = request.form.get("last_name")
        user.middle_name = request.form.get("middle_name")

        # Роль может менять только админ
        if current_user.is_admin:
            user.role_id = request.form.get("role_id") or None

        db.session.commit()
        flash("Обновлено")
        return redirect(url_for("index"))

    return render_template("user_form.html", user=user, roles=roles, errors={})


@app.route("/users/<int:id>/delete", methods=["POST"])
@login_required
@check_rights("delete")
def delete_user(id):
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash("Удалено")
    return redirect(url_for("index"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        if not check_password_hash(current_user.password_hash, request.form["old"]):
            flash("Старый пароль неверный")
            return redirect(url_for("change_password"))

        if request.form["new"] != request.form["repeat"]:
            flash("Пароли не совпадают")
            return redirect(url_for("change_password"))

        err = validate_password(request.form["new"])
        if err:
            flash(err)
            return redirect(url_for("change_password"))

        current_user.password_hash = generate_password_hash(request.form["new"])
        db.session.commit()

        flash("Пароль изменён")
        return redirect(url_for("index"))

    return render_template("change_password.html")

def init_db():
    db.create_all()

    if not Role.query.first():
        db.session.add(Role(name="User", description="Пользователь"))
        db.session.add(Role(name="Admin", description="Администратор"))
        db.session.commit()

    if not User.query.filter_by(login="admin").first():
        admin_role = Role.query.filter_by(name="Admin").first()
        db.session.add(User(
            login="admin",
            password_hash=generate_password_hash("Admin1!"),
            first_name="Хомутов",
            last_name="Матвей",
            middle_name="Васильевич",
            role_id=admin_role.id,
        ))

    if not User.query.filter_by(login="user1").first():
        user_role = Role.query.filter_by(name="User").first()
        db.session.add(User(
            login="user1",
            password_hash=generate_password_hash("User1!ok"),
            first_name="Иван",
            last_name="Иванов",
            middle_name="Иванович",
            role_id=user_role.id,
        ))

    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
