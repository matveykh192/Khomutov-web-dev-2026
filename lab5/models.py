from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class Role(db.Model):
    __tablename__ = "role"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(255))


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    login = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    last_name = db.Column(db.String(100))
    first_name = db.Column(db.String(100), nullable=False)
    middle_name = db.Column(db.String(100))

    role_id = db.Column(db.Integer, db.ForeignKey("role.id"))
    role = db.relationship("Role")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- helpers ----

    @property
    def full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p)

    @property
    def is_admin(self):
        return self.role is not None and self.role.name == "Admin"

    @property
    def is_user(self):
        return self.role is not None and self.role.name == "User"

    def can(self, action, target_user=None):
        if not self.is_authenticated:
            return False

        if self.is_admin:
            return True

        if action == "edit":
            return target_user is not None and target_user.id == self.id
        if action == "show":
            return target_user is not None and target_user.id == self.id

        # create, delete, view_all_logs -- только админ
        return False


class VisitLog(db.Model):
    __tablename__ = "visit_logs"

    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")
