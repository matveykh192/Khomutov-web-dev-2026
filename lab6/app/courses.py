from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.models import db, Review
from app.repositories import (
    CourseRepository, UserRepository, CategoryRepository,
    ImageRepository, ReviewRepository
)

user_repository = UserRepository(db)
course_repository = CourseRepository(db)
category_repository = CategoryRepository(db)
image_repository = ImageRepository(db)
review_repository = ReviewRepository(db)

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

VALID_RATINGS = {0, 1, 2, 3, 4, 5}


def params():
    return {p: request.form.get(p) or None for p in COURSE_PARAMS}


def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }


@bp.route('/')
def index():
    pagination = course_repository.get_pagination_info(**search_params())
    courses = course_repository.get_all_courses(pagination=pagination)
    categories = category_repository.get_all_categories()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())


@bp.route('/new')
@login_required
def new():
    course = course_repository.new_course()
    categories = category_repository.get_all_categories()
    users = user_repository.get_all_users()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users,
                           course=course)


@bp.route('/create', methods=['POST'])
@login_required
def create():
    f = request.files.get('background_img')
    img = None
    course = None

    try:
        if f and f.filename:
            img = image_repository.add_image(f)

        image_id = img.id if img else None
        course = course_repository.add_course(**params(), background_image_id=image_id)
    except IntegrityError as err:
        flash(f'Возникла ошибка при записи данных в БД. Проверьте корректность введённых данных. ({err})', 'danger')
        categories = category_repository.get_all_categories()
        users = user_repository.get_all_users()
        return render_template('courses/new.html',
                               categories=categories,
                               users=users,
                               course=course)

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))


@bp.route('/<int:course_id>')
def show(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    latest_reviews = review_repository.get_latest_reviews(course_id, limit=5)
    user_review = None
    if current_user.is_authenticated:
        user_review = review_repository.get_user_review(course_id, current_user.id)

    return render_template(
        'courses/show.html',
        course=course,
        latest_reviews=latest_reviews,
        user_review=user_review,
        rating_labels=Review.RATING_LABELS,
    )


@bp.route('/<int:course_id>/reviews')
def reviews(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    sort_order = request.args.get('sort', ReviewRepository.SORT_NEWEST)
    if sort_order not in dict(ReviewRepository.SORT_OPTIONS):
        sort_order = ReviewRepository.SORT_NEWEST

    pagination = review_repository.get_pagination_info(course_id, sort_order=sort_order, per_page=5)

    user_review = None
    if current_user.is_authenticated:
        user_review = review_repository.get_user_review(course_id, current_user.id)

    return render_template(
        'courses/reviews.html',
        course=course,
        pagination=pagination,
        reviews=pagination.items,
        sort_order=sort_order,
        sort_options=ReviewRepository.SORT_OPTIONS,
        user_review=user_review,
        rating_labels=Review.RATING_LABELS,
    )


@bp.route('/<int:course_id>/reviews/create', methods=['POST'])
@login_required
def create_review(course_id):
    course = course_repository.get_course_by_id(course_id)
    if course is None:
        abort(404)

    # уже оставлял? — нельзя повторно
    existing = review_repository.get_user_review(course_id, current_user.id)
    if existing is not None:
        flash('Вы уже оставили отзыв к этому курсу.', 'warning')
        return redirect(url_for('courses.show', course_id=course_id))

    try:
        rating = int(request.form.get('rating', '5'))
    except (TypeError, ValueError):
        rating = -1
    text = (request.form.get('text') or '').strip()

    if rating not in VALID_RATINGS or not text:
        flash('Проверьте корректность введённых данных: оценка должна быть от 0 до 5, текст не должен быть пустым.', 'danger')
        return redirect(url_for('courses.show', course_id=course_id))

    review_repository.add_review(
        course_id=course_id,
        user_id=current_user.id,
        rating=rating,
        text=text,
    )
    flash('Спасибо! Ваш отзыв сохранён.', 'success')
    return redirect(url_for('courses.show', course_id=course_id))
