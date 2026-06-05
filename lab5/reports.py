import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, Response, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from models import db, VisitLog, User
from auth import check_rights


bp = Blueprint("reports", __name__, url_prefix="/visits")


PER_PAGE = 10


@bp.route("/")
@login_required
def index():
    """Главная страница журнала посещений.

    Админ видит все записи, обычный пользователь -- только свои.
    """
    page = request.args.get("page", 1, type=int)

    q = VisitLog.query.order_by(VisitLog.created_at.desc())
    if not current_user.is_admin:
        q = q.filter(VisitLog.user_id == current_user.id)

    pagination = q.paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("reports/index.html", pagination=pagination)


@bp.route("/by-pages")
@check_rights("view_all_logs")
def by_pages():
    rows = (
        db.session.query(VisitLog.path, func.count(VisitLog.id).label("cnt"))
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )
    return render_template("reports/by_pages.html", rows=rows)


@bp.route("/by-pages/export")
@check_rights("view_all_logs")
def by_pages_export():
    rows = (
        db.session.query(VisitLog.path, func.count(VisitLog.id).label("cnt"))
        .group_by(VisitLog.path)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )

    buf = io.StringIO()
    buf.write("\ufeff")  # BOM, чтобы Excel корректно открывал кириллицу
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["№", "Страница", "Количество посещений"])
    for i, (path, cnt) in enumerate(rows, start=1):
        writer.writerow([i, path, cnt])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=by_pages.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


@bp.route("/by-users")
@check_rights("view_all_logs")
def by_users():
    rows = (
        db.session.query(VisitLog.user_id, func.count(VisitLog.id).label("cnt"))
        .group_by(VisitLog.user_id)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )

    # подтянем пользователей
    user_ids = [r[0] for r in rows if r[0] is not None]
    users_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    items = []
    for user_id, cnt in rows:
        if user_id is None:
            name = "Неаутентифицированный пользователь"
        else:
            user = users_map.get(user_id)
            name = user.full_name if user else f"Пользователь #{user_id}"
        items.append((name, cnt))

    return render_template("reports/by_users.html", items=items)


@bp.route("/by-users/export")
@check_rights("view_all_logs")
def by_users_export():
    rows = (
        db.session.query(VisitLog.user_id, func.count(VisitLog.id).label("cnt"))
        .group_by(VisitLog.user_id)
        .order_by(func.count(VisitLog.id).desc())
        .all()
    )

    user_ids = [r[0] for r in rows if r[0] is not None]
    users_map = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, delimiter=",", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["№", "Пользователь", "Количество посещений"])
    for i, (user_id, cnt) in enumerate(rows, start=1):
        if user_id is None:
            name = "Неаутентифицированный пользователь"
        else:
            user = users_map.get(user_id)
            name = user.full_name if user else f"Пользователь #{user_id}"
        writer.writerow([i, name, cnt])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=by_users.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )
