from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    login_manager.init_app(app)
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.picks import picks_bp
    from app.routes.standings import standings_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(picks_bp, url_prefix='/picks')
    app.register_blueprint(standings_bp, url_prefix='/standings')
    with app.app_context():
        from app.models import User
        db.create_all()
        if not User.query.filter_by(is_admin=True).first():
            admin = User(username='admin', email='admin@pickem.local', is_admin=True)
            admin.set_password('admin')
            db.session.add(admin)
            db.session.commit()
    return app
