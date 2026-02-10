import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'nfl-pickem-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'pickem.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ENTRY_FEE = int(os.environ.get('ENTRY_FEE', 30))
    # ESPN API for odds
    ESPN_ODDS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    # The Odds API (free tier) - sign up at https://the-odds-api.com for a key
    ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
    ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
    # WTF CSRF
    WTF_CSRF_ENABLED = False
    # Email settings (optional - if not configured, emails won't be sent)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@pickem.local')
    MAIL_ENABLED = bool(os.environ.get('MAIL_SERVER', ''))
