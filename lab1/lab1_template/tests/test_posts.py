import pytest
import re
from datetime import datetime
from app import app as application


# Старые тесты
def test_posts_index(client):
    response = client.get("/posts")
    assert response.status_code == 200
    assert "Последние посты" in response.text


def test_posts_index_template(client, captured_templates, mocker, posts_list):
    with captured_templates as templates:
        # Мокаем функцию posts_list, чтобы она возвращала наш фиктивный список
        mocker.patch("app.posts_list", return_value=posts_list, autospec=True)

        _ = client.get("/posts")
        assert len(templates) == 1
        template, context = templates[0]
        assert template.name == "posts.html"
        assert context["title"] == "Посты"
        assert len(context["posts"]) == 1


# 1. Проверка главной страницы (index)
def test_index_status(client):
    response = client.get("/")
    assert response.status_code == 200


def test_index_template(client, captured_templates):
    with captured_templates as templates:
        client.get("/")
        template, context = templates[0]
        assert template.name == "index.html"


# 2. Проверка страницы "Об авторе"
def test_about_status(client):
    response = client.get("/about")
    assert response.status_code == 200


def test_about_template(client, captured_templates):
    with captured_templates as templates:
        client.get("/about")
        template, context = templates[0]
        assert template.name == "about.html"


# 3. Проверка отдельного поста (post)
def test_post_valid_status(client):
    response = client.get("/posts/0")
    assert response.status_code == 200


def test_post_invalid_status(client):
    response = client.get("/posts/10")
    assert response.status_code == 404
    response = client.get("/posts/-1")
    assert response.status_code == 404


def test_post_template(client, captured_templates):
    with captured_templates as templates:
        client.get("/posts/0")
        template, context = templates[0]
        assert template.name == "post.html"
        assert "title" in context
        assert "post" in context
        assert context["post"]["title"] == context["title"]


# 4. Проверка наличия всех данных поста на странице
def test_post_contains_author(client):
    response = client.get("/posts/0")
    assert "Автор:" in response.text
    author_pattern = r"([А-Яа-я]+\s[А-Яа-я]+\s[А-Яа-я]+)"
    assert re.search(author_pattern, response.text)


def test_post_contains_date(client):
    response = client.get("/posts/0")
    # Проверяем, что дата есть и в правильном формате
    date_pattern = r"\d{2}\.\d{2}\.\d{4}"
    assert re.search(date_pattern, response.text)


def test_post_contains_image(client):
    response = client.get("/posts/0")
    # Ищем тег img с src
    assert "<img" in response.text
    assert "/static/images/" in response.text


def test_post_contains_text(client):
    response = client.get("/posts/0")
    # Текст поста должен быть не пустым (хотя бы несколько слов)
    # Ищем абзац с классом post-text или просто параграф с текстом
    # в ответе есть хотя бы 10 слов?
    words = re.findall(r"\b\w+\b", response.text)
    assert len(words) > 10


def test_post_contains_comment_form(client):
    response = client.get("/posts/0")
    assert "Оставьте комментарий" in response.text
    assert "<form" in response.text
    assert "<textarea" in response.text
    assert "Отправить" in response.text


def test_post_contains_comments_section(client):
    response = client.get("/posts/0")
    # Секция комментариев должна присутствовать (даже если нет комментариев)
    assert "Комментарии" in response.text


# 5. Проверка формата даты в списке постов
def test_date_format_in_posts_list(client):
    response = client.get("/posts")
    date_pattern = r"\d{2}\.\d{2}\.\d{4}"
    assert re.search(date_pattern, response.text)


# 6. Проверка подвала (footer) на всех страницах
def test_footer_present_on_index(client):
    response = client.get("/")
    assert "Хомутов Матвей, группа 241-371" in response.text


# 7. Дополнительные тесты для проверки контекста (передаются ли все данные)
def test_posts_list_context_has_posts(client, captured_templates):
    with captured_templates as templates:
        client.get("/posts")
        _, context = templates[0]
        assert "posts" in context
        assert len(context["posts"]) == 5


def test_post_context_has_all_fields(client, captured_templates):
    with captured_templates as templates:
        client.get("/posts/0")
        _, context = templates[0]
        post = context["post"]
        expected_keys = {"title", "text", "author", "date", "image_id", "comments"}
        assert expected_keys.issubset(post.keys())


# 8. Тест для 404 при неверном индексе
def test_404_for_negative_index(client):
    response = client.get("/posts/-5")
    assert response.status_code == 404
