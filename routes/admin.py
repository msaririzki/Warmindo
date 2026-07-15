import os
import re
import time
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, flash, current_app, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, text
from datetime import datetime, date, timedelta

from models import db, Menu, Pesanan, DetailPesanan, Admin, PengaturanToko
from routes.customer import (
    get_pengaturan, is_store_open, generate_kode_order, proses_pesanan
)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def owner_required(f):
    """Decorator: halaman hanya bisa diakses oleh admin dengan role 'owner'."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'owner':
            abort(403)
        return f(*args, **kwargs)
    return decorated


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def slugify(text):
    text = text.lower().strip()
    # Remove non-word characters (except spaces and hyphens)
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace spaces and multiple hyphens with a single hyphen
    text = re.sub(r'[-\s]+', '-', text)
    return text


def save_menu_photo(file, menu_nama):
    """Validate & save uploaded photo. Returns relative path or None on failure."""
    if not (file and file.filename and allowed_file(file.filename)):
        return None

    # Check file size (max 2 MB)
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)  # reset pointer
    if file_length > 2 * 1024 * 1024:
        return 'TOO_LARGE'

    slug = slugify(menu_nama)
    ext = file.filename.rsplit('.', 1)[1].lower()
    # Unique filename: slug + unix timestamp (ms)
    filename = f"{slug}_{int(time.time() * 1000)}.{ext}"

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)  # pastikan folder selalu ada
    upload_path = os.path.join(upload_folder, filename)
    file.save(upload_path)
    return f"img/menu/{filename}"


def delete_menu_photo(foto_path):
    """Delete a menu photo file from disk if it exists."""
    if not foto_path:
        return
    abs_path = os.path.join(current_app.root_path, 'static', foto_path)
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except OSError:
            pass


def get_pending_count():
    return Pesanan.query.filter_by(status='diproses', sumber='online').count()


def admin_context():
    """Base context passed to every admin template."""
    pengaturan = get_pengaturan()
    return {
        'pending_count': get_pending_count(),
        'store_open': is_store_open(pengaturan),
        'current_user': current_user,
        'current_page': '',
    }


# ─── AUTH ────────────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))
        error = 'Username atau password salah!'
    return render_template('admin/login.html', error=error)


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login'))


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Stats today
    pesanan_hari_ini = Pesanan.query.filter(
        Pesanan.waktu_order >= today_start,
        Pesanan.waktu_order <= today_end,
        Pesanan.status != 'batal',
    ).all()

    omzet_hari_ini = sum(p.total_harga for p in pesanan_hari_ini)
    total_pesanan = len(pesanan_hari_ini)
    pesanan_diproses = sum(1 for p in pesanan_hari_ini if p.status == 'diproses')
    pesanan_selesai = sum(1 for p in pesanan_hari_ini if p.status == 'selesai')

    # Pesanan terbaru (last 10)
    pesanan_terbaru = (
        Pesanan.query
        .order_by(Pesanan.waktu_order.desc())
        .limit(10)
        .all()
    )

    # Stok menipis (stok > 0 tapi <= 10)
    stok_menipis = (
        Menu.query
        .filter(Menu.stok > 0, Menu.stok <= 10)
        .order_by(Menu.stok.asc())
        .all()
    )

    # Omzet 7 hari terakhir (untuk Chart.js)
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_start = datetime.combine(d, datetime.min.time())
        d_end = datetime.combine(d, datetime.max.time())
        omzet_d = db.session.query(func.coalesce(func.sum(Pesanan.total_harga), 0)).filter(
            Pesanan.waktu_order >= d_start,
            Pesanan.waktu_order <= d_end,
            Pesanan.status != 'batal',
        ).scalar()
        chart_labels.append(d.strftime('%d %b'))
        chart_data.append(int(omzet_d))

    ctx = admin_context()
    ctx.update({
        'current_page': 'dashboard',
        'omzet_hari_ini': omzet_hari_ini,
        'total_pesanan': total_pesanan,
        'pesanan_diproses': pesanan_diproses,
        'pesanan_selesai': pesanan_selesai,
        'pesanan_terbaru': pesanan_terbaru,
        'stok_menipis': stok_menipis,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })
    return render_template('admin/dashboard.html', **ctx)


# ─── KASIR / POS ─────────────────────────────────────────────────────────────

@admin_bp.route('/kasir', methods=['GET', 'POST'])
@login_required
def kasir():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        items_raw = data.get('items', [])

        if not items_raw:
            return jsonify({'success': False, 'error': 'Tidak ada item'}), 400

        # Validate & enrich items from DB
        items = []
        stok_errors = []
        for raw in items_raw:
            menu_id = raw.get('menu_id')
            jumlah = int(raw.get('jumlah', 1))
            menu = Menu.query.get(menu_id)
            if not menu:
                continue
            # Cek stok cukup
            if menu.status_stok == 'habis' or menu.stok < jumlah:
                stok_errors.append(
                    f'Stok "{menu.nama}" tidak cukup (sisa {menu.stok})')
                continue
            subtotal = menu.harga * jumlah
            items.append({
                'menu_id': menu.id,
                'jumlah': jumlah,
                'subtotal': subtotal,
                'varian_id': raw.get('varian_id'),
                'catatan': raw.get('catatan', ''),
            })

        if stok_errors:
            return jsonify({'success': False, 'error': '; '.join(stok_errors)}), 400

        if not items:
            return jsonify({'success': False, 'error': 'Item tidak valid'}), 400

        pesanan = proses_pesanan(
            items=items,
            sumber='kasir',
            nama_customer=data.get('nama_customer', 'Walk-in'),
            no_hp=data.get('no_hp', ''),
            metode_ambil='ambil',
            metode_bayar=data.get('metode_bayar', 'cod'),
            catatan=data.get('catatan', ''),
            status='selesai',
        )
        return jsonify({
            'success': True,
            'kode_order': pesanan.kode_order,
            'total': pesanan.total_harga,
        })

    # GET: render POS page
    menu_list = Menu.query.order_by(Menu.kategori, Menu.nama).all()
    ctx = admin_context()
    ctx.update({
        'current_page': 'kasir',
        'menu': menu_list,
    })
    return render_template('admin/kasir.html', **ctx)


# ─── MENU CRUD ───────────────────────────────────────────────────────────────

@admin_bp.route('/menu')
@login_required
def menu():
    menu_list = Menu.query.order_by(Menu.kategori, Menu.nama).all()
    ctx = admin_context()
    ctx.update({'current_page': 'menu', 'menu': menu_list})
    return render_template('admin/menu.html', **ctx)


@admin_bp.route('/menu/tambah', methods=['GET', 'POST'])
@login_required
def menu_tambah():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
               or request.accept_mimetypes.best == 'application/json'

    if request.method == 'POST':
        foto_filename = ''
        file = request.files.get('foto')
        if file and file.filename:
            result = save_menu_photo(file, request.form.get('nama', 'menu'))
            if result == 'TOO_LARGE':
                if is_ajax:
                    return jsonify({'success': False, 'error': 'Ukuran file melebihi 2 MB'}), 400
                flash('Ukuran file melebihi 2 MB!', 'error')
                return redirect(url_for('admin.menu'))
            if result:
                foto_filename = result

        harga = int(request.form.get('harga', 0) or 0)
        if harga < 0:
            if is_ajax:
                return jsonify({'success': False, 'error': 'Harga tidak boleh negatif'}), 400
            flash('Harga tidak boleh negatif!', 'error')
            return redirect(url_for('admin.menu'))

        stok = int(request.form.get('stok', 99) or 99)
        if stok < 0:
            stok = 0
        status_stok = request.form.get('status_stok', 'tersedia')
        if stok <= 0:
            status_stok = 'habis'

        menu_baru = Menu(
            nama=request.form.get('nama', ''),
            kategori=request.form.get('kategori', 'indomie'),
            harga=harga,
            stok=stok,
            status_stok=status_stok,
            foto=foto_filename,
        )
        db.session.add(menu_baru)
        db.session.commit()

        if is_ajax:
            return jsonify({
                'success': True,
                'menu': {
                    'id': menu_baru.id,
                    'nama': menu_baru.nama,
                    'kategori': menu_baru.kategori,
                    'harga': menu_baru.harga,
                    'stok': menu_baru.stok,
                    'status_stok': menu_baru.status_stok,
                    'foto': menu_baru.foto or '',
                }
            })

        flash(f'Menu "{menu_baru.nama}" berhasil ditambahkan!', 'success')
        return redirect(url_for('admin.menu'))

    ctx = admin_context()
    ctx['current_page'] = 'menu'
    return render_template('admin/menu_form.html', menu_item=None, **ctx)


@admin_bp.route('/menu/<int:menu_id>/edit', methods=['GET', 'POST'])
@login_required
def menu_edit(menu_id):
    menu_item = Menu.query.get_or_404(menu_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
               or request.accept_mimetypes.best == 'application/json'

    if request.method == 'POST':
        menu_item.nama = request.form.get('nama', menu_item.nama)
        menu_item.kategori = request.form.get('kategori', menu_item.kategori)

        new_harga = int(request.form.get('harga', menu_item.harga) or menu_item.harga)
        if new_harga < 0:
            if is_ajax:
                return jsonify({'success': False, 'error': 'Harga tidak boleh negatif'}), 400
            flash('Harga tidak boleh negatif!', 'error')
            return redirect(url_for('admin.menu'))
        menu_item.harga = new_harga

        new_stok = int(request.form.get('stok', menu_item.stok) or menu_item.stok)
        if new_stok < 0:
            new_stok = 0
        menu_item.stok = new_stok
        menu_item.status_stok = request.form.get('status_stok', menu_item.status_stok)
        menu_item.update_status_stok()

        file = request.files.get('foto')
        if file and file.filename:
            result = save_menu_photo(file, menu_item.nama)
            if result == 'TOO_LARGE':
                if is_ajax:
                    return jsonify({'success': False, 'error': 'Ukuran file melebihi 2 MB'}), 400
                flash('Ukuran file melebihi 2 MB!', 'error')
                return redirect(url_for('admin.menu'))
            if result:
                # Delete old photo from disk
                delete_menu_photo(menu_item.foto)
                menu_item.foto = result

        db.session.commit()

        if is_ajax:
            return jsonify({
                'success': True,
                'menu': {
                    'id': menu_item.id,
                    'nama': menu_item.nama,
                    'kategori': menu_item.kategori,
                    'harga': menu_item.harga,
                    'stok': menu_item.stok,
                    'status_stok': menu_item.status_stok,
                    'foto': menu_item.foto or '',
                }
            })

        flash(f'Menu "{menu_item.nama}" berhasil diupdate!', 'success')
        return redirect(url_for('admin.menu'))

    ctx = admin_context()
    ctx.update({'current_page': 'menu', 'menu_item': menu_item})
    return render_template('admin/menu_form.html', **ctx)


@admin_bp.route('/menu/<int:menu_id>/hapus', methods=['POST'])
@login_required
def menu_hapus(menu_id):
    menu_item = Menu.query.get_or_404(menu_id)
    nama = menu_item.nama
    # Delete photo file from disk before removing DB record
    delete_menu_photo(menu_item.foto)
    db.session.delete(menu_item)
    db.session.commit()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return jsonify({'success': True})
    flash(f'Menu "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('admin.menu'))


@admin_bp.route('/menu/<int:menu_id>/toggle-stok', methods=['POST'])
@login_required
def menu_toggle_stok(menu_id):
    menu_item = Menu.query.get_or_404(menu_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get('status_stok')
    if new_status in ('tersedia', 'habis'):
        menu_item.status_stok = new_status
        if new_status == 'tersedia' and menu_item.stok <= 0:
            menu_item.stok = 1  # minimum stok when manually set to tersedia
        db.session.commit()
    return jsonify({'success': True, 'status_stok': menu_item.status_stok})


# ─── PESANAN ONLINE ──────────────────────────────────────────────────────────

@admin_bp.route('/pesanan')
@login_required
def pesanan():
    status_filter = request.args.get('status', 'semua')
    q = Pesanan.query.filter_by(sumber='online')
    if status_filter != 'semua':
        q = q.filter_by(status=status_filter)
    pesanan_list = q.order_by(Pesanan.waktu_order.desc()).all()

    # Count per status for filter tabs
    status_counts = {}
    for s in ['diproses', 'siap', 'selesai', 'batal']:
        status_counts[s] = Pesanan.query.filter_by(sumber='online', status=s).count()
    status_counts['semua'] = Pesanan.query.filter_by(sumber='online').count()

    ctx = admin_context()
    ctx.update({
        'current_page': 'pesanan',
        'pesanan_list': pesanan_list,
        'active_status': status_filter,
        'status_counts': status_counts,
    })
    return render_template('admin/pesanan.html', **ctx)


@admin_bp.route('/pesanan/<int:pesanan_id>/status', methods=['POST'])
@login_required
def pesanan_update_status(pesanan_id):
    pesanan_item = Pesanan.query.get_or_404(pesanan_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    valid_statuses = ['diproses', 'siap', 'selesai', 'batal']
    if new_status in valid_statuses:
        pesanan_item.status = new_status
        db.session.commit()
        return jsonify({'success': True, 'status': pesanan_item.status})
    return jsonify({'success': False, 'error': 'Status tidak valid'}), 400


@admin_bp.route('/pesanan/<int:pesanan_id>/detail')
@login_required
def pesanan_detail(pesanan_id):
    pesanan_item = Pesanan.query.get_or_404(pesanan_id)
    items = []
    for dp in pesanan_item.items:
        menu_nama = dp.menu.nama if dp.menu else '(menu dihapus)'
        varian_label = dp.varian.nama_varian if dp.varian else ''
        items.append({
            'nama': menu_nama,
            'varian': varian_label,
            'qty': dp.jumlah,
            'subtotal': dp.subtotal,
        })
    return jsonify({
        'kode_order': pesanan_item.kode_order,
        'nama': pesanan_item.nama_customer,
        'hp': pesanan_item.no_hp,
        'ambil': 'Ambil di Tempat' if pesanan_item.metode_ambil == 'ambil' else 'Diantar',
        'bayar': pesanan_item.metode_bayar.upper(),
        'catatan': pesanan_item.catatan or '—',
        'total': pesanan_item.total_harga,
        'items': items,
        'sumber': pesanan_item.sumber,
        'status': pesanan_item.status,
    })


# ─── KELOLA KASIR ────────────────────────────────────────────────────────────

@admin_bp.route('/kelola-kasir')
@owner_required
def kelola_kasir():
    kasir_list = Admin.query.filter_by(role='kasir').order_by(Admin.username).all()
    ctx = admin_context()
    ctx.update({
        'current_page': 'kelola-kasir',
        'kasir_list': kasir_list,
    })
    return render_template('admin/kelola_kasir.html', **ctx)


@admin_bp.route('/kelola-kasir/tambah', methods=['POST'])
@owner_required
def kelola_kasir_tambah():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    confirm = request.form.get('confirm_password', '')

    import re as _re
    if not username or len(username) < 3:
        flash('Username minimal 3 karakter!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    if not _re.match(r'^[a-zA-Z0-9_]+$', username):
        flash('Username hanya boleh huruf, angka, dan underscore!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    if Admin.query.filter_by(username=username).first():
        flash(f'Username "{username}" sudah digunakan!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    if not password or len(password) < 6:
        flash('Password minimal 6 karakter!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    if password != confirm:
        flash('Password dan konfirmasi tidak cocok!', 'error')
        return redirect(url_for('admin.kelola_kasir'))

    kasir = Admin(
        username=username,
        password_hash=generate_password_hash(password),
        role='kasir',
    )
    db.session.add(kasir)
    db.session.commit()
    flash(f'Akun kasir "{username}" berhasil dibuat!', 'success')
    return redirect(url_for('admin.kelola_kasir'))


@admin_bp.route('/kelola-kasir/<int:kasir_id>/hapus', methods=['POST'])
@owner_required
def kelola_kasir_hapus(kasir_id):
    kasir = Admin.query.get_or_404(kasir_id)
    if kasir.role != 'kasir':
        flash('Tidak bisa menghapus akun owner!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    nama = kasir.username
    db.session.delete(kasir)
    db.session.commit()
    flash(f'Akun kasir "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('admin.kelola_kasir'))


@admin_bp.route('/kelola-kasir/<int:kasir_id>/reset-password', methods=['POST'])
@owner_required
def kelola_kasir_reset_password(kasir_id):
    kasir = Admin.query.get_or_404(kasir_id)
    if kasir.role != 'kasir':
        flash('Tidak bisa mereset password akun owner!', 'error')
        return redirect(url_for('admin.kelola_kasir'))

    new_password = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')

    if not new_password or len(new_password) < 6:
        flash('Password baru minimal 6 karakter!', 'error')
        return redirect(url_for('admin.kelola_kasir'))
    if new_password != confirm:
        flash('Password baru dan konfirmasi tidak cocok!', 'error')
        return redirect(url_for('admin.kelola_kasir'))

    kasir.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash(f'Password kasir "{kasir.username}" berhasil direset!', 'success')
    return redirect(url_for('admin.kelola_kasir'))


# ─── LAPORAN ─────────────────────────────────────────────────────────────────

@admin_bp.route('/laporan')
@owner_required
def laporan():
    periode = request.args.get('periode', 'hari')
    date_from_str = request.args.get('from')
    date_to_str = request.args.get('to')

    today = date.today()
    if periode == 'hari':
        date_from = today
        date_to = today
    elif periode == 'minggu':
        date_from = today - timedelta(days=today.weekday())
        date_to = today
    elif periode == 'bulan':
        date_from = today.replace(day=1)
        date_to = today
    elif periode == 'custom' and date_from_str and date_to_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            date_from = today
            date_to = today
    else:
        date_from = today
        date_to = today

    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to, datetime.max.time())

    # Filtered pesanan
    pesanan_filtered = Pesanan.query.filter(
        Pesanan.waktu_order >= dt_from,
        Pesanan.waktu_order <= dt_to,
        Pesanan.status != 'batal',
    ).order_by(Pesanan.waktu_order.desc()).all()

    total_omzet = sum(p.total_harga for p in pesanan_filtered)
    total_transaksi = len(pesanan_filtered)
    rata_rata = total_omzet // total_transaksi if total_transaksi else 0

    # Menu terlaris
    top_menu_rows = (
        db.session.query(Menu.nama, func.sum(DetailPesanan.jumlah).label('terjual'))
        .join(DetailPesanan, DetailPesanan.menu_id == Menu.id)
        .join(Pesanan, Pesanan.id == DetailPesanan.pesanan_id)
        .filter(
            Pesanan.waktu_order >= dt_from,
            Pesanan.waktu_order <= dt_to,
            Pesanan.status != 'batal',
        )
        .group_by(Menu.id)
        .order_by(func.sum(DetailPesanan.jumlah).desc())
        .limit(5)
        .all()
    )

    top_menu_nama = top_menu_rows[0][0] if top_menu_rows else '—'
    max_terjual = top_menu_rows[0][1] if top_menu_rows else 1

    top_menu = [
        {'nama': r[0], 'terjual': r[1], 'pct': round(r[1] / max_terjual * 100)}
        for r in top_menu_rows
    ]

    # Omzet per hari (last 7 days in range)
    omzet_harian = []
    days_count = (date_to - date_from).days + 1
    for i in range(min(days_count, 7)):
        d = date_from + timedelta(days=i)
        d_start = datetime.combine(d, datetime.min.time())
        d_end = datetime.combine(d, datetime.max.time())
        omzet_d = sum(
            p.total_harga for p in pesanan_filtered
            if d_start <= p.waktu_order <= d_end
        )
        omzet_harian.append({'tanggal': d.strftime('%d %b'), 'omzet': omzet_d})

    ctx = admin_context()
    ctx.update({
        'current_page': 'laporan',
        'periode': periode,
        'date_from': date_from.strftime('%Y-%m-%d'),
        'date_to': date_to.strftime('%Y-%m-%d'),
        'total_omzet': total_omzet,
        'total_transaksi': total_transaksi,
        'rata_rata': rata_rata,
        'top_menu_nama': top_menu_nama,
        'top_menu': top_menu,
        'omzet_harian': omzet_harian,
        'pesanan_list': pesanan_filtered[:20],  # last 20 for table
    })
    return render_template('admin/laporan.html', **ctx)


@admin_bp.route('/laporan/export')
@owner_required
def laporan_export():
    """Export laporan penjualan ke file CSV."""
    import csv
    import io
    from flask import Response

    periode = request.args.get('periode', 'hari')
    date_from_str = request.args.get('from')
    date_to_str = request.args.get('to')

    today = date.today()
    if periode == 'hari':
        date_from = today
        date_to = today
    elif periode == 'minggu':
        date_from = today - timedelta(days=today.weekday())
        date_to = today
    elif periode == 'bulan':
        date_from = today.replace(day=1)
        date_to = today
    elif periode == 'custom' and date_from_str and date_to_str:
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            date_from = today
            date_to = today
    else:
        date_from = today
        date_to = today

    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to, datetime.max.time())

    pesanan_filtered = Pesanan.query.filter(
        Pesanan.waktu_order >= dt_from,
        Pesanan.waktu_order <= dt_to,
        Pesanan.status != 'batal',
    ).order_by(Pesanan.waktu_order.desc()).all()

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Tanggal', 'Kode Order', 'Sumber', 'Nama Customer', 'No HP',
                     'Metode Bayar', 'Status', 'Total (Rp)'])
    for p in pesanan_filtered:
        writer.writerow([
            p.waktu_order.strftime('%Y-%m-%d %H:%M') if p.waktu_order else '',
            p.kode_order,
            p.sumber,
            p.nama_customer or 'Walk-in',
            p.no_hp or '-',
            p.metode_bayar.upper() if p.metode_bayar else '-',
            p.status,
            p.total_harga,
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"laporan_warmindo_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ─── PENGATURAN ──────────────────────────────────────────────────────────────

@admin_bp.route('/pengaturan', methods=['GET', 'POST'])
@owner_required
def pengaturan():
    toko = get_pengaturan()

    if request.method == 'POST':
        action = request.form.get('action', 'kontak')

        if action == 'jam':
            toko.jam_buka = request.form.get('jam_buka', toko.jam_buka)
            toko.jam_tutup = request.form.get('jam_tutup', toko.jam_tutup)
            db.session.commit()
            flash('Jadwal operasional berhasil disimpan!', 'success')

        elif action == 'kontak':
            toko.no_wa = request.form.get('no_wa', toko.no_wa)
            toko.alamat = request.form.get('alamat', toko.alamat)
            toko.link_maps = request.form.get('link_maps', toko.link_maps)
            db.session.commit()
            flash('Info kontak berhasil disimpan!', 'success')

        elif action == 'foto':
            file = request.files.get('foto_toko')
            if file and file.filename and allowed_file(file.filename):
                file.seek(0, os.SEEK_END)
                size = file.tell(); file.seek(0)
                if size > 2 * 1024 * 1024:
                    flash('Ukuran foto melebihi 2 MB!', 'error')
                else:
                    # Delete old photo
                    if toko.foto_toko:
                        old = os.path.join(current_app.root_path, 'static', toko.foto_toko)
                        if os.path.isfile(old):
                            try: os.remove(old)
                            except OSError: pass
                    import time as _time
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    fname = f"toko_{int(_time.time()*1000)}.{ext}"
                    dest_dir = os.path.join(current_app.root_path, 'static', 'img', 'toko')
                    os.makedirs(dest_dir, exist_ok=True)
                    file.save(os.path.join(dest_dir, fname))
                    toko.foto_toko = f"img/toko/{fname}"
                    db.session.commit()
                    flash('Foto toko berhasil diperbarui!', 'success')
            else:
                flash('Pilih file gambar yang valid (JPG/PNG/WEBP).', 'error')

        elif action == 'password':
            old_pass = request.form.get('old_pass', '')
            new_pass = request.form.get('new_pass', '')
            confirm = request.form.get('confirm_pass', '')
            if not check_password_hash(current_user.password_hash, old_pass):
                flash('Password lama tidak sesuai!', 'error')
            elif new_pass != confirm:
                flash('Password baru tidak cocok!', 'error')
            elif len(new_pass) < 6:
                flash('Password minimal 6 karakter!', 'error')
            else:
                current_user.password_hash = generate_password_hash(new_pass)
                db.session.commit()
                flash('Password berhasil diubah!', 'success')

        return redirect(url_for('admin.pengaturan'))

    ctx = admin_context()
    ctx.update({'current_page': 'pengaturan', 'pengaturan_toko': toko})
    return render_template('admin/pengaturan.html', **ctx)


@admin_bp.route('/pengaturan/toggle-status', methods=['POST'])
@owner_required
def toggle_store_status():
    toko = get_pengaturan()
    data = request.get_json(silent=True) or {}
    toko.status_buka = bool(data.get('status_buka', not toko.status_buka))
    db.session.commit()
    return jsonify({'success': True, 'status_buka': toko.status_buka})
