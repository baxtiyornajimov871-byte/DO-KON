from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Shop

auth_bp = Blueprint('auth', __name__)

# ========================
# BOSH SAHIFA
# ========================
@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))

# ========================
# LOGIN
# ========================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            flash('Login yoki parol noto\'g\'ri!', 'danger')
            return render_template('auth/login.html')
        
        if not user.is_active:
            flash('Akkauntingiz bloklangan!', 'danger')
            return render_template('auth/login.html')
        
        login_user(user)
        return redirect(url_for('auth.dashboard'))
    
    return render_template('auth/login.html')

# ========================
# RO'YXATDAN O'TISH
# ========================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        shop_name = request.form.get('shop_name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Tekshiruvlar
        if not all([full_name, phone, shop_name, username, password]):
            flash('Barcha maydonlarni to\'ldiring!', 'danger')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Parollar mos kelmadi!', 'danger')
            return render_template('auth/register.html')
        
        if len(password) < 6:
            flash('Parol kamida 6 ta belgidan iborat bo\'lishi kerak!', 'danger')
            return render_template('auth/register.html')
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Bu username allaqachon band!', 'danger')
            return render_template('auth/register.html')
        
        # Do'kon yaratish (status=pending)
        new_shop = Shop(
            name=shop_name,
            owner_name=full_name,
            phone=phone,
            status='pending'
        )
        db.session.add(new_shop)
        db.session.flush()  # ID olish uchun
        
        # Owner yaratish
        new_user = User(
            shop_id=new_shop.id,
            full_name=full_name,
            username=username,
            password_hash=generate_password_hash(password),
            role='owner'
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Ariza yuborildi! Super Admin tasdiqlashini kuting.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

# ========================
# DASHBOARD (YO'NALTIRUVCHI)
# ========================
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'super_admin':
        return redirect(url_for('admin.panel'))
    
    elif current_user.role == 'owner':
        shop = Shop.query.get(current_user.shop_id)
        if shop.status == 'pending':
            return render_template('auth/pending.html', shop=shop)
        elif shop.status == 'rejected':
            return render_template('auth/rejected.html', shop=shop)
        else:
            return redirect(url_for('owner.dashboard'))
    
    elif current_user.role == 'employee':
        shop = Shop.query.get(current_user.shop_id)
        if shop.status != 'active':
            return render_template('auth/pending.html', shop=shop)
        return redirect(url_for('employee.dashboard'))

# ========================
# LOGOUT
# ========================
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Tizimdan chiqdingiz!', 'info')
    return redirect(url_for('auth.login'))