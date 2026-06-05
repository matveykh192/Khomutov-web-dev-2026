# Лабораторная работа 6 — Отзывы к курсам

Доработанное приложение «Образовательный портал»: добавлена возможность
оставлять отзывы к онлайн-курсам.

## Запуск

```bash
python3 -m venv ve
. ve/bin/activate
pip install -r requirements.txt
```

Настроить подключение к БД в `app/config.py` (по умолчанию — sqlite).

Если будет работа с общей БД, в `app/migrations/env.py` добавьте функцию
`include_object` (см. методичку, пункт 6) **до** выполнения первой миграции.

```bash
cd app
export FLASK_APP=__init__.py
flask db init                                  # только в первый раз
flask db migrate -m "Initial migration"
flask db upgrade
flask run
```

При первом запуске миграции в БД заливаются три категории курсов
(см. `data_upgrades()` в файле миграции).

## Создание пользователя

```bash
cd app
flask shell
```
```python
from app.models import db, User
user = User(first_name='Иван', last_name='Иванов', login='user')
user.set_password('qwerty')
db.session.add(user)
db.session.commit()
```

## Запуск тестов

```bash
. ve/bin/activate
python -m pytest tests/
```

Тесты используют отдельную in-memory sqlite-БД и не трогают рабочую.

## Что было сделано

- **Модель `Review`** (`app/models.py`) — `id`, `rating`, `text`,
  `created_at`, `course_id`, `user_id` + отношения `course`, `user`
  (с `backref="reviews"`).
- **Миграция** на создание таблицы `reviews`
  (`app/migrations/versions/*_initial_migration_with_reviews.py`).
- **Репозиторий** `ReviewRepository`
  (`app/repositories/review_repository.py`) — получение последних
  N отзывов, пагинация с тремя видами сортировки, поиск отзыва
  текущего пользователя, создание отзыва с пересчётом
  `rating_sum`/`rating_num` курса.
- **Маршруты** в `app/courses.py`:
  - `GET /courses/<id>` — добавлено отображение 5 последних отзывов
    и форма для нового отзыва внизу.
  - `GET /courses/<id>/reviews` — все отзывы курса с пагинацией и
    фильтром сортировки (по новизне / сначала положительные /
    сначала отрицательные). Параметр `sort` пробрасывается между
    страницами.
  - `POST /courses/<id>/reviews/create` — создание отзыва, защищено
    `@login_required`, не даёт оставить второй отзыв, валидирует
    `rating ∈ {0..5}` и непустой текст.
- **Шаблоны**: `courses/show.html` (доработан), `courses/reviews.html`
  (новый), `courses/_review_form.html` и `courses/_review_item.html`
  (партиалы).
- **Тесты** (`tests/test_reviews.py`, 32 теста) — модель, репозиторий,
  все три маршрута, граничные случаи валидации, пагинация с
  сохранением сортировки, повторный отзыв одним пользователем.
