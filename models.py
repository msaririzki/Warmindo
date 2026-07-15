from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class Menu(db.Model):
    __tablename__ = 'menu'

    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(120), nullable=False)
    kategori = db.Column(db.String(30), nullable=False)  # indomie/nasi/minuman/topping
    harga = db.Column(db.Integer, nullable=False)
    foto = db.Column(db.String(200), default='')
    stok = db.Column(db.Integer, default=99)
    status_stok = db.Column(db.String(10), default='tersedia')  # tersedia/habis

    varian = db.relationship('Varian', backref='menu', lazy=True, cascade='all, delete-orphan')
    detail_pesanan = db.relationship('DetailPesanan', backref='menu', lazy=True)

    def update_status_stok(self):
        """Auto-update status_stok based on stok value."""
        if self.stok <= 0:
            self.status_stok = 'habis'
        else:
            self.status_stok = 'tersedia'

    def to_dict(self):
        return {
            'id': self.id,
            'nama': self.nama,
            'kategori': self.kategori,
            'harga': self.harga,
            'foto': self.foto,
            'stok': self.stok,
            'status_stok': self.status_stok,
        }


class Varian(db.Model):
    __tablename__ = 'varian'

    id = db.Column(db.Integer, primary_key=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=False)
    nama_varian = db.Column(db.String(80), nullable=False)
    harga_tambahan = db.Column(db.Integer, default=0)


class Pesanan(db.Model):
    __tablename__ = 'pesanan'

    id = db.Column(db.Integer, primary_key=True)
    kode_order = db.Column(db.String(30), unique=True, nullable=False)
    sumber = db.Column(db.String(10), nullable=False)       # online/kasir
    nama_customer = db.Column(db.String(120), default='')
    no_hp = db.Column(db.String(20), default='')
    metode_ambil = db.Column(db.String(10), default='ambil')   # ambil/diantar
    alamat = db.Column(db.Text, default='')
    metode_bayar = db.Column(db.String(10), default='cod')     # cod/transfer/qris
    total_harga = db.Column(db.Integer, default=0)
    status = db.Column(db.String(10), default='diproses')      # diproses/siap/selesai/batal
    waktu_order = db.Column(db.DateTime, default=datetime.now)
    catatan = db.Column(db.Text, default='')

    items = db.relationship('DetailPesanan', backref='pesanan', lazy=True, cascade='all, delete-orphan')

    def items_as_dicts(self):
        result = []
        for dp in self.items:
            result.append({
                'nama': dp.menu.nama if dp.menu else '(dihapus)',
                'varian': dp.varian_id,   # simple label; no Varian obj needed for display
                'qty': dp.jumlah,
                'subtotal': dp.subtotal,
                'catatan_item': dp.catatan_item or '',
            })
        return result


class DetailPesanan(db.Model):
    __tablename__ = 'detail_pesanan'

    id = db.Column(db.Integer, primary_key=True)
    pesanan_id = db.Column(db.Integer, db.ForeignKey('pesanan.id'), nullable=False)
    menu_id = db.Column(db.Integer, db.ForeignKey('menu.id'), nullable=True)
    varian_id = db.Column(db.Integer, db.ForeignKey('varian.id'), nullable=True)
    jumlah = db.Column(db.Integer, default=1)
    subtotal = db.Column(db.Integer, default=0)
    catatan_item = db.Column(db.String(200), default='')

    varian = db.relationship('Varian', foreign_keys=[varian_id])


class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), default='kasir')   # owner/kasir


class PengaturanToko(db.Model):
    __tablename__ = 'pengaturan_toko'

    id = db.Column(db.Integer, primary_key=True)
    jam_buka = db.Column(db.String(5), default='07:00')
    jam_tutup = db.Column(db.String(5), default='22:00')
    status_buka = db.Column(db.Boolean, default=True)     # manual override
    no_wa = db.Column(db.String(30), default='6281234567890')
    alamat = db.Column(db.Text, default='Jl. Contoh No. 123, Kota Baik 12345')
    link_maps = db.Column(db.Text, default='https://maps.google.com/?q=-6.1944491,106.8195613')
    foto_toko = db.Column(db.String(200), default='')



class Customer(UserMixin, db.Model):
    __tablename__ = 'customer'

    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    no_hp = db.Column(db.String(20), default='')
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

