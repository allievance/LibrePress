import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///librepress.db'
    SQLALCHEMY_TRACK_NOTIFICATIONS = False

    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')

    MAIL_SERVER = 'smtp-relay.brevo.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv('BREVO_SMTP_LOGIN')
    MAIL_PASSWORD = os.getenv('BREVO_SMTP_KEY')
    MAIL_DEFAULT_SENDER = ('Librepress', 'info@librepress.us')

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

    LULU_CLIENT_KEY = os.getenv('LULU_CLIENT_KEY')
    LULU_CLIENT_SECRET = os.getenv('LULU_CLIENT_SECRET')

    RESEED_KEY = os.getenv('RESEED_KEY')
    POD_PACKAGE_ID = '0583X0827BWSTDPB060UC444MXX'