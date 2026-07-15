from app import create_app
from models import db, Menu

app = create_app()

updates = {
    'Indomie Goreng Rendang': 'img/menu/indomie-goreng-rendang.png',
    'Indomie Goreng Spesial': 'img/menu/indomie-goreng-special.png',
    'Indomie Kuah Kari Ayam': 'img/menu/indomie-kuah-kari-ayam.png',
    'Indomie Kuah Original': 'img/menu/indomie-kuah-original.png',
    'Indomie Kuah Soto': 'img/menu/indomie-kuah-soto.png',
    'Es Jeruk': 'img/menu/es-jeruk.png',
    'Es Teh Manis': 'img/menu/es-teh-manis.png',
}

with app.app_context():
    menus = Menu.query.all()
    for m in menus:
        if m.nama in updates:
            m.foto = updates[m.nama]
            print(f"Updated {m.nama} to {m.foto}")
    db.session.commit()
    print("Database updated for 7 items.")
