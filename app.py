from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
from models import db, User, Shop
from werkzeug.security import generate_password_hash
import os

# ========================
# FLASK ILOVASINI YARATISH
# ========================
app = Flask(__name__)
app.config.from_object(Config)

# ========================
# DB VA MIGRATE
# ========================
db.init_app(app)
migrate = Migrate(app, db)

# ========================
# LOGIN MANAGER
# ========================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Iltimos, tizimga kiring!'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ========================
# ROUTELARNI ULASH
# ========================
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.owner import owner_bp
from routes.employee import employee_bp

app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(owner_bp, url_prefix='/owner')
app.register_blueprint(employee_bp, url_prefix='/employee')

# ========================
# SUPER ADMIN YARATISH
# ========================
def create_super_admin():
    with app.app_context():
        existing = User.query.filter_by(role='super_admin').first()
        if not existing:
            from werkzeug.security import generate_password_hash
            admin = User(
                full_name='Super Admin',
                username=app.config['SUPER_ADMIN_USERNAME'],
                password_hash=generate_password_hash(app.config['SUPER_ADMIN_PASSWORD']),
                role='super_admin',
                shop_id=None
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Super Admin yaratildi!")
        else:
            print("ℹ️ Super Admin allaqachon mavjud.")

# ========================
# BAZANI YARATISH
# ========================
with app.app_context():
    db.create_all()
    create_super_admin()

# ========================
# ISHGA TUSHIRISH
# ========================
if __name__ == '__main__':
    app.run(debug=True)