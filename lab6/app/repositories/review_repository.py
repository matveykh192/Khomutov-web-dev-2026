from sqlalchemy import desc, asc
from app.models import Review, Course


class ReviewRepository:
    SORT_NEWEST = 'newest'
    SORT_POSITIVE = 'positive'
    SORT_NEGATIVE = 'negative'

    SORT_OPTIONS = [
        (SORT_NEWEST, 'По новизне'),
        (SORT_POSITIVE, 'Сначала положительные'),
        (SORT_NEGATIVE, 'Сначала отрицательные'),
    ]

    def __init__(self, db):
        self.db = db

    def _sorted_query(self, course_id, sort_order=SORT_NEWEST):
        query = self.db.select(Review).filter(Review.course_id == course_id)
        if sort_order == self.SORT_POSITIVE:
            query = query.order_by(desc(Review.rating), desc(Review.created_at))
        elif sort_order == self.SORT_NEGATIVE:
            query = query.order_by(asc(Review.rating), desc(Review.created_at))
        else:
            query = query.order_by(desc(Review.created_at))
        return query

    def get_latest_reviews(self, course_id, limit=5):
        query = (
            self.db.select(Review)
            .filter(Review.course_id == course_id)
            .order_by(desc(Review.created_at))
            .limit(limit)
        )
        return self.db.session.execute(query).scalars().all()

    def get_pagination_info(self, course_id, sort_order=SORT_NEWEST, per_page=5):
        query = self._sorted_query(course_id, sort_order)
        return self.db.paginate(query, per_page=per_page)

    def get_user_review(self, course_id, user_id):
        if user_id is None:
            return None
        query = self.db.select(Review).filter(
            Review.course_id == course_id,
            Review.user_id == user_id
        )
        return self.db.session.execute(query).scalar()

    def add_review(self, course_id, user_id, rating, text):
        review = Review(
            course_id=course_id,
            user_id=user_id,
            rating=rating,
            text=text,
        )
        try:
            self.db.session.add(review)
            # пересчёт рейтинга курса
            course = self.db.session.get(Course, course_id)
            if course is not None:
                course.rating_sum = (course.rating_sum or 0) + rating
                course.rating_num = (course.rating_num or 0) + 1
            self.db.session.commit()
        except Exception as e:
            self.db.session.rollback()
            raise e
        return review
