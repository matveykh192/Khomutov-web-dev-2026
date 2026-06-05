import os
import sys
import uuid
import hashlib
import tempfile
import pytest

# чтобы пакет `app` импортировался
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db, User, Category, Image, Course, Review


@pytest.fixture
def app():
    # отдельный временный файл под sqlite — чтобы тесты не задевали dev-БД
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    upload_dir = tempfile.mkdtemp()

    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_ECHO': False,
        'WTF_CSRF_ENABLED': False,
        'UPLOAD_FOLDER': upload_dir,
        'SECRET_KEY': 'test',
    })

    with app.app_context():
        db.create_all()
        _seed(db)
        yield app
        db.session.remove()
        db.drop_all()
        # на Windows SQLAlchemy держит файл — явно отпускаем
        db.engine.dispose()

    os.close(db_fd)
    # на Windows иногда файл всё ещё «занят» — не валим тесты из-за этого
    try:
        os.unlink(db_path)
    except (PermissionError, OSError):
        pass
    try:
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """Логинит дефолтного пользователя `user/qwerty`."""
    client.post('/auth/login', data={'login': 'user', 'password': 'qwerty'},
                follow_redirects=True)
    return client


def _seed(db):
    """Заполнение БД базовыми сущностями: 2 юзера, категория, картинка, курс."""
    u1 = User(first_name='Иван', last_name='Иванов', login='user')
    u1.set_password('qwerty')
    u2 = User(first_name='Пётр', last_name='Петров', login='petrov')
    u2.set_password('qwerty')
    db.session.add_all([u1, u2])

    cat = Category(name='Программирование')
    db.session.add(cat)

    img = Image(
        id=str(uuid.uuid4()),
        file_name='test.png',
        mime_type='image/png',
        md5_hash=hashlib.md5(b'test').hexdigest(),
    )
    db.session.add(img)
    db.session.commit()

    course = Course(
        name='Тестовый курс',
        short_desc='Краткое описание',
        full_desc='Полное описание для теста отзывов',
        category_id=cat.id,
        author_id=u1.id,
        background_image_id=img.id,
    )
    db.session.add(course)
    db.session.commit()


@pytest.fixture
def course(app):
    with app.app_context():
        return db.session.execute(db.select(Course)).scalar()


@pytest.fixture
def course_id(app):
    with app.app_context():
        return db.session.execute(db.select(Course)).scalar().id


@pytest.fixture
def user_id(app):
    with app.app_context():
        return db.session.execute(db.select(User).filter_by(login='user')).scalar().id


@pytest.fixture
def petrov_id(app):
    with app.app_context():
        return db.session.execute(db.select(User).filter_by(login='petrov')).scalar().id
