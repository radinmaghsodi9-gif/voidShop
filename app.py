import os, secrets, hashlib, time
from datetime import datetime, timedelta
from functools import wraps
import flask

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-this-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024

raw_db = os.getenv('DATABASE_URL', 'sqlite:///void_shop.db')
if raw_db.startswith('postgres://'):
    raw_db = raw_db.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ALLOWED_RECEIPTS = {'png','jpg','jpeg','webp','pdf'}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(32), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StaffAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(80), default='متفرقه')
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default='')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product_name = db.Column(db.String(180), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    player_id = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), default='')
    status = db.Column(db.String(30), default='pending', nullable=False)
    receipt_data = db.Column(db.LargeBinary, nullable=True)
    receipt_name = db.Column(db.String(180), nullable=True)
    receipt_mime = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LoginRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(32), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)
    support_code = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id','product_id', name='uq_favorite'),)

class Setting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, default='')

DEFAULT_SETTINGS = {
    'site_name':'Void Shop',
    'site_tagline':'Blox Fruits Services',
    'site_description':'فروش سرویس‌ها و آیتم‌های Blox Fruits',
    'announcement':'سفارش‌ها بعد از بررسی رسید وارد صف انجام می‌شوند.',
    'support_text':'برای پشتیبانی از راه ارتباطی اعلام‌شده توسط مدیریت استفاده کنید.',
    'terms':'قبل از ثبت سفارش، توضیحات محصول را کامل بخوانید. مسئولیت وارد کردن Player ID صحیح با خریدار است.',
    'card_number':'0000-0000-0000-0000',
    'card_owner':'Void Shop',
    'support_phone':'09xxxxxxxxx',
    'telegram_support':'@VoidSupport',
    'rubika_support':'@VoidSupport',
    'telegram_channel':'@VoidShop',
    'rubika_channel':'@VoidShop',
    'maintenance':'0'
}

PRODUCTS = [
('Yama','Sword',120000),('Tushita','Sword',180000),('Full Cursed Dual Katana','Package',420000),
('Fragments 1000','Fragments',50000),('Fragments 5000','Fragments',250000),('Fragments 10000','Fragments',500000),
('Hallow Scythe','Sword',230000),('Dark Coat','Accessory',700000),('Full TTK','Package',330000),
('Dragon Talon','Fighting Style',300000),('Dragon Talon V2','Fighting Style',150000),('Full Belt','Package',300000),
('Godhuman','Fighting Style',800000),('Sanguine Art','Fighting Style',450000),('Combat V2','Fighting Style',1000000),
('Fish','Race',220000),('Sharkman Karate','Fighting Style',200000),('Soul Guitar','Gun',300000),('Venom Bow','Gun',30000),
('Dragonstorm','Gun',550000),('Sharkman Karate V2','Fighting Style',100000),('Swan Glasses','Accessory',50000),
('Leviathan Ship','Ship',105000),('Pale Scarf','Accessory',155000),('Spiky Trident','Sword',420000),
('Shark Anchor','Sword',300000),('Leviathan Shield','Accessory',400000),('Levi Crown','Accessory',300000),
('Ghoul','Race',180000),('Cyborg','Race',300000),('Draco','Race',400000),
('V2 Any Race (except Draco)','Race V2',45000),('V3 Any Race (except Draco)','Race V3',100000),
('V4 Single Gear (except Draco)','Race V4',120000),('V4 Full Gear (except Draco)','Race V4',365000),
('Draco V2','Race V2',130000),('Draco V3','Race V3',230000),('Draco V4','Race V4',500000),
('Level Up 300 Levels','Level Up',200000),('Mastery 100','Mastery',165000),
('Rainbow Haki','Haki',70000),('Kitsune Haki','Haki',235000),('Collection 1M','Collection',140000),('Chocolates 10','Collection',140000)
]
SECRET = {
'Middle Town':(45000,180000,55000,195000),'Skyland':(70000,100000,110000,285000),'Colosseum':(35000,20000,160000,205000),
'Magma Village':(50000,80000,145000,275000),'Snow Village':(20000,50000,80000,155000),'Marine Fortress':(23000,160000,80000,268000),
'Pirate Village':(20000,60000,85000,160000),'Underwater City':(35000,40000,45000,115000),'Jungle':(25000,40000,45000,100000),
'Prison':(35000,50000,80000,160000),'Desert':(40000,42000,67000,140000),'Upper Skyland':(110000,60000,125000,280000)
}

STATUS_FA = {'pending':'در انتظار بررسی','paid':'پرداخت تأیید شد','processing':'در حال انجام','completed':'تکمیل شد','rejected':'رد شد'}

@app.context_processor
def inject_globals():
    settings = {x.key:x.value for x in Setting.query.all()} if db.session.registry.has() else DEFAULT_SETTINGS.copy()
    settings = {**DEFAULT_SETTINGS, **settings}
    return {'settings':settings, 'status_fa':STATUS_FA}

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapper


def owner_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin') or session.get('admin_role') != 'owner':
            flash('این بخش فقط برای Owner است.', 'error')
            return redirect(url_for('admin'))
        return fn(*args, **kwargs)
    return wrapper

def user_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

def hash_code(code):
    return hashlib.sha256(code.encode()).hexdigest()

def money(n):
    return f'{n:,}'
app.jinja_env.filters['money'] = money

@app.before_request
def guard_maintenance():
    if request.endpoint and request.endpoint.startswith('static'):
        return
    if request.endpoint in {'admin_login','admin_logout','static'}:
        return
    s = Setting.query.filter_by(key='maintenance').first()
    if s and s.value == '1' and not session.get('admin'):
        return render_template('maintenance.html'), 503

with app.app_context():
    db.create_all() @app.route('/')
def index():
    q = request.args.get('q','').strip()
    cat = request.args.get('category','').strip()
    query = Product.query.filter_by(active=True)
    if q: query = query.filter(Product.name.ilike(f'%{q}%'))
    if cat: query = query.filter_by(category=cat)
    products = query.order_by(Product.category, Product.price).all()
    favorite_ids = set()
    if session.get('user_id'):
        favorite_ids = {x.product_id for x in Favorite.query.filter_by(user_id=session['user_id']).all()}
    categories = [x[0] for x in db.session.query(Product.category).filter_by(active=True).distinct().order_by(Product.category).all()]
    return render_template('index.html', products=products, favorite_ids=favorite_ids, categories=categories, q=q, cat=cat)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone','').strip()
        if len(phone) < 7:
            flash('شماره موبایل معتبر وارد کنید.','error')
            return redirect(url_for('login'))
        code = f'{secrets.randbelow(1000000):06d}'
        req = LoginRequest(phone=phone, code_hash=hash_code(code), support_code=code, expires_at=datetime.utcnow()+timedelta(minutes=10))
        db.session.add(req); db.session.commit()
        session['login_request_id'] = req.id
        return redirect(url_for('verify'))
    return render_template('login.html')

@app.route('/verify', methods=['GET','POST'])
def verify():
    req_id = session.get('login_request_id')
    req = LoginRequest.query.get(req_id) if req_id else None
    if not req or req.used:
        return redirect(url_for('login'))
    if request.method == 'POST':
        code = request.form.get('code','').strip()
        if datetime.utcnow() > req.expires_at or not req.approved or hash_code(code) != req.code_hash:
            flash('کد اشتباه است، هنوز توسط پشتیبانی تأیید نشده یا منقضی شده.','error')
            return redirect(url_for('verify'))
        req.used = True
        phone = req.phone
        user = User.query.filter_by(phone=phone).first() or User(phone=phone)
        db.session.add(user); db.session.commit()
        session.pop('login_request_id',None)
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return render_template('verify.html', login_request=req)

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('index'))

@app.route('/favorite/<int:product_id>', methods=['POST'])
@user_required
def favorite(product_id):
    existing = Favorite.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    if existing: db.session.delete(existing)
    else: db.session.add(Favorite(user_id=session['user_id'], product_id=product_id))
    db.session.commit(); return redirect(request.referrer or url_for('index'))

@app.route('/account')
@user_required
def account():
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    favs = Favorite.query.filter_by(user_id=session['user_id']).all()
    fav_products = [Product.query.get(f.product_id) for f in favs]
    return render_template(
    'account.html',
    orders=orders,
    favorites=favorites,
    management_unlocked=session.get('management_unlocked', False)
)

@app.route('/order/<int:product_id>', methods=['GET','POST'])
@user_required
def order(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.active: abort(404)
    if request.method == 'POST':
        if request.form.get('rules') != 'yes':
            flash('برای ثبت سفارش باید قوانین را تأیید کنید.','error'); return redirect(url_for('order',product_id=product.id))
        player_id = request.form.get('player_id','').strip()
        contact = request.form.get('contact','').strip()
        if not player_id:
            flash('Player ID / Username را وارد کنید.','error'); return redirect(url_for('order',product_id=product.id))
        order = Order(user_id=session['user_id'], product_id=product.id, product_name=product.name, price=product.price, player_id=player_id, contact=contact)
        db.session.add(order); db.session.commit()
        return redirect(url_for('payment',order_id=order.id))
    return render_template('order.html', product=product)

@app.route('/payment/<int:order_id>', methods=['GET','POST'])
@user_required
def payment(order_id):
    order = Order.query.filter_by(id=order_id, user_id=session['user_id']).first_or_404()
    settings = {x.key:x.value for x in Setting.query.all()}
    card = settings.get('card_number', DEFAULT_SETTINGS['card_number'])
    owner = settings.get('card_owner', DEFAULT_SETTINGS['card_owner'])
    if request.method == 'POST':
        receipt = request.files.get('receipt')
        if not receipt or not receipt.filename:
            flash('رسید پرداخت را انتخاب کنید.','error'); return redirect(url_for('payment',order_id=order.id))
        ext = receipt.filename.rsplit('.',1)[-1].lower() if '.' in receipt.filename else ''
        if ext not in ALLOWED_RECEIPTS:
            flash('فرمت رسید باید PNG/JPG/WEBP/PDF باشد.','error'); return redirect(url_for('payment',order_id=order.id))
        data = receipt.read()
        if not data or len(data) > 8*1024*1024:
            flash('حجم رسید نامعتبر است.','error'); return redirect(url_for('payment',order_id=order.id))
        order.receipt_data = data
        order.receipt_name = secure_filename(receipt.filename)
        order.receipt_mime = receipt.mimetype or 'application/octet-stream'
        order.status = 'pending'
        db.session.commit()
        return redirect(url_for('success',order_id=order.id))
    return render_template('payment.html', order=order, card=card, owner=owner)

@app.route('/success/<int:order_id>')
@user_required
def success(order_id):
    order = Order.query.filter_by(id=order_id, user_id=session['user_id']).first_or_404()
    return render_template('success.html', order=order)

@app.route('/account/management-access', methods=['POST'])
def management_access():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    code = request.form.get('management_code', '').strip()

    if code == MANAGEMENT_ACCESS_CODE:
        session['management_unlocked'] = True
        flash('دسترسی مدیریتی فعال شد.', 'ok')
    else:
        session.pop('management_unlocked', None)
        flash('کد دسترسی اشتباه است.', 'error')

    return redirect(url_for('account'))

OWNER_EMAIL = 'radinmaghsodi9@gmail.com'
MANAGEMENT_ACCESS_CODE = 'Admin 3317'

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        owner_password = os.getenv('ADMIN_PASSWORD', 'change-me')

        if email == OWNER_EMAIL and password == owner_password:
            session['admin'] = True
            session['admin_role'] = 'owner'
            session['admin_email'] = OWNER_EMAIL

            return redirect(url_for('admin'))

        staff = StaffAdmin.query.filter_by(
            email=email,
            active=True
        ).first()

        if staff and check_password_hash(
            staff.password_hash,
            password
        ):
            session['admin'] = True
            session['admin_role'] = 'admin'
            session['admin_email'] = staff.email

            return redirect(url_for('admin'))

        flash('ایمیل یا رمز عبور اشتباه است.', 'error')

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    session.pop('admin_role', None)
    session.pop('admin_email', None)
    session.pop('management_unlocked', None)

    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    orders = Order.query.order_by(
        Order.created_at.desc()
    ).all()

    products = Product.query.order_by(
        Product.id.asc()
    ).all()

    login_requests = LoginRequest.query.order_by(
        LoginRequest.created_at.desc()
    ).all()

    settings = {
        setting.key: setting.value
        for setting in Setting.query.all()
    }

    staff_admins = StaffAdmin.query.order_by(
        StaffAdmin.created_at.desc()
    ).all()

    return render_template(
        'admin.html',
        orders=orders,
        products=products,
        login_requests=login_requests,
        settings={**DEFAULT_SETTINGS, **settings},
        staff_admins=staff_admins,
        admin_role=session.get('admin_role'),
        admin_email=session.get('admin_email')
    )

@app.route('/admin/login-request/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_login_request(request_id):
    req = LoginRequest.query.get_or_404(request_id)
    if req.used or datetime.utcnow() > req.expires_at:
        flash('این درخواست منقضی شده است.','error')
        return redirect(url_for('admin'))
    req.approved = True
    db.session.commit()
    flash(f'کد ورود برای {req.phone}: {get_code_for_admin(req.id)}','ok')
    return redirect(url_for('admin'))

def get_code_for_admin(request_id):
    # The raw code is intentionally not stored. Admin gets a fresh code by resetting the request.
    req = LoginRequest.query.get_or_404(request_id)
    # derive a support-visible code from a server-side temporary value stored in the session is not possible across devices.
    # This function is replaced below by the support-code flow using a separate encrypted/plain temporary field.
    return 'کد در نسخه بعدی'
@app.route('/admin/staff/add', methods=['POST'])
@owner_required
def add_staff_admin():
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or '@' not in email:
        flash('ایمیل معتبر وارد کنید.', 'error')
        return redirect(url_for('admin'))

    if len(password) < 6:
        flash('رمز عبور باید حداقل ۶ کاراکتر باشد.', 'error')
        return redirect(url_for('admin'))

    if email == OWNER_EMAIL:
        flash('ایمیل Owner را نمی‌توان به عنوان Admin اضافه کرد.', 'error')
        return redirect(url_for('admin'))

    existing = StaffAdmin.query.filter_by(email=email).first()

    if existing:
        flash('این Admin قبلاً وجود دارد.', 'error')
        return redirect(url_for('admin'))

    staff = StaffAdmin(
        email=email,
        password_hash=generate_password_hash(password),
        active=True
    )

    db.session.add(staff)
    db.session.commit()

    flash('Admin جدید اضافه شد.', 'ok')
    return redirect(url_for('admin'))


@app.route('/admin/staff/<int:admin_id>/delete', methods=['POST'])
@owner_required
def delete_staff_admin(admin_id):
    staff = StaffAdmin.query.get_or_404(admin_id)

    db.session.delete(staff)
    db.session.commit()

    flash('Admin حذف شد.', 'ok')
    return redirect(url_for('admin'))

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@admin_required
def admin_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get('status')
    if status not in STATUS_FA: abort(400)
    order.status = status; db.session.commit()
    flash('وضعیت سفارش ذخیره شد.','ok'); return redirect(url_for('admin'))

@app.route('/admin/receipt/<int:order_id>')
@admin_required
def receipt(order_id):
    order = Order.query.get_or_404(order_id)
    if not order.receipt_data: abort(404)
    return send_file(BytesIO(order.receipt_data), mimetype=order.receipt_mime or 'application/octet-stream', download_name=order.receipt_name or f'receipt-{order.id}')
@app.route('/admin/product/add', methods=['POST'])
@admin_required
def add_product():
    name = request.form.get('name', '').strip()
    price = request.form.get('price', '0').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('نام محصول را وارد کنید.', 'error')
        return redirect(url_for('admin'))

    try:
        price = int(price)
    except ValueError:
        flash('قیمت باید عدد باشد.', 'error')
        return redirect(url_for('admin'))

    if price < 0:
        flash('قیمت نمی‌تواند منفی باشد.', 'error')
        return redirect(url_for('admin'))

    product = Product(
        name=name,
        price=price,
        description=description,
        active=True
    )

    db.session.add(product)
    db.session.commit()

    flash('محصول جدید اضافه شد.', 'ok')
    return redirect(url_for('admin'))
@app.route('/admin/product/<int:product_id>', methods=['POST'])
@admin_required
def edit_product(product_id):
    p = Product.query.get_or_404(product_id)
    p.name = request.form.get('name',p.name).strip() or p.name
    p.category = request.form.get('category',p.category).strip() or p.category
    p.price = max(0, int(request.form.get('price',p.price) or p.price))
    p.description = request.form.get('description',p.description)
    p.active = request.form.get('active') == '1'
    db.session.commit(); flash('محصول ذخیره شد.','ok'); return redirect(url_for('admin'))

@app.route('/admin/settings', methods=['POST'])
@admin_required
def edit_settings():
    allowed = DEFAULT_SETTINGS.keys()
    for key in allowed:
        value = request.form.get(key)
        if value is not None:
            row = Setting.query.get(key) or Setting(key=key)
            row.value = value
            db.session.add(row)
    db.session.commit(); flash('تنظیمات ذخیره شد.','ok'); return redirect(url_for('admin'))

@app.errorhandler(413)
def too_large(_):
    staff_admins = StaffAdmin.query.order_by(StaffAdmin.created_at.desc()).all()


def seed():
    db.create_all()
    for k,v in DEFAULT_SETTINGS.items():
        if not Setting.query.get(k): db.session.add(Setting(key=k,value=v))
    if Product.query.count() == 0:
        for name,cat,price in PRODUCTS:
            db.session.add(Product(name=name,category=cat,price=price,description='توضیحات این محصول را مدیریت می‌تواند از پنل ادمین تغییر دهد.'))
        for place, vals in SECRET.items():
            a,b,c,full = vals
            db.session.add(Product(name=f'{place} Secret Quest 1',category='Secret Quest',price=a,description=f'مرحله اول Secret Quest در {place}.'))
            db.session.add(Product(name=f'{place} Secret Quest 2',category='Secret Quest',price=b,description=f'مرحله دوم Secret Quest در {place}.'))
            db.session.add(Product(name=f'{place} Secret Quest 3',category='Secret Quest',price=c,description=f'مرحله سوم Secret Quest در {place}.'))
            db.session.add(Product(name=f'{place} Secret Quest Full',category='Secret Quest',price=full,description=f'پکیج کامل Secret Quest در {place}.'))
        db.session.commit()

with app.app_context():
    seed()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT',5000)), debug=True)
