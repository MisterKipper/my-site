import re
from datetime import datetime
from hashlib import md5

import bleach
from flask import current_app, url_for
from flask_login import AnonymousUserMixin, UserMixin
from itsdangerous import BadData, TimedJSONWebSignatureSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login
from app.exceptions import ValidationError


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(254), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    role_id = db.Column(db.Integer, db.ForeignKey("role.id"))
    active = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    posts = db.relationship("Post", backref="author", lazy="dynamic")
    comments = db.relationship("Comment", backref="author", lazy="dynamic")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config["ADMIN_ADDRESS"]:
                self.role = Role.query.filter_by(name="admin").first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()

    @property
    def password(self):
        raise AttributeError("Password is not stored.")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_activation_token(self, expiration=3600):
        s = TimedJSONWebSignatureSerializer(current_app.config["SECRET_KEY"], expiration)
        return s.dumps({"confirm": self.id}).decode("utf-8")

    def activate(self, token):
        s = TimedJSONWebSignatureSerializer(current_app.config["SECRET_KEY"])
        try:
            data = s.loads(token.encode("utf-8"))
        except BadData:
            return False
        if data.get("confirm") != self.id:
            return False
        self.active = True
        db.session.add(self)
        return True

    def generate_auth_token(self, expiration):
        s = TimedJSONWebSignatureSerializer(current_app.config["SECRET_KEY"], expires_in=expiration)
        return s.dumps({"id": self.id}).decode("utf-8")

    @staticmethod
    def verify_auth_token(token):
        s = TimedJSONWebSignatureSerializer(current_app.config["SECRET_KEY"])
        try:
            data = s.loads(token)
        except BadData:
            return None
        return User.query.get(data["id"])

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def can(self, perm):
        return self.role and self.role.has_permission(perm)

    def is_admin(self):
        return self.can(Permission.ADMIN)

    def seen(self):
        self._last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def to_dict(self):
        user = {
            "url": url_for("api.get_user", id=self.id),
            "username": self.username,
            "member_since": self.member_since,
            "last_seen": self.last_seen,
            "posts_url": url_for("api.get_user_posts", id=self.id),
            "post_count": self.posts.count()
        }
        return user

    def __repr__(self):
        return f"<User {self.username}>"


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_admin(self):
        return False


class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(16), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship("User", backref="role", lazy="dynamic")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.permissions:
            self.permissions = 0

    def add_permission(self, perm):
        if not self.has_permission(perm):
            self.permissions += perm

    def remove_permission(self, perm):
        if self.has_permission(perm):
            self.permissions -= perm

    def reset_permissions(self):
        self.permissions = 0

    def has_permission(self, perm):
        return self.permissions & perm == perm

    @staticmethod
    def insert_roles():
        roles = {
            "user": [Permission.FOLLOW, Permission.COMMENT],
            "moderator": [Permission.FOLLOW, Permission.COMMENT, Permission.MODERATE],
            "admin": [
                Permission.FOLLOW, Permission.COMMENT, Permission.WRITE, Permission.MODERATE,
                Permission.ADMIN
            ],
        }
        default_role = "user"
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.reset_permissions()
            for perm in roles[r]:
                role.add_permission(perm)
            role.default = role.name == default_role
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission:
    FOLLOW = 1
    COMMENT = 2
    WRITE = 4
    MODERATE = 8
    ADMIN = 16


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    slug = db.Column(db.Text, index=True, unique=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.Text)
    summary = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    comments = db.relationship("Comment", backref="post", lazy="dynamic")

    def __repr__(self):
        return f"<Post {self.author_id}, {self.timestamp}>"


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    disabled = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    edit_time = db.Column(db.DateTime)
    parent_id = db.Column(db.Integer, db.ForeignKey("comment.id"), index=True)
    parent = db.relationship("Comment", remote_side=id, backref="children")

    @staticmethod
    def on_change_body(target, value, oldvalue, initiator):
        if not target.edit_time:
            target.edit_time = datetime.utcnow()
        r = re.compile(r"\n+")
        target.body_html = "<p>" + bleach.linkify(
            r.sub("</p><p>", bleach.clean(value.strip(), tags=[]))) + "</p>"

    def __repr__(self):
        return f"<Comment {self.id}>"


class Demo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text)
    slug = db.Column(db.Text, index=True)
    summary = db.Column(db.Text)
    body = db.Column(db.Text)
    thumbnail_id = db.Column(db.Integer, db.ForeignKey("image.id"))

    def __repr__(self):
        return f"<Demo {self.slug}>"


class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.Text, index=True, unique=True)
    data = db.Column(db.Binary)
    alt_text = db.Column(db.Text)
    thumbnail_for = db.relationship("Demo", backref="thumbnail", lazy="dynamic")

    def __repr__(self):
        return f"<Image {self.filename}>"


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


login.anonymous_user = AnonymousUser

db.event.listen(Comment.body, "set", Comment.on_change_body)
