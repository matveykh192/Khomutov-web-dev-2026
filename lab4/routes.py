from flask import render_template, redirect, url_for, request, flash, session, abort, jsonify
from functools import wraps
from models import db, User, Role
from forms import LoginForm, CreateUserForm, EditUserForm, ChangePasswordForm
from utils import check_password, hash_password

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Необходимо войти в систему', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def register_routes(app):

    @app.route('/')
    def index():
        users = User.query.all()
        return render_template('index.html', users=users)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(login=form.login.data).first()
            if user and check_password(user.password_hash, form.password.data):
                session['user_id'] = user.id
                flash('Вы успешно вошли', 'success')
                return redirect(url_for('index'))
            flash('Неверный логин или пароль', 'danger')
        return render_template('login.html', form=form)

    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        flash('Вы вышли из системы', 'info')
        return redirect(url_for('index'))

    @app.route('/users/<int:user_id>')
    def view_user(user_id):
        user = User.query.get_or_404(user_id)
        return render_template('view_user.html', user=user)

    @app.route('/users/create', methods=['GET', 'POST'])
    @login_required
    def create_user():
        form = CreateUserForm()
        if form.validate_on_submit():
            role_id = form.role.data if form.role.data != 0 else None
            user = User(
                login=form.login.data,
                password_hash=hash_password(form.password.data),
                last_name=form.last_name.data,
                first_name=form.first_name.data,
                middle_name=form.middle_name.data or None,
                role_id=role_id
            )
            try:
                db.session.add(user)
                db.session.commit()
                flash('Пользователь успешно создан', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка при сохранении: {str(e)}', 'danger')
        # При ошибках валидации вернуть форму с подсветкой
        return render_template('user_form.html', form=form, title='Создание пользователя')

    @app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_user(user_id):
        user = User.query.get_or_404(user_id)
        form = EditUserForm(obj=user)
        # Устанавливаем роль в форму (0 если нет роли)
        if request.method == 'GET':
            form.role.data = user.role_id if user.role_id else 0
        if form.validate_on_submit():
            user.last_name = form.last_name.data
            user.first_name = form.first_name.data
            user.middle_name = form.middle_name.data or None
            user.role_id = form.role.data if form.role.data != 0 else None
            try:
                db.session.commit()
                flash('Данные пользователя обновлены', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'danger')
        return render_template('user_form.html', form=form, title='Редактирование пользователя')

    @app.route('/users/<int:user_id>/delete', methods=['POST'])
    @login_required
    def delete_user(user_id):
        user = User.query.get_or_404(user_id)
        try:
            db.session.delete(user)
            db.session.commit()
            flash('Пользователь удалён', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Не удалось удалить: {str(e)}', 'danger')
        return redirect(url_for('index'))

    @app.route('/change-password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        user = User.query.get(session['user_id'])
        form = ChangePasswordForm()
        if form.validate_on_submit():
            if not check_password(user.password_hash, form.old_password.data):
                flash('Старый пароль неверен', 'danger')
                return render_template('change_password.html', form=form)
            # Новый пароль уже прошёл валидацию
            user.password_hash = hash_password(form.new_password.data)
            try:
                db.session.commit()
                flash('Пароль успешно изменён', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка: {str(e)}', 'danger')
        return render_template('change_password.html', form=form)