"""
Тесты для Flask-приложения.
Запуск: pytest test_app.py -v
"""
import pytest
from app import app, validate_phone, format_phone, COOKIE_NAME, COOKIE_VALUE

@pytest.fixture
def client():
    """Тестовый клиент Flask."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_url_params_shows_passed_params(client):
    """Переданные параметры отображаются на странице."""
    response = client.get('/url-params?name=Alice&age=30')
    html = response.data.decode()
    assert 'name' in html
    assert 'Alice' in html
    assert 'age' in html
    assert '30' in html


def test_url_params_multiple_values(client):
    """Несколько параметров с одинаковым именем отображаются."""
    response = client.get('/url-params?color=red&color=blue')
    html = response.data.decode()
    assert 'red' in html
    assert 'blue' in html


def test_url_params_empty(client):
    """Страница без параметров показывает предупреждение."""
    response = client.get('/url-params')
    html = response.data.decode()
    assert response.status_code == 200
    assert 'Параметры URL не переданы' in html

def test_headers_shows_all_headers(client):
    """Все отправленные заголовки отображаются на странице."""
    response = client.get('/headers', headers={
        'X-Custom-Header': 'hello123',
        'Another-Header': 'world'
    })
    html = response.data.decode()
    assert 'X-Custom-Header' in html
    assert 'hello123' in html
    assert 'Another-Header' in html
    assert 'world' in html


def test_headers_shows_standard_headers(client):
    """Стандартные заголовки (Host, User-Agent) тоже видны."""
    response = client.get('/headers')
    html = response.data.decode()
    assert 'Host' in html

def test_cookie_set_when_absent(client):
    """Куки устанавливается, если его не было."""
    response = client.get('/cookies')
    assert COOKIE_NAME in response.headers.get('Set-Cookie', '')


def test_cookie_deleted_when_present(client):
    """Куки удаляется, если он уже был установлен."""
    client.get('/cookies')
    client.set_cookie(COOKIE_NAME, COOKIE_VALUE)
    response = client.get('/cookies')
    set_cookie = response.headers.get('Set-Cookie', '')
    assert COOKIE_NAME in set_cookie
    assert 'expires=' in set_cookie.lower() or 'max-age=0' in set_cookie.lower()


def test_cookie_page_shows_cookie_info(client):
    """Страница отображает информацию о состоянии куки."""
    response = client.get('/cookies')
    html = response.data.decode()
    assert COOKIE_NAME in html

def test_form_params_shows_submitted_data(client):
    """Данные формы отображаются после отправки POST."""
    response = client.post('/form-params', data={
        'name': 'Иван',
        'email': 'ivan@example.com',
        'message': 'Привет!'
    })
    html = response.data.decode()
    assert 'Иван' in html
    assert 'ivan@example.com' in html
    assert 'Привет!' in html


def test_form_params_get_shows_empty_form(client):
    """GET-запрос показывает пустую форму без данных."""
    response = client.get('/form-params')
    html = response.data.decode()
    assert response.status_code == 200
    assert 'Полученные данные формы' not in html

def test_validate_valid_11_digits_plus7():
    """Номер с +7 и 11 цифрами — валиден."""
    valid, error = validate_phone('+7 (123) 456-75-90')
    assert valid is True
    assert error is None


def test_validate_valid_11_digits_8():
    """Номер, начинающийся с 8, и 11 цифр — валиден."""
    valid, error = validate_phone('8(123)4567590')
    assert valid is True
    assert error is None


def test_validate_valid_10_digits():
    """Номер без префикса и 10 цифр — валиден."""
    valid, error = validate_phone('123.456.75.90')
    assert valid is True
    assert error is None


def test_validate_wrong_digit_count():
    """Неверное количество цифр — ошибка о количестве."""
    valid, error = validate_phone('12345')
    assert valid is False
    assert 'Неверное количество цифр' in error


def test_validate_invalid_chars():
    """Недопустимые символы — соответствующая ошибка."""
    valid, error = validate_phone('123abc456')
    assert valid is False
    assert 'недопустимые символы' in error


def test_format_phone_10_digits():
    """10-значный номер форматируется корректно (добавляется 8)."""
    result = format_phone('1234567890')
    assert result == '8-123-456-78-90'


def test_format_phone_11_digits():
    """11-значный номер с +7 форматируется корректно (7 заменяется на 8)."""
    result = format_phone('+71234567890')
    assert result == '8-123-456-78-90'

def test_phone_page_valid_number_shows_formatted(client):
    """При правильном номере выводится отформатированный результат."""
    response = client.post('/phone', data={'phone': '+7 (123) 456-75-90'})
    html = response.data.decode()
    assert '8-123-456-75-90' in html
    assert 'is-invalid' not in html


def test_phone_page_wrong_digits_shows_error(client):
    """При неверном количестве цифр — сообщение об ошибке и класс is-invalid."""
    response = client.post('/phone', data={'phone': '12345'})
    html = response.data.decode()
    assert 'is-invalid' in html
    assert 'invalid-feedback' in html
    assert 'Неверное количество цифр' in html


def test_phone_page_invalid_chars_shows_error(client):
    """При недопустимых символах — сообщение об ошибке и класс is-invalid."""
    response = client.post('/phone', data={'phone': 'abc123'})
    html = response.data.decode()
    assert 'is-invalid' in html
    assert 'invalid-feedback' in html
    assert 'недопустимые символы' in html


def test_phone_page_get_shows_empty_form(client):
    """GET-запрос показывает чистую форму без ошибок."""
    response = client.get('/phone')
    html = response.data.decode()
    assert response.status_code == 200
    assert 'is-invalid' not in html
    assert 'alert-success' not in html
