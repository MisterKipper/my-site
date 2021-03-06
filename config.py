import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config():
    SECRET_KEY = os.environ["SECRET_KEY"]
    SSL_REDIRECT = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = os.environ.get("DB_RECORD_QUERIES")
    DB_SLOW_QUERY_TIME = 0.5
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT"))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_SUBJECT_PREFIX = "[Kyle's junk] "
    MAIL_SENDER = os.environ.get("MAIL_SENDER")
    ADMIN_ADDRESS = os.environ.get("ADMIN_ADDRESS")
    POSTS_PER_PAGE = 10
    COMMENTS_PER_PAGE = 10

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    SQLALCHEMY_DATABASE_URI = (os.environ.get("DEV_DATABASE_URL") or
                               "sqlite:///" + os.path.join(basedir, "dev.sqlite"))


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = (os.environ.get("TEST_DATABASE_URL") or "sqlite://")
    WTF_CSRF_ENABLED = False
    SSL_REDIRECT = True


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = ("postgresql+pg8000://{user}:{password}@"
                               "/{database}?unix_sock=/cloudsql/{instance}".format(
                                   user=os.environ.get("CLOUD_SQL_USERNAME"),
                                   password=os.environ.get("CLOUD_SQL_PASSWORD"),
                                   instance=os.environ.get('CLOUD_SQL_INSTANCE_NAME'),
                                   database=os.environ.get("CLOUD_SQL_DATABASE_NAME")))
    SSL_REDIRECT = True

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        import logging
        from logging.handlers import SMTPHandler
        credentials = None
        secure = None
        if getattr(cls, "MAIL_USERNAME", None) is not None:
            credentials = (cls.MAIL_USERNAME, cls.MAIL_PASSWORD)
            if getattr(cls, "MAIL_USE_TLS", None):
                secure = ()
        mail_handler = SMTPHandler(mailhost=(cls.MAIL_SERVER, cls.MAIL_PORT),
                                   fromaddr=cls.MAIL_SENDER,
                                   toaddrs=[cls.ADMIN_ADDRESS],
                                   subject=cls.MAIL_SUBJECT_PREFIX + "Application error",
                                   credentials=credentials,
                                   secure=secure)
        mail_handler.setLevel(logging.ERROR)
        app.logger.addHandler(mail_handler)


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}
