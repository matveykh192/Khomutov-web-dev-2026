from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

from models import User


def check_rights(action):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            target_user = None
            user_id = kwargs.get("id") or kwargs.get("user_id")
            if user_id is not None:
                target_user = User.query.get(user_id)

            if not current_user.is_authenticated or not current_user.can(action, target_user):
                flash("У вас недостаточно прав для доступа к данной странице.")
                return redirect(url_for("index"))

            return view(*args, **kwargs)

        return wrapper

    return decorator
