"""
Script de création de la base de données SQLite — Case-Shiller House Price Index.

Source : S&P/Case-Shiller U.S. National Home Price Index
         https://github.com/datasets/house-prices-us

Ce script :
  1. Télécharge les CSV depuis GitHub (ou utilise des fichiers locaux)
  2. Crée une base SQLite normalisée avec 4 tables :
     - cities        : les 20 métropoles du Case-Shiller Index
     - national_index: indice national mensuel depuis 1975
     - city_prices   : indice mensuel par ville depuis 1987
     - market_events : événements économiques marquants pour le contexte
"""

import csv
import io
import os
import sqlite3
import urllib.request

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "housing.db")

CITIES_URL = "https://raw.githubusercontent.com/datasets/house-prices-us/main/data/cities-month-SA.csv"
NATIONAL_URL = "https://raw.githubusercontent.com/datasets/house-prices-us/main/data/national-month.csv"


def download_csv(url: str) -> list[dict]:
    """Télécharge un CSV depuis une URL et retourne une liste de dicts."""
    print(f"  Téléchargement : {url}")
    response = urllib.request.urlopen(url)
    content = response.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


# Mapping des colonnes CSV → noms de villes lisibles
CITY_MAPPING = {
    "AZ-Phoenix": ("Phoenix", "Arizona", "AZ"),
    "CA-Los Angeles": ("Los Angeles", "California", "CA"),
    "CA-San Diego": ("San Diego", "California", "CA"),
    "CA-San Francisco": ("San Francisco", "California", "CA"),
    "CO-Denver": ("Denver", "Colorado", "CO"),
    "DC-Washington": ("Washington D.C.", "District of Columbia", "DC"),
    "FL-Miami": ("Miami", "Florida", "FL"),
    "FL-Tampa": ("Tampa", "Florida", "FL"),
    "GA-Atlanta": ("Atlanta", "Georgia", "GA"),
    "IL-Chicago": ("Chicago", "Illinois", "IL"),
    "MA-Boston": ("Boston", "Massachusetts", "MA"),
    "MI-Detroit": ("Detroit", "Michigan", "MI"),
    "MN-Minneapolis": ("Minneapolis", "Minnesota", "MN"),
    "NC-Charlotte": ("Charlotte", "North Carolina", "NC"),
    "NV-Las Vegas": ("Las Vegas", "Nevada", "NV"),
    "NY-New York": ("New York", "New York", "NY"),
    "OH-Cleveland": ("Cleveland", "Ohio", "OH"),
    "OR-Portland": ("Portland", "Oregon", "OR"),
    "TX-Dallas": ("Dallas", "Texas", "TX"),
    "WA-Seattle": ("Seattle", "Washington", "WA"),
}

# Événements économiques marquants pour enrichir l'analyse
MARKET_EVENTS = [
    ("1987-10-19", "Black Monday", "Krach boursier mondial — le Dow Jones perd 22.6% en un jour"),
    ("1991-03-01", "Fin récession 1990-91", "Fin de la récession causée par la crise S&L"),
    ("1995-01-01", "Boom dot-com début", "Début de la bulle Internet — croissance économique forte"),
    ("2000-03-10", "Pic bulle dot-com", "Le NASDAQ atteint son sommet historique avant l'éclatement"),
    ("2001-09-11", "Attentats 11 septembre", "Choc économique majeur — la Fed baisse les taux drastiquement"),
    ("2004-06-01", "Fed hausse taux", "La Fed commence à remonter les taux après les avoir maintenus bas"),
    ("2006-07-01", "Pic immobilier US", "Les prix immobiliers atteignent leur sommet national — début de la chute"),
    ("2007-12-01", "Début Grande Récession", "Début officiel de la récession — crise des subprimes"),
    ("2008-09-15", "Faillite Lehman Brothers", "La banque Lehman Brothers fait faillite — panique financière mondiale"),
    ("2009-06-01", "Fin Grande Récession", "Fin officielle de la récession — début de la reprise lente"),
    ("2012-01-01", "Creux immobilier", "Les prix immobiliers atteignent leur point le plus bas au niveau national"),
    ("2020-03-11", "Pandémie COVID-19", "L'OMS déclare la pandémie — les marchés s'effondrent"),
    ("2020-06-01", "Boom immobilier COVID", "Les taux bas + télétravail provoquent une flambée des prix immobiliers"),
    ("2022-03-16", "Fed hausse taux post-COVID", "La Fed commence à remonter agressivement les taux pour combattre l'inflation"),
]


def create_database():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── Tables ──────────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            csv_key TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            state TEXT NOT NULL,
            state_code TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE national_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            index_value REAL NOT NULL,
            index_sa REAL,
            yoy_change REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE city_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            index_value REAL NOT NULL,
            FOREIGN KEY (city_id) REFERENCES cities(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE market_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            event_name TEXT NOT NULL,
            description TEXT
        )
    """)

    # Indexes pour les performances
    cursor.execute("CREATE INDEX idx_national_date ON national_index(date)")
    cursor.execute("CREATE INDEX idx_national_year ON national_index(year)")
    cursor.execute("CREATE INDEX idx_city_prices_date ON city_prices(date)")
    cursor.execute("CREATE INDEX idx_city_prices_city ON city_prices(city_id)")
    cursor.execute("CREATE INDEX idx_city_prices_year ON city_prices(year)")

    # ── Insertion des villes ────────────────────────────────

    print("Insertion des villes...")
    for csv_key, (name, state, state_code) in CITY_MAPPING.items():
        cursor.execute(
            "INSERT INTO cities (csv_key, name, state, state_code) VALUES (?, ?, ?, ?)",
            (csv_key, name, state, state_code),
        )

    # ── Insertion des données nationales ────────────────────

    print("Téléchargement des données nationales...")
    national_rows = download_csv(NATIONAL_URL)

    print(f"  {len(national_rows)} mois de données nationales")
    prev_value = None
    prev_year = None
    yearly_cache = {}

    # Premier passage : stocker les valeurs par année pour calcul YoY
    for row in national_rows:
        date = row["Date"]
        year = int(date[:4])
        month = int(date[5:7])
        val = float(row["National-US"])
        key = (year, month)
        yearly_cache[key] = val

    for row in national_rows:
        date = row["Date"]
        year = int(date[:4])
        month = int(date[5:7])
        val = float(row["National-US"])
        sa = float(row["National-US-SA"]) if row.get("National-US-SA") else None

        # Calcul variation Year-over-Year
        yoy = None
        prev_key = (year - 1, month)
        if prev_key in yearly_cache and yearly_cache[prev_key] > 0:
            yoy = round((val - yearly_cache[prev_key]) / yearly_cache[prev_key] * 100, 2)

        cursor.execute(
            "INSERT INTO national_index (date, year, month, index_value, index_sa, yoy_change) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (date, year, month, val, sa, yoy),
        )

    # ── Insertion des données par ville ─────────────────────

    print("Téléchargement des données par ville...")
    city_rows = download_csv(CITIES_URL)

    # Récupérer les IDs des villes
    cursor.execute("SELECT id, csv_key FROM cities")
    city_id_map = {row[1]: row[0] for row in cursor.fetchall()}

    count = 0
    for row in city_rows:
        date = row["Date"]
        year = int(date[:4])
        month = int(date[5:7])

        for csv_key, city_id in city_id_map.items():
            val_str = row.get(csv_key, "")
            if val_str and val_str.strip():
                try:
                    val = float(val_str)
                    cursor.execute(
                        "INSERT INTO city_prices (city_id, date, year, month, index_value) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (city_id, date, year, month, val),
                    )
                    count += 1
                except ValueError:
                    pass

    print(f"  {count} points de données par ville insérés")

    # ── Insertion des événements de marché ──────────────────

    print("Insertion des événements de marché...")
    for date, name, desc in MARKET_EVENTS:
        cursor.execute(
            "INSERT INTO market_events (date, event_name, description) VALUES (?, ?, ?)",
            (date, name, desc),
        )

    conn.commit()
    conn.close()
    print(f"\nBase de données créée avec succès : {DB_PATH}")

    # Afficher un résumé
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for table in ["cities", "national_index", "city_prices", "market_events"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cursor.fetchone()[0]} lignes")
    conn.close()


if __name__ == "__main__":
    create_database()
