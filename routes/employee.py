from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Shop, Debtor, Transaction, AuditLog
from datetime import datetime

employee_bp = Blueprint('employee', __name__)

# ========================
# EMPLOYEE DEKORATOR
# ========================
def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['employee', 'owner']:
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
# DASHBOARD
# ========================
@employee_bp.route('/')
@login_required
@employee_required
def dashboard():
    shop = Shop.query.get(current_user.shop_id)
    debtors = Debtor.query.filter_by(
        shop_id=current_user.shop_id).order_by(
        Debtor.total_debt.desc()).all()

    total_debt = sum(d.total_debt for d in debtors)

    # Bugungi o'z tranzaksiyalari
    today = datetime.utcnow().date()
    my_today = Transaction.query.filter_by(
        user_id=current_user.id).filter(
        db.func.date(Transaction.created_at) == today).all()

    today_added = sum(t.amount for t in my_today if t.action_type == 'add')
    today_paid = sum(t.amount for t in my_today if t.action_type == 'pay')

    return render_template('employee/dashboard.html',
                           shop=shop,
                           debtors=debtors,
                           total_debt=total_debt,
                           today_added=today_added,
                           today_paid=today_paid)

# ========================
# MIJOZLAR RO'YXATI
# ========================
@employee_bp.route('/debtors')
@login_required
@employee_required
def debtors():
    search = request.args.get('search', '').strip()

    query = Debtor.query.filter_by(shop_id=current_user.shop_id)

    if search:
        query = query.filter(
            db.or_(
                Debtor.full_name.ilike(f'%{search}%'),
                Debtor.phone.ilike(f'%{search}%')
            )
        )

    debtors_list = query.order_by(Debtor.total_debt.desc()).all()
    return render_template('employee/debtors.html',
                           debtors=debtors_list, search=search)

# ========================
# MIJOZ QO'SHISH
# ========================
@employee_bp.route('/debtors/add', methods=['GET', 'POST'])
@login_required
@employee_required
def add_debtor():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        notes = request.form.get('notes', '').strip()

        if not full_name or not phone:
            flash('Ism va telefon raqam majburiy!', 'danger')
            return render_template('employee/add_debtor.html')

        new_debtor = Debtor(
            shop_id=current_user.shop_id,
            full_name=full_name,
            phone=phone,
            notes=notes
        )
        db.session.add(new_debtor)
        db.session.flush()

        write_log('Mijoz qo\'shildi',
                  f'{full_name} ({phone}) mijozlar bazasiga qo\'shildi.')
        db.session.commit()

        flash(f'✅ {full_name} muvaffaqiyatli qo\'shildi!', 'success')
        return redirect(url_for('employee.debtors'))

    return render_template('employee/add_debtor.html')

# ========================
# MIJOZ PROFILI
# ========================
@employee_bp.route('/debtors/<int:debtor_id>')
@login_required
@employee_required
def debtor_profile(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id,
        shop_id=current_user.shop_id).first_or_404()
    transactions = Transaction.query.filter_by(
        debtor_id=debtor_id).order_by(
        Transaction.created_at.desc()).all()
    return render_template('employee/debtor_profile.html',
                           debtor=debtor,
                           transactions=transactions)

# ========================
# QARZ QO'SHISH
# ========================
@employee_bp.route('/debtors/<int:debtor_id>/add-debt', methods=['POST'])
@login_required
@employee_required
def add_debt(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id,
        shop_id=current_user.shop_id).first_or_404()

    if debtor.is_frozen:
        flash('❌ Bu mijoz muzlatilgan! Qarz berib bo\'lmaydi.', 'danger')
        return redirect(url_for('employee.debtor_profile',
                                debtor_id=debtor_id))

    amount = float(request.form.get('amount', 0))
    comment = request.form.get('comment', '').strip()
    items = request.form.get('items', '').strip()
    due_date_str = request.form.get('due_date', '').strip()

    # Limit tekshiruvi
    if debtor.total_debt + amount > debtor.debt_limit:
        flash(f'❌ Qarz limiti ({debtor.debt_limit:,.0f} so\'m) oshib ketdi!',
              'danger')
        return redirect(url_for('employee.debtor_profile',
                                debtor_id=debtor_id))

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
              f'{debtor.full_name}ga {amount:,.0f} so\'m qarz yozildi. '
              f'Izoh: {comment}')
    db.session.commit()

    flash(f'✅ {amount:,.0f} so\'m qarz yozildi!', 'success')
    return redirect(url_for('employee.debtor_profile', debtor_id=debtor_id))

# ========================
# QARZ KAMAYTIRISH (TO'LOV)
# ========================
@employee_bp.route('/debtors/<int:debtor_id>/pay-debt', methods=['POST'])
@login_required
@employee_required
def pay_debt(debtor_id):
    debtor = Debtor.query.filter_by(
        id=debtor_id,
        shop_id=current_user.shop_id).first_or_404()

    amount = float(request.form.get('amount', 0))
    comment = request.form.get('comment', 'Qarz qaytarildi').strip()

    if amount > debtor.total_debt:
        flash('❌ To\'lov miqdori qarz miqdoridan ko\'p!', 'danger')
        return redirect(url_for('employee.debtor_profile',
                                debtor_id=debtor_id))

    transaction = Transaction(
        debtor_id=debtor_id,
        user_id=current_user.id,
        amount=amount,
        action_type='pay',
        comment=comment
    )
    debtor.total_debt -= amount

    db.session.add(transaction)
    write_log('Qarz to\'landi',
              f'{debtor.full_name} {amount:,.0f} so\'m to\'ladi. '
              f'Qolgan qarz: {debtor.total_debt:,.0f} so\'m')
    db.session.commit()

    flash(f'✅ {amount:,.0f} so\'m qabul qilindi!', 'success')
    return redirect(url_for('employee.debtor_profile', debtor_id=debtor_id))

# ========================
# LIVE QIDIRUV (AJAX)
# ========================
@employee_bp.route('/search')
@login_required
@employee_required
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])

    results = Debtor.query.filter_by(
        shop_id=current_user.shop_id).filter(
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
        'is_frozen': d.is_frozen
    } for d in results]

    return jsonify(data)