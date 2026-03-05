"""
Script de création de la base de données SQLite de démonstration.
Thème : une petite entreprise e-commerce avec clients, produits, commandes.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")


def create_database():
    # Supprimer si elle existe déjà
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Tables ──────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            city TEXT,
            country TEXT DEFAULT 'France',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL CHECK(price > 0),
            stock INTEGER NOT NULL DEFAULT 0,
            description TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TEXT DEFAULT (date('now')),
            status TEXT CHECK(status IN ('pending', 'shipped', 'delivered', 'cancelled')),
            total REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # ── Données ─────────────────────────────────────────────

    customers = [
        ("Alice", "Dupont", "alice.dupont@email.fr", "Paris", "France"),
        ("Bob", "Martin", "bob.martin@email.fr", "Lyon", "France"),
        ("Clara", "Bernard", "clara.bernard@email.fr", "Marseille", "France"),
        ("David", "Petit", "david.petit@email.fr", "Toulouse", "France"),
        ("Emma", "Robert", "emma.robert@email.fr", "Nice", "France"),
        ("François", "Richard", "francois.richard@email.fr", "Nantes", "France"),
        ("Giulia", "Rossi", "giulia.rossi@email.it", "Milan", "Italie"),
        ("Hans", "Müller", "hans.muller@email.de", "Berlin", "Allemagne"),
    ]
    cursor.executemany(
        "INSERT INTO customers (first_name, last_name, email, city, country) VALUES (?, ?, ?, ?, ?)",
        customers,
    )

    products = [
        ("Laptop Pro 15", "Informatique", 1299.99, 25, "Ordinateur portable 15 pouces, 16 Go RAM"),
        ("Souris sans fil", "Informatique", 29.99, 150, "Souris ergonomique Bluetooth"),
        ("Clavier mécanique", "Informatique", 89.99, 80, "Clavier RGB switches Cherry MX"),
        ("Écran 27 pouces", "Informatique", 349.99, 40, "Écran 4K IPS 27 pouces"),
        ("Casque audio BT", "Audio", 79.99, 60, "Casque Bluetooth avec réduction de bruit"),
        ("Enceinte portable", "Audio", 49.99, 100, "Enceinte waterproof 20W"),
        ("Webcam HD", "Vidéo", 59.99, 45, "Webcam 1080p avec micro intégré"),
        ("Hub USB-C", "Accessoires", 39.99, 200, "Hub 7 ports USB-C vers USB-A/HDMI"),
        ("Tapis de souris XL", "Accessoires", 19.99, 300, "Tapis 90x40cm antidérapant"),
        ("Câble HDMI 2.1", "Accessoires", 14.99, 500, "Câble 2m HDMI 2.1 8K"),
    ]
    cursor.executemany(
        "INSERT INTO products (name, category, price, stock, description) VALUES (?, ?, ?, ?, ?)",
        products,
    )

    orders_data = [
        (1, "2025-01-15", "delivered", 1329.98),
        (2, "2025-01-20", "delivered", 89.99),
        (1, "2025-02-10", "delivered", 429.98),
        (3, "2025-02-14", "shipped", 79.99),
        (4, "2025-03-01", "pending", 1399.98),
        (5, "2025-03-02", "pending", 169.97),
        (7, "2025-02-28", "delivered", 349.99),
        (8, "2025-03-03", "cancelled", 29.99),
        (6, "2025-01-25", "delivered", 139.98),
        (2, "2025-03-04", "pending", 59.99),
    ]
    cursor.executemany(
        "INSERT INTO orders (customer_id, order_date, status, total) VALUES (?, ?, ?, ?)",
        orders_data,
    )

    order_items_data = [
        (1, 1, 1, 1299.99),  # Alice: 1 Laptop
        (1, 2, 1, 29.99),    # Alice: 1 Souris
        (2, 3, 1, 89.99),    # Bob: 1 Clavier
        (3, 1, 1, 1299.99),  # Alice commande 2: Laptop (non, erreur) -> Écran + Casque
        (3, 4, 1, 349.99),   # Alice commande 2: Écran
        (3, 5, 1, 79.99),    # Alice commande 2: Casque
        (4, 5, 1, 79.99),    # Clara: Casque
        (5, 1, 1, 1299.99),  # David: Laptop
        (5, 9, 1, 19.99),    # David: Tapis
        (5, 8, 2, 39.99),    # David: 2 Hub USB-C
        (6, 6, 2, 49.99),    # Emma: 2 Enceintes
        (6, 5, 1, 79.99),    # Emma: Casque (corrigé)
        (7, 4, 1, 349.99),   # Giulia: Écran
        (8, 2, 1, 29.99),    # Hans: Souris (annulée)
        (9, 3, 1, 89.99),    # François: Clavier
        (9, 6, 1, 49.99),    # François: Enceinte
        (10, 7, 1, 59.99),   # Bob: Webcam
    ]
    cursor.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
        order_items_data,
    )

    conn.commit()
    conn.close()
    print(f"Base de données créée avec succès : {DB_PATH}")


if __name__ == "__main__":
    create_database()
