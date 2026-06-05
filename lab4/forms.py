import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp, ValidationError
from models import User, Role

class LoginForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

def validate_login(form, field):
    if not re.match(r'^[A-Za-z0-9]+$', field.data):
        raise ValidationError('Логин должен содержать только латинские буквы и цифры')
    if len(field.data) < 5:
        raise ValidationError('Логин должен быть не менее 5 символов')

def validate_password(form, field):
    pwd = field.data
    if len(pwd) < 8 or len(pwd) > 128:
        raise ValidationError('Пароль должен быть от 8 до 128 символов')
    if not re.search(r'[A-ZА-Я]', pwd):
        raise ValidationError('Пароль должен содержать хотя бы одну заглавную букву')
    if not re.search(r'[a-zа-я]', pwd):
        raise ValidationError('Пароль должен содержать хотя бы одну строчную букву')
    if not re.search(r'\d', pwd):
        raise ValidationError('Пароль должен содержать хотя бы одну цифру')
    if re.search(r'\s', pwd):
        raise ValidationError('Пароль не должен содержать пробелов')
    allowed = r'^[A-Za-zА-Яа-я0-9~!?@#$%^&*_\-+()\[\]{}><\/\\|"\'.,:;]+$'
    if not re.match(allowed, pwd):
        raise ValidationError('Пароль содержит недопустимые символы')

class CreateUserForm(FlaskForm):
    login = StringField('Логин', validators=[DataRequired(), validate_login])
    password = PasswordField('Пароль', validators=[DataRequired(), validate_password])
    last_name = StringField('Фамилия', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    middle_name = StringField('Отчество')
    role = SelectField('Роль', coerce=int, validators=[])
    submit = SubmitField('Сохранить')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role.choices = [(0, 'Без роли')] + [(r.id, r.name) for r in Role.query.all()]

    def validate_login(self, field):
        if User.query.filter_by(login=field.data).first():
            raise ValidationError('Этот логин уже занят')

class EditUserForm(FlaskForm):
    last_name = StringField('Фамилия', validators=[DataRequired()])
    first_name = StringField('Имя', validators=[DataRequired()])
    middle_name = StringField('Отчество')
    role = SelectField('Роль', coerce=int, validators=[])
    submit = SubmitField('Сохранить')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role.choices = [(0, 'Без роли')] + [(r.id, r.name) for r in Role.query.all()]

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Старый пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), validate_password])
    confirm_password = PasswordField('Повторите пароль', validators=[DataRequired()])
    submit = SubmitField('Сменить пароль')

    def validate_confirm_password(self, field):
        if field.data != self.new_password.data:
            raise ValidationError('Пароли не совпадают')