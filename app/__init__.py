commit 4320ced583a63199d84af3c13c0e986667ba80a8
Author: Rajiv Mordani <rajiv.mordani@broadcom.com>
Date:   Sat Feb 7 14:55:20 2026 -0800

    Restore correct __init__.py
    
    Co-authored-by: Cursor <cursoragent@cursor.com>

diff --git a/app/__init__.py b/app/__init__.py
index b99acde..4901571 100644
--- a/app/__init__.py
+++ b/app/__init__.py
@@ -12,34 +12,27 @@ login_manager.login_message_category = 'info'
 def create_app(config_class=Config):
     app = Flask(__name__)
     app.config.from_object(config_class)
+
     db.init_app(app)
     login_manager.init_app(app)
 
-    from app.models import User
-
-    @login_manager.user_loader
-    def load_user(user_id):
-        return User.query.get(int(user_id))
-
     from app.routes.auth import auth_bp
-    from app.routes.main import main_bp
     from app.routes.admin import admin_bp
     from app.routes.picks import picks_bp
     from app.routes.standings import standings_bp
 
     app.register_blueprint(auth_bp)
-    app.register_blueprint(main_bp)
     app.register_blueprint(admin_bp, url_prefix='/admin')
     app.register_blueprint(picks_bp, url_prefix='/picks')
     app.register_blueprint(standings_bp, url_prefix='/standings')
 
     with app.app_context():
+        from app.models import User
         db.create_all()
-        admin = User.query.filter_by(is_admin=True).first()
-        if not admin:
-            admin = User(username='admin', email='admin@pickem.local',
-                         display_name='Administrator', is_admin=True)
-            admin.set_password('admin123')
+
+        if not User.query.filter_by(is_admin=True).first():
+            admin = User(username='admin', email='admin@pickem.local', is_admin=True)
+            admin.set_password('admin')
             db.session.add(admin)
             db.session.commit()
 
