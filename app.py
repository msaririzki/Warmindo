import os
from flask import Flask, jsonify, session, render_template
from flask_login import LoginManager
from models import db, Admin, PengaturanToko
from werkzeug.security import generate_password_hash


def create_app():
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────────────────────────────
    app.secret_key = os.environ.get('SECRET_KEY', 'jokian-warmindo-secret-2025-change-me')
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'img', 'menu')
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2 MB

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Silakan login terlebih dahulu.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return Admin.query.get(int(user_id))

    # ── Blueprints ────────────────────────────────────────────────────────────
    from routes.customer import customer_bp
    from routes.admin import admin_bp

    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response

    # ── Legacy API shims (keep old AJAX calls working) ────────────────────────
    from flask_login import login_required as flask_login_required
    from models import Menu, Pesanan

    @app.route('/api/pesanan/<kode_order>/status', methods=['PATCH'])
    @flask_login_required
    def api_update_status(kode_order):
        from flask import request as req
        data = req.get_json(silent=True) or {}
        p = Pesanan.query.filter_by(kode_order=kode_order).first()
        if p:
            p.status = data.get('status', p.status)
            db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/menu/<int:menu_id>/stok', methods=['PATCH'])
    @flask_login_required
    def api_toggle_stok(menu_id):
        from flask import request as req
        data = req.get_json(silent=True) or {}
        item = Menu.query.get(menu_id)
        if item:
            item.status_stok = data.get('status_stok', item.status_stok)
            db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/pengaturan/status', methods=['PATCH'])
    @flask_login_required
    def api_toggle_store():
        from flask import request as req
        from models import PengaturanToko
        from routes.customer import get_pengaturan
        data = req.get_json(silent=True) or {}
        toko = get_pengaturan()
        toko.status_buka = bool(data.get('status_buka', toko.status_buka))
        db.session.commit()
        return jsonify({'success': True})

    # ── Error Handlers ─────────────────────────────────────────────────────
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    # ── DB init & seed ────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_if_empty()

    return app


def _seed_if_empty():
    """Seed initial data only when tables are empty."""
    from models import Menu, Admin, PengaturanToko

    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='owner',
        )
        db.session.add(admin)
        db.session.commit()
        print('[SEED] Admin created: admin / admin123 (owner)')

    if not Admin.query.filter_by(username='kasir1').first():
        kasir = Admin(
            username='kasir1',
            password_hash=generate_password_hash('kasir123'),
            role='kasir',
        )
        db.session.add(kasir)
        db.session.commit()
        print('[SEED] Kasir created: kasir1 / kasir123 (kasir)')

    if not PengaturanToko.query.first():
        toko = PengaturanToko(
            jam_buka='07:00',
            jam_tutup='22:00',
            status_buka=True,
            no_wa='6287715811122',
            alamat='Jl. Contoh No. 123, Kelurahan Maju, Kota Baik 12345',
            link_maps='https://maps.google.com/?q=-6.1944491,106.8195613',
        )
        db.session.add(toko)
        db.session.commit()
        print('[SEED] PengaturanToko created')

    if not Menu.query.first():
        menus = [
            Menu(nama='Indomie Goreng Spesial',  kategori='indomie',  harga=12000, stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Indomie Goreng Rendang',  kategori='indomie',  harga=13000, stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Indomie Kuah Original',   kategori='indomie',  harga=11000, stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Indomie Kuah Soto',       kategori='indomie',  harga=11000, stok=0,  status_stok='habis', foto=''),
            Menu(nama='Indomie Kuah Kari Ayam',  kategori='indomie',  harga=12000, stok=3,  status_stok='tersedia', foto=''),
            Menu(nama='Nasi Goreng Kampung',     kategori='nasi',     harga=18000, stok=30, status_stok='tersedia', foto=''),
            Menu(nama='Nasi Goreng Spesial',     kategori='nasi',     harga=22000, stok=25, status_stok='tersedia', foto=''),
            Menu(nama='Nasi Putih + Telur',      kategori='nasi',     harga=10000, stok=50, status_stok='tersedia', foto=''),
            Menu(nama='Es Teh Manis',            kategori='minuman',  harga=5000,  stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Es Jeruk',                kategori='minuman',  harga=8000,  stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Teh Hangat',              kategori='minuman',  harga=4000,  stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Telur Ceplok',            kategori='topping',  harga=3000,  stok=8,  status_stok='tersedia', foto=''),
            Menu(nama='Telur Dadar',             kategori='topping',  harga=3000,  stok=8,  status_stok='tersedia', foto=''),
            Menu(nama='Kerupuk',                 kategori='topping',  harga=1000,  stok=99, status_stok='tersedia', foto=''),
            Menu(nama='Sosis',                   kategori='topping',  harga=5000,  stok=5,  status_stok='tersedia', foto=''),
        ]
        # Link seeded menu records to the bundled image assets when available.
        image_by_name = {
            'Indomie Goreng Spesial': 'img/menu/indomie-goreng-special.png',
            'Indomie Goreng Rendang': 'img/menu/indomie-goreng-rendang.png',
            'Indomie Kuah Original': 'img/menu/indomie-kuah-original.png',
            'Indomie Kuah Soto': 'img/menu/indomie-kuah-soto.png',
            'Indomie Kuah Kari Ayam': 'img/menu/indomie-kuah-kari-ayam.png',
            'Es Teh Manis': 'img/menu/es-teh-manis.png',
            'Es Jeruk': 'img/menu/es-jeruk.png',
        }
        for menu in menus:
            if menu.nama in image_by_name:
                menu.foto = image_by_name[menu.nama]
        db.session.add_all(menus)
        db.session.commit()
        print(f'[SEED] {len(menus)} menu items created')


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
