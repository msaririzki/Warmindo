from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Menu, Pesanan, DetailPesanan, PengaturanToko, Customer
from datetime import datetime

customer_bp = Blueprint('customer', __name__)


# ─── HELPERS ────────────────────────────────────────────────────────────────

def get_pengaturan():
    p = PengaturanToko.query.first()
    if not p:
        p = PengaturanToko()
        db.session.add(p)
        db.session.commit()
    return p


def is_store_open(pengaturan=None):
    if pengaturan is None:
        pengaturan = get_pengaturan()
    # Manual override check
    if not pengaturan.status_buka:
        return False
    now = datetime.now()
    try:
        buka = datetime.strptime(pengaturan.jam_buka, '%H:%M').replace(
            year=now.year, month=now.month, day=now.day)
        tutup = datetime.strptime(pengaturan.jam_tutup, '%H:%M').replace(
            year=now.year, month=now.month, day=now.day)
        return buka <= now < tutup
    except Exception:
        return True


def generate_kode_order():
    today = datetime.now().strftime('%Y%m%d')
    prefix = f'WM-{today}-'
    count = Pesanan.query.filter(
        Pesanan.kode_order.like(f'{prefix}%')
    ).count()
    return f'{prefix}{str(count + 1).zfill(3)}'


def get_cart():
    """Return list of cart dicts from session, enriched with DB price."""
    raw = session.get('cart', [])
    result = []
    for item in raw:
        menu = Menu.query.get(item.get('menu_id'))
        if menu:
            subtotal = menu.harga * item.get('jumlah', 1)
            result.append({
                'menu_id': menu.id,
                'nama': menu.nama,
                'harga': menu.harga,
                'foto': menu.foto,
                'jumlah': item.get('jumlah', 1),
                'varian_id': item.get('varian_id'),
                'varian_label': item.get('varian_label', ''),
                'catatan': item.get('catatan', ''),
                'subtotal': subtotal,
            })
    return result


def cart_total(cart):
    return sum(i['subtotal'] for i in cart)


def proses_pesanan(items, sumber, nama_customer=None, no_hp=None, **kwargs):
    """
    Shared order-processing logic used by both /checkout (online) and
    /admin/kasir (walk-in). Cuts stock, inserts Pesanan + DetailPesanan.
    Returns the saved Pesanan object.
    """
    kode = generate_kode_order()
    total = sum(i['subtotal'] for i in items)

    pesanan = Pesanan(
        kode_order=kode,
        sumber=sumber,
        nama_customer=nama_customer or '',
        no_hp=no_hp or '',
        total_harga=total,
        **kwargs
    )
    db.session.add(pesanan)
    db.session.flush()  # get pesanan.id before commit

    for item in items:
        menu = Menu.query.get(item['menu_id'])
        if menu:
            menu.stok = max(0, menu.stok - item['jumlah'])
            menu.update_status_stok()
            db.session.add(menu)

        detail = DetailPesanan(
            pesanan_id=pesanan.id,
            menu_id=item.get('menu_id'),
            varian_id=item.get('varian_id'),
            jumlah=item['jumlah'],
            subtotal=item['subtotal'],
            catatan_item=item.get('catatan', ''),
        )
        db.session.add(detail)

    db.session.commit()
    return pesanan


# ─── ROUTES ─────────────────────────────────────────────────────────────────

@customer_bp.route('/')
def index():
    pengaturan = get_pengaturan()
    menu_favorit = (
        Menu.query
        .filter_by(status_stok='tersedia')
        .order_by(Menu.id.asc())
        .limit(4)
        .all()
    )
    return render_template(
        'customer/index.html',
        menu_favorit=menu_favorit,
        store_open=is_store_open(pengaturan),
        pengaturan=pengaturan,
    )


@customer_bp.route('/menu')
def menu_page():
    kategori = request.args.get('kategori', 'semua')
    q = Menu.query
    if kategori != 'semua':
        q = q.filter_by(kategori=kategori)
    menu_list = q.order_by(Menu.kategori, Menu.nama).all()
    return render_template(
        'customer/menu.html',
        menu=menu_list,
        active_kategori=kategori,
    )


@customer_bp.route('/keranjang/tambah', methods=['POST'])
def keranjang_tambah():
    data = request.get_json(silent=True) or {}
    menu_id = data.get('menu_id')
    jumlah = int(data.get('jumlah', 1))

    menu = Menu.query.get(menu_id)
    if not menu or menu.status_stok == 'habis':
        return jsonify({'success': False, 'error': 'Menu tidak tersedia'}), 400

    cart = session.get('cart', [])
    # Find existing entry (same menu_id + varian_id)
    existing = next(
        (i for i in cart
         if i.get('menu_id') == menu_id and i.get('varian_id') == data.get('varian_id')),
        None
    )
    if existing:
        existing['jumlah'] += jumlah
    else:
        cart.append({
            'menu_id': menu_id,
            'jumlah': jumlah,
            'varian_id': data.get('varian_id'),
            'varian_label': data.get('varian_label', ''),
            'catatan': data.get('catatan', ''),
        })

    session['cart'] = cart
    session.modified = True

    cart_enriched = get_cart()
    return jsonify({
        'success': True,
        'cart_count': sum(i['jumlah'] for i in cart),
        'cart_total': cart_total(cart_enriched),
    })


@customer_bp.route('/keranjang')
def keranjang():
    cart = get_cart()
    return render_template(
        'customer/keranjang.html',
        cart=cart,
        cart_total=cart_total(cart),
    )


@customer_bp.route('/keranjang/update', methods=['POST'])
def keranjang_update():
    data = request.get_json(silent=True) or {}
    idx = data.get('idx')
    jumlah = int(data.get('jumlah', 0))

    cart = session.get('cart', [])
    if idx is not None and 0 <= idx < len(cart):
        if jumlah <= 0:
            cart.pop(idx)
        else:
            cart[idx]['jumlah'] = jumlah

    session['cart'] = cart
    session.modified = True
    cart_enriched = get_cart()
    return jsonify({
        'success': True,
        'cart_count': sum(i['jumlah'] for i in cart),
        'cart_total': cart_total(cart_enriched),
    })


@customer_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    pengaturan = get_pengaturan()

    if request.method == 'POST':
        if not cart:
            flash('Keranjang kamu kosong!', 'warning')
            return redirect(url_for('customer.menu_page'))

        # ── Validasi input form ──────────────────────────────────────
        nama = request.form.get('nama', '').strip()
        no_hp = request.form.get('no_hp', '').strip()
        if not nama:
            flash('Nama lengkap wajib diisi!', 'warning')
            return redirect(url_for('customer.checkout'))
        if not no_hp or not no_hp.replace('+', '').replace('-', '').isdigit() or len(no_hp) < 10:
            flash('Nomor HP tidak valid! Gunakan angka minimal 10 digit.', 'warning')
            return redirect(url_for('customer.checkout'))

        # ── Validasi stok ────────────────────────────────────────────
        stok_errors = []
        for item in cart:
            menu = Menu.query.get(item['menu_id'])
            if not menu:
                stok_errors.append(f"Menu \"{item['nama']}\" sudah tidak tersedia.")
            elif menu.status_stok == 'habis' or menu.stok < item['jumlah']:
                stok_errors.append(
                    f"Stok \"{menu.nama}\" tidak cukup (sisa {menu.stok}, diminta {item['jumlah']}).")
        if stok_errors:
            for err in stok_errors:
                flash(err, 'error')
            flash('Silakan perbarui keranjang kamu.', 'warning')
            return redirect(url_for('customer.keranjang'))

        # Build items list for proses_pesanan
        items = [
            {
                'menu_id': i['menu_id'],
                'jumlah': i['jumlah'],
                'subtotal': i['subtotal'],
                'varian_id': i.get('varian_id'),
                'catatan': i.get('catatan', ''),
            }
            for i in cart
        ]

        pesanan = proses_pesanan(
            items=items,
            sumber='online',
            nama_customer=nama,
            no_hp=no_hp,
            metode_ambil=request.form.get('metode_ambil', 'ambil'),
            alamat=request.form.get('alamat', ''),
            metode_bayar=request.form.get('metode_bayar', 'cod'),
            catatan=request.form.get('catatan', ''),
            status='diproses',
        )

        # Clear session cart
        session.pop('cart', None)
        session.modified = True

        return redirect(url_for('customer.status_pesanan', kode_order=pesanan.kode_order))

    return render_template(
        'customer/checkout.html',
        cart=cart,
        cart_total=cart_total(cart),
        pengaturan=pengaturan,
    )


@customer_bp.route('/pesanan/<kode_order>')
def status_pesanan(kode_order):
    pesanan = Pesanan.query.filter_by(kode_order=kode_order).first_or_404()
    pengaturan = get_pengaturan()

    # Build items list compatible with template
    items = []
    for dp in pesanan.items:
        menu_nama = dp.menu.nama if dp.menu else '(menu dihapus)'
        varian_label = ''
        if dp.varian:
            varian_label = dp.varian.nama_varian
        elif dp.catatan_item:
            varian_label = dp.catatan_item
        items.append({
            'nama': menu_nama,
            'varian': varian_label,
            'qty': dp.jumlah,
            'subtotal': dp.subtotal,
        })

    # Build a context dict that matches what the template expects
    pesanan_ctx = {
        'kode_order': pesanan.kode_order,
        'nama_customer': pesanan.nama_customer or 'Pelanggan',
        'status': pesanan.status,
        'metode_ambil': pesanan.metode_ambil,
        'metode_bayar': pesanan.metode_bayar,
        'total_harga': pesanan.total_harga,
        'waktu_order': pesanan.waktu_order.strftime('%Y-%m-%d %H:%M') if pesanan.waktu_order else '',
        'catatan': pesanan.catatan or '',
        'items': items,
    }

    return render_template(
        'customer/status_pesanan.html',
        pesanan=pesanan_ctx,
        pengaturan=pengaturan,
    )


# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@customer_bp.route('/pesanan/<kode_order>/batal', methods=['POST'])
def batal_pesanan(kode_order):
    pesanan = Pesanan.query.filter_by(kode_order=kode_order).first()
    if not pesanan:
        return jsonify({'success': False, 'error': 'Pesanan tidak ditemukan'}), 404
    if pesanan.status != 'diproses':
        return jsonify({'success': False, 'error': 'Pesanan tidak bisa dibatalkan'}), 400

    # Restore stock
    for dp in pesanan.items:
        menu = Menu.query.get(dp.menu_id)
        if menu:
            menu.stok += dp.jumlah
            menu.update_status_stok()

    pesanan.status = 'batal'
    db.session.commit()
    return jsonify({'success': True, 'status': 'batal'})


@customer_bp.route('/api/pesanan/<kode_order>', methods=['GET'])
def api_get_pesanan(kode_order):
    pesanan = Pesanan.query.filter_by(kode_order=kode_order).first()
    if not pesanan:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'status': pesanan.status})


@customer_bp.route('/api/cart/count')
def api_cart_count():
    cart = session.get('cart', [])
    enriched = get_cart()
    return jsonify({
        'count': sum(i['jumlah'] for i in cart),
        'total': cart_total(enriched),
    })


# ─── HELPER: current customer ────────────────────────────────────────────────

def get_current_customer():
    cid = session.get('customer_id')
    if cid:
        return Customer.query.get(cid)
    return None


# ─── AUTH CUSTOMER ───────────────────────────────────────────────────────────

@customer_bp.route('/daftar', methods=['GET', 'POST'])
def daftar():
    if get_current_customer():
        return redirect(url_for('customer.index'))

    error = None
    if request.method == 'POST':
        nama  = request.form.get('nama', '').strip()
        email = request.form.get('email', '').strip().lower()
        no_hp = request.form.get('no_hp', '').strip()
        pw    = request.form.get('password', '')
        pw2   = request.form.get('confirm_password', '')

        if not nama or not email or not pw:
            error = 'Semua field wajib diisi.'
        elif pw != pw2:
            error = 'Password dan konfirmasi tidak cocok.'
        elif len(pw) < 6:
            error = 'Password minimal 6 karakter.'
        elif Customer.query.filter_by(email=email).first():
            error = 'Email sudah terdaftar. Silakan login.'
        else:
            customer = Customer(
                nama=nama,
                email=email,
                no_hp=no_hp,
                password_hash=generate_password_hash(pw),
            )
            db.session.add(customer)
            db.session.commit()
            session['customer_id'] = customer.id
            flash(f'Selamat datang, {customer.nama}! Akun kamu berhasil dibuat.', 'success')
            return redirect(url_for('customer.index'))

    return render_template('customer/daftar.html', error=error)


@customer_bp.route('/masuk', methods=['GET', 'POST'])
def masuk():
    if get_current_customer():
        return redirect(url_for('customer.index'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pw    = request.form.get('password', '')
        customer = Customer.query.filter_by(email=email).first()
        if customer and check_password_hash(customer.password_hash, pw):
            session['customer_id'] = customer.id
            flash(f'Selamat datang kembali, {customer.nama}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('customer.index'))
        error = 'Email atau password salah.'

    return render_template('customer/masuk.html', error=error)


@customer_bp.route('/keluar')
def keluar():
    session.pop('customer_id', None)
    flash('Kamu berhasil keluar.', 'info')
    return redirect(url_for('customer.index'))


@customer_bp.route('/profil')
def profil():
    customer = get_current_customer()
    if not customer:
        return redirect(url_for('customer.masuk', next='/profil'))
    pesanan_list = Pesanan.query.filter_by(
        nama_customer=customer.nama, sumber='online'
    ).order_by(Pesanan.waktu_order.desc()).limit(10).all()
    return render_template('customer/profil.html', customer=customer, pesanan_list=pesanan_list)

