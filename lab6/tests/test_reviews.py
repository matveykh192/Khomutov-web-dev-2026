"""Тесты для функциональности отзывов (лаб. 6).

Тестируем только то, что добавили сами: модель Review, репозиторий,
маршруты show (в части отзывов), reviews, create_review.
"""
from datetime import datetime, timedelta
import pytest

from app.models import db, Review, Course, User


# ---------- ReviewRepository (unit) ----------

class TestReviewRepository:
    def test_add_review_creates_record(self, app, course_id, user_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            review = repo.add_review(course_id=course_id, user_id=user_id,
                                     rating=4, text='Норм')
            assert review.id is not None
            assert review.rating == 4
            assert review.text == 'Норм'
            assert review.created_at is not None

    def test_add_review_updates_course_rating(self, app, course_id, user_id, petrov_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            repo.add_review(course_id=course_id, user_id=user_id, rating=5, text='top')
            repo.add_review(course_id=course_id, user_id=petrov_id, rating=3, text='mid')
            course = db.session.get(Course, course_id)
            assert course.rating_num == 2
            assert course.rating_sum == 8
            assert course.rating == 4.0  # 8 / 2

    def test_get_user_review_returns_none_when_absent(self, app, course_id, user_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            assert repo.get_user_review(course_id, user_id) is None

    def test_get_user_review_returns_own(self, app, course_id, user_id, petrov_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            repo.add_review(course_id=course_id, user_id=user_id, rating=5, text='a')
            repo.add_review(course_id=course_id, user_id=petrov_id, rating=2, text='b')
            mine = repo.get_user_review(course_id, user_id)
            assert mine.user_id == user_id
            assert mine.rating == 5

    def test_get_latest_reviews_limit_and_order(self, app, course_id, user_id, petrov_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            # создаём 7 отзывов с возрастающим created_at
            base = datetime(2025, 1, 1, 12, 0, 0)
            users = [user_id, petrov_id]
            # для разнообразия user_id чередуем (но реально нам важна сортировка по времени)
            for i in range(7):
                r = Review(course_id=course_id, user_id=users[i % 2],
                           rating=i % 6, text=f'r{i}',
                           created_at=base + timedelta(hours=i))
                db.session.add(r)
            db.session.commit()

            latest = repo.get_latest_reviews(course_id, limit=5)
            assert len(latest) == 5
            # самый свежий (i=6) идёт первым
            assert latest[0].text == 'r6'
            assert latest[-1].text == 'r2'

    def test_sort_positive_first(self, app, course_id, user_id, petrov_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            db.session.add_all([
                Review(course_id=course_id, user_id=user_id, rating=1, text='bad'),
                Review(course_id=course_id, user_id=petrov_id, rating=5, text='top'),
                Review(course_id=course_id, user_id=user_id, rating=3, text='mid'),
            ])
            db.session.commit()
            page = repo.get_pagination_info(course_id, sort_order='positive', per_page=10)
            ratings = [r.rating for r in page.items]
            assert ratings == [5, 3, 1]

    def test_sort_negative_first(self, app, course_id, user_id, petrov_id):
        from app.repositories import ReviewRepository
        repo = ReviewRepository(db)
        with app.app_context():
            db.session.add_all([
                Review(course_id=course_id, user_id=user_id, rating=1, text='bad'),
                Review(course_id=course_id, user_id=petrov_id, rating=5, text='top'),
                Review(course_id=course_id, user_id=user_id, rating=3, text='mid'),
            ])
            db.session.commit()
            page = repo.get_pagination_info(course_id, sort_order='negative', per_page=10)
            ratings = [r.rating for r in page.items]
            assert ratings == [1, 3, 5]


# ---------- Route: course show ----------

class TestCourseShow:
    def test_show_has_reviews_section(self, client, course_id):
        resp = client.get(f'/courses/{course_id}')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'Последние отзывы' in body
        assert 'Все отзывы' in body

    def test_show_has_all_reviews_link(self, client, course_id):
        resp = client.get(f'/courses/{course_id}')
        body = resp.get_data(as_text=True)
        assert f'/courses/{course_id}/reviews' in body

    def test_show_displays_at_most_5_reviews(self, app, client, course_id, user_id, petrov_id):
        with app.app_context():
            # 7 отзывов с явно различающимся created_at
            base = datetime(2025, 1, 1, 12, 0, 0)
            for i in range(7):
                db.session.add(Review(
                    course_id=course_id,
                    user_id=user_id if i % 2 == 0 else petrov_id,
                    rating=i % 6,
                    text=f'отзыв-номер-{i}',
                    created_at=base + timedelta(hours=i),
                ))
            db.session.commit()
        resp = client.get(f'/courses/{course_id}')
        body = resp.get_data(as_text=True)
        # должны быть отображены только последние 5 — самые свежие (2..6)
        assert 'отзыв-номер-6' in body
        assert 'отзыв-номер-2' in body
        assert 'отзыв-номер-0' not in body
        assert 'отзыв-номер-1' not in body

    def test_show_anonymous_sees_login_invite(self, client, course_id):
        body = client.get(f'/courses/{course_id}').get_data(as_text=True)
        assert 'Чтобы оставить отзыв' in body

    def test_show_authenticated_sees_form(self, auth_client, course_id):
        body = auth_client.get(f'/courses/{course_id}').get_data(as_text=True)
        # есть селект и текстарея для отзыва
        assert 'name="rating"' in body
        assert 'name="text"' in body
        assert 'Оставить отзыв' in body

    def test_show_user_with_review_sees_own_instead_of_form(self, app, auth_client, course_id, user_id):
        with app.app_context():
            db.session.add(Review(course_id=course_id, user_id=user_id, rating=4,
                                  text='мой-эксклюзивный-текст'))
            db.session.commit()
        body = auth_client.get(f'/courses/{course_id}').get_data(as_text=True)
        assert 'мой-эксклюзивный-текст' in body
        # формы быть не должно — кнопка "Оставить отзыв" пропала
        assert 'Оставить отзыв' not in body


# ---------- Route: reviews list ----------

class TestReviewsList:
    def test_reviews_page_renders(self, client, course_id):
        resp = client.get(f'/courses/{course_id}/reviews')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'Отзывы к курсу' in body
        assert 'По новизне' in body
        assert 'Сначала положительные' in body
        assert 'Сначала отрицательные' in body
        assert 'Применить' in body

    def test_pagination_preserves_sort_order(self, app, client, course_id, user_id, petrov_id):
        # 6 отзывов чтобы появилась 2-я страница (per_page=5)
        with app.app_context():
            for i in range(6):
                db.session.add(Review(
                    course_id=course_id,
                    user_id=user_id if i % 2 == 0 else petrov_id,
                    rating=i % 6, text=f'r{i}',
                ))
            db.session.commit()
        body = client.get(f'/courses/{course_id}/reviews?sort=positive').get_data(as_text=True)
        # ссылка на 2-ю страницу должна включать sort=positive
        assert 'sort=positive' in body
        assert 'page=2' in body

    def test_sort_positive_ordering_in_html(self, app, client, course_id, user_id, petrov_id):
        with app.app_context():
            db.session.add_all([
                Review(course_id=course_id, user_id=user_id, rating=0, text='AAA-плохо'),
                Review(course_id=course_id, user_id=petrov_id, rating=5, text='BBB-топ'),
            ])
            db.session.commit()
        body = client.get(f'/courses/{course_id}/reviews?sort=positive').get_data(as_text=True)
        assert body.index('BBB-топ') < body.index('AAA-плохо')

    def test_sort_negative_ordering_in_html(self, app, client, course_id, user_id, petrov_id):
        with app.app_context():
            db.session.add_all([
                Review(course_id=course_id, user_id=user_id, rating=0, text='AAA-плохо'),
                Review(course_id=course_id, user_id=petrov_id, rating=5, text='BBB-топ'),
            ])
            db.session.commit()
        body = client.get(f'/courses/{course_id}/reviews?sort=negative').get_data(as_text=True)
        assert body.index('AAA-плохо') < body.index('BBB-топ')

    def test_invalid_sort_value_falls_back_to_default(self, client, course_id):
        # просто не должно падать
        resp = client.get(f'/courses/{course_id}/reviews?sort=__hack__')
        assert resp.status_code == 200

    def test_404_for_unknown_course(self, client):
        assert client.get('/courses/9999/reviews').status_code == 404


# ---------- Route: create_review ----------

class TestCreateReview:
    def test_anonymous_cannot_create_review(self, client, course_id):
        resp = client.post(f'/courses/{course_id}/reviews/create',
                           data={'rating': '5', 'text': 'hi'})
        # @login_required -> редирект на /auth/login
        assert resp.status_code in (301, 302)
        assert '/auth/login' in resp.headers.get('Location', '')

    def test_authenticated_can_create_review(self, app, auth_client, course_id, user_id):
        resp = auth_client.post(f'/courses/{course_id}/reviews/create',
                                data={'rating': '4', 'text': 'отлично'},
                                follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            r = db.session.execute(db.select(Review)).scalar()
            assert r is not None
            assert r.rating == 4
            assert r.text == 'отлично'
            assert r.user_id == user_id

    def test_create_review_recalculates_course_rating(self, app, auth_client, course_id):
        with app.app_context():
            before = db.session.get(Course, course_id)
            assert before.rating_num == 0
            assert before.rating_sum == 0

        auth_client.post(f'/courses/{course_id}/reviews/create',
                         data={'rating': '4', 'text': 'ok'})

        with app.app_context():
            after = db.session.get(Course, course_id)
            assert after.rating_num == 1
            assert after.rating_sum == 4
            assert after.rating == 4.0

    def test_user_cannot_post_two_reviews(self, app, auth_client, course_id, user_id):
        auth_client.post(f'/courses/{course_id}/reviews/create',
                         data={'rating': '5', 'text': 'first'})
        auth_client.post(f'/courses/{course_id}/reviews/create',
                         data={'rating': '1', 'text': 'second'})
        with app.app_context():
            reviews = db.session.execute(
                db.select(Review).filter_by(user_id=user_id)
            ).scalars().all()
            assert len(reviews) == 1
            assert reviews[0].text == 'first'
            # рейтинг тоже не должен сложиться от второго
            course = db.session.get(Course, course_id)
            assert course.rating_num == 1
            assert course.rating_sum == 5

    @pytest.mark.parametrize('rating,text', [
        ('6', 'хорошо'),     # вне диапазона
        ('-1', 'хорошо'),    # вне диапазона
        ('abc', 'хорошо'),   # не число
        ('5', ''),           # пустой текст
        ('5', '   '),        # только пробелы
    ])
    def test_invalid_input_does_not_create_review(self, app, auth_client, course_id, rating, text):
        auth_client.post(f'/courses/{course_id}/reviews/create',
                         data={'rating': rating, 'text': text})
        with app.app_context():
            assert db.session.execute(db.select(Review)).scalar() is None
            course = db.session.get(Course, course_id)
            assert course.rating_num == 0

    def test_valid_rating_boundaries(self, app, auth_client, course_id):
        # rating=0 и rating=5 должны проходить (граничные значения)
        auth_client.post(f'/courses/{course_id}/reviews/create',
                         data={'rating': '0', 'text': 'ужасно'})
        # второй пользователь — отдельный клиент с собственной сессией
        c2 = app.test_client()
        c2.post('/auth/login', data={'login': 'petrov', 'password': 'qwerty'},
                follow_redirects=True)
        c2.post(f'/courses/{course_id}/reviews/create',
                data={'rating': '5', 'text': 'отлично'})
        with app.app_context():
            ratings = sorted(r.rating for r in db.session.execute(db.select(Review)).scalars())
            assert ratings == [0, 5]


# ---------- Model: Review ----------

class TestReviewModel:
    def test_rating_label_property(self):
        r = Review(rating=5, text='x', course_id=1, user_id=1)
        assert r.rating_label == 'отлично'
        assert Review(rating=0, text='x', course_id=1, user_id=1).rating_label == 'ужасно'
        assert Review(rating=3, text='x', course_id=1, user_id=1).rating_label == 'удовлетворительно'

    def test_review_belongs_to_course_and_user(self, app, course_id, user_id):
        with app.app_context():
            r = Review(course_id=course_id, user_id=user_id, rating=5, text='x')
            db.session.add(r)
            db.session.commit()
            db.session.refresh(r)
            assert r.course.id == course_id
            assert r.user.id == user_id

    def test_course_reviews_backref(self, app, course_id, user_id):
        with app.app_context():
            db.session.add(Review(course_id=course_id, user_id=user_id, rating=4, text='y'))
            db.session.commit()
            course = db.session.get(Course, course_id)
            assert len(course.reviews) == 1
            assert course.reviews[0].text == 'y'
