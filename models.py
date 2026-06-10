from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# =====================
# 1. DO'KONLAR JADVALI
# =====================
class Shop(db.Model):
    __tablename__ = 'shops'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / active / rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Aloqalar
    users = db.relationship('User', backref='shop', lazy=True, cascade='all, delete-orphan')
    debtors = db.relationship('Debtor', backref='shop', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='shop', lazy=True, cascade='all, delete-orphan')


# ================================
# 2. FOYDALANUVCHILAR JADVALI
# ================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='employee')
    # Rollar: 'super_admin' | 'owner' | 'employee'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Aloqalar
    transactions = db.relationship('Transaction', backref='user', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)


# =============================
# 3. QARZDORLAR JADVALI
# =============================
class Debtor(db.Model):
    __tablename__ = 'debtors'

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(200), default=None)
    total_debt = db.Column(db.Float, default=0.0)
    debt_limit = db.Column(db.Float, default=5000000.0)  # 5 million default limit
    is_frozen = db.Column(db.Boolean, default=False)
    trust_score = db.Column(db.String(20), default='new')
    # trust_score: 'new' | 'good' | 'medium' | 'bad'
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Aloqalar
    transactions = db.relationship('Transaction', backref='debtor', lazy=True, cascade='all, delete-orphan')


# ================================
# 4. TRANZAKSIYALAR JADVALI
# ================================
class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    debtor_id = db.Column(db.Integer, db.ForeignKey('debtors.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    action_type = db.Column(db.String(10), nullable=False)
    # action_type: 'add' (qarz oldi) | 'pay' (to'ladi)
    items = db.Column(db.Text, nullable=True)       # Mahsulotlar (JSON string)
    comment = db.Column(db.Text, nullable=True)     # Izoh
    due_date = db.Column(db.DateTime, nullable=True) # Qaytarish muddati
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ================================
# 5. AUDIT LOGS JADVALI
# ================================
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shops.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)