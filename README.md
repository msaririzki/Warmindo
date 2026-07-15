# 🍜 WARMINDO — Sistem Pemesanan Online Warung Mie Instan

Aplikasi web pemesanan makanan untuk Warung Mie Instan (Warmindo) yang mencakup **pemesanan online oleh customer**, **sistem POS kasir**, dan **panel admin** untuk pengelolaan toko secara menyeluruh.

## 📸 Fitur Utama

### 🛒 Fitur Customer (Pelanggan)
- Landing page dengan informasi toko & menu favorit
- Katalog menu lengkap dengan filter kategori (Indomie, Nasi, Minuman, Topping)
- Keranjang belanja dengan pengelolaan item
- Checkout dengan pilihan metode pengambilan (Ambil/Diantar) & pembayaran (COD/Transfer/QRIS)
- Halaman status pesanan real-time dengan kode order unik
- Registrasi & login akun pelanggan
- Profil pelanggan dengan riwayat pesanan

### 🏪 Fitur Admin / Kasir
- **Dashboard** — Ringkasan omzet harian, pesanan masuk, grafik omzet 7 hari (Chart.js)
- **Kasir / POS** — Mode point-of-sale untuk transaksi walk-in langsung
- **Pesanan Online** — Manajemen pesanan dari customer online (diproses → siap → selesai)
- **Kelola Menu** — CRUD menu lengkap dengan upload foto (maks 2 MB), manajemen stok & varian
- **Laporan Penjualan** — Statistik omzet dengan filter periode (Hari/Minggu/Bulan/Custom) + **Export CSV**
- **Pengaturan Toko** — Jam operasional, status buka/tutup, kontak WhatsApp, alamat & Google Maps

### 🔐 Keamanan & Hak Akses
- Password di-hash menggunakan PBKDF2 via `werkzeug.security`
- **Role-based access control**: Admin dibagi menjadi **Owner** dan **Kasir**
  - 🔑 **Owner**: Akses penuh (Dashboard, Kasir, Pesanan, Menu, Laporan, Pengaturan)
  - 🔑 **Kasir**: Akses terbatas (Dashboard, Kasir, Pesanan, Menu)
- Halaman error custom (404 & 403) agar tidak menampilkan traceback Python
- Validasi stok otomatis saat checkout & kasir

---

## 🛠️ Tech Stack

| Komponen      | Teknologi                                        |
|---------------|--------------------------------------------------|
| **Backend**   | Python 3, Flask 3.x                              |
| **Database**  | SQLite (via SQLAlchemy ORM — database-agnostic)   |
| **Frontend**  | HTML5, Tailwind CSS (CDN), JavaScript             |
| **Grafik**    | Chart.js 4.x (CDN)                               |
| **Auth**      | Flask-Login (Admin), Session-based (Customer)     |
| **Font**      | Plus Jakarta Sans (Google Fonts)                  |

---

## 📦 Petunjuk Instalasi

### Prasyarat
- **Python** 3.10 atau lebih baru
- **pip** (biasanya sudah termasuk dengan Python)
- **Git** (untuk cloning repository)

### Langkah-langkah

```bash
# 1. Clone repository
git clone https://github.com/<username>/WEBSITE-WARMINDO.git
cd WEBSITE-WARMINDO-main

# 2. Buat virtual environment
python -m venv venv

# 3. Aktifkan virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependency
pip install -r requirements.txt

# 5. Jalankan aplikasi
python app.py
```

Aplikasi akan berjalan di **http://localhost:5000**

### 🔑 Akun Default

| Role    | Username | Password   |
|---------|----------|------------|
| Owner   | `admin`  | `admin123` |

> **Catatan**: Database SQLite (`instance/database.db`) akan dibuat otomatis saat pertama kali menjalankan `python app.py`. Data awal (menu, admin, pengaturan toko) akan di-seed secara otomatis.

---

## 📁 Struktur Direktori

```
WEBSITE-WARMINDO-main/
├── app.py                  # Entry point aplikasi Flask
├── models.py               # Model database (SQLAlchemy ORM)
├── requirements.txt        # Daftar dependency Python
├── migrate_db.py           # Script migrasi database
│
├── routes/
│   ├── customer.py         # Route untuk halaman customer
│   └── admin.py            # Route untuk panel admin
│
├── templates/
│   ├── base.html           # Template dasar (layout utama)
│   ├── customer/           # Template halaman customer
│   │   ├── index.html      # Landing page
│   │   ├── menu.html       # Katalog menu
│   │   ├── keranjang.html  # Keranjang belanja
│   │   ├── checkout.html   # Halaman checkout
│   │   ├── status_pesanan.html  # Status pesanan
│   │   ├── masuk.html      # Login customer
│   │   ├── daftar.html     # Registrasi customer
│   │   ├── profil.html     # Profil customer
│   │   ├── navbar.html     # Navigasi customer
│   │   └── footer.html     # Footer customer
│   ├── admin/              # Template panel admin
│   │   ├── dashboard.html  # Dashboard + grafik Chart.js
│   │   ├── kasir.html      # Mode POS kasir
│   │   ├── pesanan.html    # Manajemen pesanan online
│   │   ├── menu.html       # CRUD menu
│   │   ├── laporan.html    # Laporan penjualan
│   │   ├── pengaturan.html # Pengaturan toko
│   │   ├── sidebar.html    # Sidebar navigasi admin
│   │   └── login.html      # Login admin
│   └── errors/             # Halaman error custom
│       ├── 404.html        # Halaman Not Found
│       └── 403.html        # Halaman Forbidden
│
└── static/
    ├── css/main.css        # Stylesheet utama
    ├── js/main.js          # JavaScript global (toast, cart, modal)
    └── img/                # Gambar (menu, toko)
```

---

## 🗄️ Entity Relationship Diagram (ERD)

Aplikasi menggunakan **7 tabel** dalam database SQLite:

```mermaid
erDiagram
    ADMIN {
        int id PK
        string username UK
        string password_hash
        string role "owner / kasir"
    }

    CUSTOMER {
        int id PK
        string nama
        string email UK
        string no_hp
        string password_hash
        datetime created_at
    }

    MENU {
        int id PK
        string nama
        string kategori "indomie/nasi/minuman/topping"
        int harga
        string foto
        int stok
        string status_stok "tersedia / habis"
    }

    VARIAN {
        int id PK
        int menu_id FK
        string nama_varian
        int harga_tambahan
    }

    PESANAN {
        int id PK
        string kode_order UK
        string sumber "online / kasir"
        string nama_customer
        string no_hp
        string metode_ambil "ambil / diantar"
        string metode_bayar "cod / transfer / qris"
        int total_harga
        string status "diproses/siap/selesai/batal"
        datetime waktu_order
        text catatan
    }

    DETAIL_PESANAN {
        int id PK
        int pesanan_id FK
        int menu_id FK
        int varian_id FK
        int jumlah
        int subtotal
        string catatan_item
    }

    PENGATURAN_TOKO {
        int id PK
        string jam_buka
        string jam_tutup
        boolean status_buka
        string no_wa
        text alamat
        text link_maps
    }

    MENU ||--o{ VARIAN : "memiliki"
    MENU ||--o{ DETAIL_PESANAN : "dipesan dalam"
    PESANAN ||--|{ DETAIL_PESANAN : "berisi"
    VARIAN ||--o{ DETAIL_PESANAN : "dipilih di"
```

---

## 👥 Use Case Diagram

```mermaid
graph LR
    subgraph Aktor
        C["👤 Customer"]
        K["🛒 Kasir"]
        O["👑 Owner"]
    end

    subgraph "Fitur Customer"
        C1["Lihat Menu & Katalog"]
        C2["Tambah ke Keranjang"]
        C3["Checkout Pesanan"]
        C4["Lihat Status Pesanan"]
        C5["Registrasi / Login"]
        C6["Lihat Profil & Riwayat"]
    end

    subgraph "Fitur Kasir"
        K1["Login Admin"]
        K2["Dashboard"]
        K3["Mode Kasir / POS"]
        K4["Kelola Pesanan Online"]
        K5["Kelola Menu CRUD"]
        K6["Cetak Struk"]
    end

    subgraph "Fitur Owner"
        O1["Laporan Penjualan"]
        O2["Export CSV"]
        O3["Pengaturan Toko"]
        O4["Grafik Omzet Chart.js"]
    end

    C --- C1 & C2 & C3 & C4 & C5 & C6
    K --- K1 & K2 & K3 & K4 & K5 & K6
    O --- K1 & K2 & K3 & K4 & K5 & K6
    O --- O1 & O2 & O3 & O4
```

---

## 🔄 Flowchart Alur Pemesanan

```mermaid
flowchart TD
    A["Customer Buka Website"] --> B["Lihat Menu"]
    B --> C["Tambah ke Keranjang"]
    C --> D["Buka Checkout"]
    D --> E{"Isi Form Valid?"}
    E -- Tidak --> D
    E -- Ya --> F{"Stok Cukup?"}
    F -- Tidak --> G["Flash Error: Stok Habis"]
    G --> H["Redirect ke Keranjang"]
    F -- Ya --> I["Proses Pesanan"]
    I --> J["Potong Stok Menu"]
    J --> K["Simpan ke Database"]
    K --> L["Tampilkan Kode Order"]

    L --> M{"Admin Proses"}
    M --> N["Status: Diproses"]
    N --> O["Status: Siap"]
    O --> P["Status: Selesai"]

    style A fill:#e84a0c,color:#fff
    style I fill:#22c55e,color:#fff
    style P fill:#3b82f6,color:#fff
    style G fill:#ef4444,color:#fff
```

---

## 📝 Catatan Pengembangan

- **Database-agnostic**: Menggunakan SQLAlchemy ORM. Untuk migrasi ke MySQL/PostgreSQL, cukup ubah `SQLALCHEMY_DATABASE_URI` di `app.py`.
- **Responsive Design**: Semua halaman mendukung desktop dan mobile.
- **Validasi Berlapis**: Validasi dilakukan di frontend (HTML5 + JavaScript) dan backend (Python/Flask).

---

## 📄 Lisensi

Proyek ini dibuat untuk keperluan akademis — Mata Kuliah MPTI, Semester 6.

© 2025 WARMINDO
