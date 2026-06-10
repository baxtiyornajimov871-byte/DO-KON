from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Shop, Debtor, Transaction, AuditLog
from datetime import datetime
import os
import json

owner_bp = Blueprint('owner', __name__)

# ========================
# OWNER DEKORATOR
# ========================
def owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'owner':
            flash('Bu sahifaga kirishga ruxsatingiz yo\'q!', 'danger')
            return redirect(url_for('auth.login'))
        shop = Shop.query.get(current_user.shop_id)
        if shop.status != 'active':
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ========================
# LOG YOZISH YORDAMCHI
# ========================
def write_log(action, details):
    log = AuditLog(
        shop_id=current_user.shop_id,
        user_id=current_user.id,
        action=action,
        details=details
    )
    db.session.add(log)

# ========================
# RASM YUKLASH YORDAMCHI
# ========================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ========================
# DASHBOARD
# ========================
@owner_bp.route('/')
@login_required
@owner_required
def dashboard():
    shop = Shop.query.get(current_user.shop_id)
    debtors = Debtor.query.filter_by(shop_id=current_user.shop_id).all()
    
    total_debt = sum(d.total_debt for d in debtors)
    frozen_count = sum(1 for d in debtors if d.is_frozen)
    
    # Bugungi tranzaksiyalar
    today = datetime.utcnow().date()
    today_transactions = Transaction.query.join(Debtor).filter(
        Debtor.shop_id == current_user.shop_id,
        db.func.date(Transaction.created_at) == today
    ).all()
    
    today_added = sum(t.amount for t in today_transactions if t.action_type == 'add')
    today_paid = sum(t.amount for t in today_transactions if t.action_type == 'pay')
    
    # Xavfli qarzdorlar (limiti tugab kelganlar)
    danger_debtors = [d for d in debtors if d.total_debt >= d.debt_limit * 0.8]
    
    return render_template('owner/dashboard.html',
                           shop=shop,
                           debtors=debtors,
                           total_debt=total_debt,
                           frozen_count=frozen_count,
                           today_added=today_added,
                           today_paid=today_paid,
                           danger_debtors=danger_debtors)

# ========================
# MIJOZLAR RO'YXATI
# ========================
@owner_bp.route('/debtors')
@login_required
@owner_required
def debtors():
    search = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')
    
    query = Debtor.query.filter_by(shop_id=current_user.shop_id)
    
    if search:
        query = query.filter(
            db.or_(
                Debtor.full_name.ilike(f'%{search}%'),
                Debtor.phone.ilike(f'%{search}%')
            )
        )
    
    if filter_type == 'frozen':
        query = query.filter_by(is_frozen=True)
    elif filter_type == 'danger':
        query = query.filter(Debtor.total_debt >= 1000000)
    elif filter_type == 'good':
        query = query.filter_by(trust_score='good')
    
    debtors_list = query.order_by(Debtor.total_debt.desc()).all()
    return render_template('owner/debtors.html', debtors=debtors_list,
                           search=search, filter_type=filter_type)

# ========================
# MIJOZ QO'SHISH
# ========================
@owner_bp.route('/debtors/add', methods=['GET', 'POST'])
@login_required
@owner_required
def add_debtor():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        debt_limit = request.form.get('debt_limit', 5000000)
        notes = request.form.get('notes', '').strip()
        
        if not full_name or not phone:
            flash('Ism va telefon raqam majburiy!', 'danger')
            return render_template('owner/add_debtor.html')
        
        # Rasm yuklash
        avatar_filename = None
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_name = f"{current_user.shop_id}_{datetime.utcnow().timestamp()}_{filename}"
                file.save(os.path.join('static/uploads', unique_name))
                avatar_filename = unique_name
        
        new_debtor = Debtor(
            shop_id=current_user.shop_id,
            full_name=full_name,
            phone=phone,
            debt_limit=float(debt_limit),
            notes=notes,
            avatar=avatar_filename
        )
        db.session.add(new_debtor)
        db.session.flush()
        
        write_log('Mijoz qo\'shildi', f'{full_name} ({phone}) mijozlar bazasiga qo\'shildi.')
        db.session.commit()
        
        flash(f'✅ {full_name} muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('owner.debtors'))
    
    return render_template('owner/add_debtor.html')

# ========================
# MIJOZ PROFILI
# ========================
@owner_bp.route('/debtors/<int:debtor_id>')
@login_required
@owner_required
def debtor_profile(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id, shop_id=current_user.shop_id).first_or_404()
    transactions = Transaction.query.filter_by(
        debtor_id=debtor_id).order_by(Transaction.created_at.desc()).all()
    return render_template('owner/debtor_profile.html',
                           debtor=debtor, transactions=transactions)

# ========================
# QARZ QO'SHISH
# ========================
@owner_bp.route('/debtors/<int:debtor_id>/add-debt', methods=['POST'])
@login_required
@owner_required
def add_debt(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id, shop_id=current_user.shop_id).first_or_404()
    
    if debtor.is_frozen:
        flash('❌ Bu mijoz muzlatilgan! Qarz berib bo\'lmaydi.', 'danger')
        return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))
    
    amount = float(request.form.get('amount', 0))
    comment = request.form.get('comment', '').strip()
    items = request.form.get('items', '').strip()
    due_date_str = request.form.get('due_date', '').strip()
    
    # Limit tekshiruvi
    if debtor.total_debt + amount > debtor.debt_limit:
        flash(f'❌ Qarz limiti ({debtor.debt_limit:,.0f} so\'m) oshib ketdi!', 'danger')
        return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))
    
    due_date = None
    if due_date_str:
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
    
    transaction = Transaction(
        debtor_id=debtor_id,
        user_id=current_user.id,
        amount=amount,
        action_type='add',
        items=items,
        comment=comment,
        due_date=due_date
    )
    debtor.total_debt += amount
    
    db.session.add(transaction)
    write_log('Qarz qo\'shildi',
              f'{debtor.full_name}ga {amount:,.0f} so\'m qarz yozildi. Izoh: {comment}')
    db.session.commit()
    
    flash(f'✅ {amount:,.0f} so\'m qarz yozildi!', 'success')
    return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))

# ========================
# QARZ KAMAYTIRISH (TO'LOV)
# ========================
@owner_bp.route('/debtors/<int:debtor_id>/pay-debt', methods=['POST'])
@login_required
@owner_required
def pay_debt(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id, shop_id=current_user.shop_id).first_or_404()
    
    amount = float(request.form.get('amount', 0))
    comment = request.form.get('comment', 'Qarz qaytarildi').strip()
    
    if amount > debtor.total_debt:
        flash('❌ To\'lov miqdori qarz miqdoridan ko\'p!', 'danger')
        return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))
    
    transaction = Transaction(
        debtor_id=debtor_id,
        user_id=current_user.id,
        amount=amount,
        action_type='pay',
        comment=comment
    )
    debtor.total_debt -= amount
    
    # Trust score yangilash
    if debtor.total_debt == 0:
        debtor.trust_score = 'good'
    
    db.session.add(transaction)
    write_log('Qarz to\'landi',
              f'{debtor.full_name} {amount:,.0f} so\'m to\'ladi. Qolgan qarz: {debtor.total_debt:,.0f} so\'m')
    db.session.commit()
    
    flash(f'✅ {amount:,.0f} so\'m qabul qilindi!', 'success')
    return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))

# ========================
# MIJOZNI MUZLATISH/OCHISH
# ========================
@owner_bp.route('/debtors/<int:debtor_id>/freeze', methods=['POST'])
@login_required
@owner_required
def freeze_debtor(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id, shop_id=current_user.shop_id).first_or_404()
    
    debtor.is_frozen = not debtor.is_frozen
    status = 'muzlatildi' if debtor.is_frozen else 'ochildi'
    
    write_log(f'Mijoz {status}',
              f'{debtor.full_name} profili {status}.')
    db.session.commit()
    
    flash(f'✅ {debtor.full_name} profili {status}!', 'success')
    return redirect(url_for('owner.debtor_profile', debtor_id=debtor_id))

# ========================
# MIJOZNI O'CHIRISH
# ========================
@owner_bp.route('/debtors/<int:debtor_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_debtor(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id, shop_id=current_user.shop_id).first_or_404()
    
    name = debtor.full_name
    write_log('Mijoz o\'chirildi', f'{name} bazadan o\'chirildi.')
    db.session.delete(debtor)
    db.session.commit()
    
    flash(f'🗑️ {name} bazadan o\'chirildi!', 'info')
    return redirect(url_for('owner.debtors'))

# ========================
# ISHCHILAR RO'YXATI
# ========================
@owner_bp.route('/employees')
@login_required
@owner_required
def employees():
    workers = User.query.filter_by(
        shop_id=current_user.shop_id, role='employee').all()
    return render_template('owner/employees.html', workers=workers)

# ========================
# ISHCHI QO'SHISH
# ========================
@owner_bp.route('/employees/add', methods=['GET', 'POST'])
@login_required
@owner_required
def add_employee():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not all([full_name, username, password]):
            flash('Barcha maydonlarni to\'ldiring!', 'danger')
            return render_template('owner/add_employee.html')
        
        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Bu username allaqachon band!', 'danger')
            return render_template('owner/add_employee.html')
        
        new_employee = User(
            shop_id=current_user.shop_id,
            full_name=full_name,
            username=username,
            password_hash=generate_password_hash(password),
            role='employee'
        )
        db.session.add(new_employee)
        write_log('Ishchi qo\'shildi', f'{full_name} (@{username}) ishchi sifatida qo\'shildi.')
        db.session.commit()
        
        flash(f'✅ {full_name} ishchi sifatida qo\'shildi!', 'success')
        return redirect(url_for('owner.employees'))
    
    return render_template('owner/add_employee.html')

# ========================
# ISHCHINI O'CHIRISH
# ========================
@owner_bp.route('/employees/<int:user_id>/delete', methods=['POST'])
@login_required
@owner_required
def delete_employee(user_id):
    employee = User.query.filter_by(
        id=user_id, shop_id=current_user.shop_id, role='employee').first_or_404()
    
    name = employee.full_name
    db.session.delete(employee)
    write_log('Ishchi o\'chirildi', f'{name} ishchilar ro\'yxatidan o\'chirildi.')
    db.session.commit()
    
    flash(f'🗑️ {name} o\'chirildi!', 'info')
    return redirect(url_for('owner.employees'))

# ========================
# AUDIT LOGLAR
# ========================
@owner_bp.route('/audit-logs')
@login_required
@owner_required
def audit_logs():
    logs = AuditLog.query.filter_by(
        shop_id=current_user.shop_id
    ).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('owner/audit_logs.html', logs=logs)

# ========================
# LIVE QIDIRUV (AJAX)
# ========================
@owner_bp.route('/search')
@login_required
@owner_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    
    results = Debtor.query.filter_by(shop_id=current_user.shop_id).filter(
        db.or_(
            Debtor.full_name.ilike(f'%{q}%'),
            Debtor.phone.ilike(f'%{q}%')
        )
    ).limit(10).all()
    
    data = [{
        'id': d.id,
        'full_name': d.full_name,
        'phone': d.phone,
        'total_debt': d.total_debt,
        'is_frozen': d.is_frozen,
        'trust_score': d.trust_score
    } for d in results]
    
    return jsonify(data)