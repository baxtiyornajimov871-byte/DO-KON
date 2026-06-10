from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Shop, AuditLog

admin_bp = Blueprint('admin', __name__)

# ========================
# SUPER ADMIN DEKORATOR
# ========================
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            flash('Bu sahifaga kirishga ruxsatingiz yo\'q!', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# ========================
# ADMIN PANEL (BOSH SAHIFA)
# ========================
@admin_bp.route('/')
@login_required
@super_admin_required
def panel():
    pending_shops = Shop.query.filter_by(status='pending').order_by(Shop.created_at.desc()).all()
    active_shops = Shop.query.filter_by(status='active').order_by(Shop.created_at.desc()).all()
    rejected_shops = Shop.query.filter_by(status='rejected').order_by(Shop.created_at.desc()).all()
    
    stats = {
        'pending': len(pending_shops),
        'active': len(active_shops),
        'rejected': len(rejected_shops),
        'total': Shop.query.count()
    }
    
    return render_template('admin/panel.html',
                           pending_shops=pending_shops,
                           active_shops=active_shops,
                           rejected_shops=rejected_shops,
                           stats=stats)

# ========================
# DO'KON TASDIQLASH
# ========================
@admin_bp.route('/approve/<int:shop_id>', methods=['POST'])
@login_required
@super_admin_required
def approve_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop.status = 'active'
    db.session.commit()
    flash(f'✅ "{shop.name}" do\'koni muvaffaqiyatli tasdiqlandi!', 'success')
    return redirect(url_for('admin.panel'))

# ========================
# DO'KON RAD ETISH
# ========================
@admin_bp.route('/reject/<int:shop_id>', methods=['POST'])
@login_required
@super_admin_required
def reject_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop.status = 'rejected'
    db.session.commit()
    flash(f'❌ "{shop.name}" do\'koni rad etildi!', 'warning')
    return redirect(url_for('admin.panel'))

# ========================
# DO'KON NI O'CHIRISH
# ========================
@admin_bp.route('/delete/<int:shop_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_shop(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    shop_name = shop.name
    db.session.delete(shop)
    db.session.commit()
    flash(f'🗑️ "{shop_name}" do\'koni butunlay o\'chirildi!', 'info')
    return redirect(url_for('admin.panel'))

# ========================
# BARCHA AUDIT LOGLAR
# ========================
@admin_bp.route('/logs')
@login_required
@super_admin_required
def all_logs():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    return render_template('admin/logs.html', logs=logs)

# ========================
# DO'KON TAFSILOTLARI
# ========================
@admin_bp.route('/shop/<int:shop_id>')
@login_required
@super_admin_required
def shop_detail(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    users = User.query.filter_by(shop_id=shop_id).all()
    logs = AuditLog.query.filter_by(shop_id=shop_id).order_by(
        AuditLog.timestamp.desc()).limit(50).all()
    return render_template('admin/shop_detail.html',
                           shop=shop,
                           users=users,
                           logs=logs)