# Data Query Builder — Serveur MCP SQLite

**Projet Day 2 — Building Agentic Systems with MCP (PGE3)**

Serveur MCP Python qui permet à un agent IA (Claude, Gemini) d'interroger une base de données SQLite contenant le **S&P/Case-Shiller U.S. National Home Price Index** — des données time series sur l'évolution des prix immobiliers américains depuis 1975.

## Concepts du cours appliqués

| Concept (Day 1)                        | Application dans ce projet                                                   |
|----------------------------------------|------------------------------------------------------------------------------|
| **ReAct loop** (Think → Act → Observe) | L'agent découvre les tables, puis le schéma, puis exécute des requêtes       |
| **Tool descriptions = prompt engineering** | Chaque outil a une docstring détaillée qui guide le LLM                   |
| **Negative instructions**              | `run_query` interdit explicitement DROP, DELETE, INSERT, UPDATE, etc.         |
| **Capability fencing**                 | Connexion SQLite en mode lecture seule (`?mode=ro`)                          |
| **Security (allowlist)**               | Validation des requêtes : seuls SELECT et WITH sont autorisés                |
| **Blast radius / measure twice**       | Les opérations destructrices sont bloquées au niveau code, pas juste prompt  |

## Architecture

```
data-query-builder/
├── server.py                        # Serveur MCP avec 3 outils + 1 ressource
├── create_db.py                     # Script de création de la base (télécharge les CSV)
├── housing.db                       # Base SQLite (Case-Shiller House Price Index)
├── test_server.py                   # Tests unitaires (15 tests)
├── claude_desktop_config_example.json
└── README.md
```

## La base de données

**Source** : S&P/Case-Shiller U.S. National Home Price Index (via [datasets/house-prices-us](https://github.com/datasets/house-prices-us))

| Table            | Lignes | Description                                              |
|------------------|--------|----------------------------------------------------------|
| `cities`         | 20     | Les 20 métropoles du Case-Shiller Index (nom, état)      |
| `national_index` | 595    | Indice national mensuel depuis 1975 (avec variation YoY) |
| `city_prices`    | 5 756  | Indice mensuel par ville depuis 1987                     |
| `market_events`  | 14     | Événements économiques marquants (crises, bulles, etc.)  |

## Les 3 outils MCP

| Outil             | Description                                          | Paramètres       |
|-------------------|------------------------------------------------------|------------------|
| `list_tables`     | Liste toutes les tables avec leur nombre de lignes   | Aucun            |
| `describe_schema` | Décrit le schéma d'une table (colonnes, types, FK)   | `table_name: str`|
| `run_query`       | Exécute une requête SQL SELECT (lecture seule)        | `sql: str`       |

**Ressource** : `info://server` — métadonnées du serveur (version, outils disponibles)

## Installation

### 1. Créer le répertoire et l'environnement virtuel

```bash
cd data-query-builder
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 2. Installer les dépendances

```bash
pip install "mcp[cli]"
```

### 3. Créer la base de données

```bash
python create_db.py
```

Ce script télécharge automatiquement les CSV depuis GitHub et crée `housing.db`.

## Test avec MCP Inspector

**Règle d'or du cours** : toujours tester dans l'Inspector AVANT de connecter à Claude/Gemini.

```bash
mcp dev server.py
```

Puis dans l'Inspector (http://localhost:6274) :

1. **Tools tab** → vérifier que `list_tables`, `describe_schema`, `run_query` apparaissent
2. Exécuter `list_tables` → voir les 4 tables
3. Exécuter `describe_schema` avec `table_name: "national_index"` → voir le schéma
4. Exécuter `run_query` avec `sql: "SELECT * FROM national_index ORDER BY date DESC LIMIT 5"` → voir les résultats
5. Tester la sécurité : `run_query` avec `sql: "DROP TABLE cities"` → doit être rejeté

## Tests automatisés

```bash
python test_server.py
```

15 tests couvrant : list_tables, describe_schema (valide + invalide), run_query (SELECT, JOIN, CTE), événements de marché, sécurité (DROP, DELETE, INSERT, UPDATE bloqués), edge cases `is_safe_query`.

## Connexion à Claude Desktop

Ajouter dans `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "data-query-builder": {
      "command": "/chemin/absolu/.venv/bin/python",
      "args": ["/chemin/absolu/data-query-builder/server.py"]
    }
  }
}
```

> **Windows** : utiliser `\\` dans les chemins et `.venv\\Scripts\\python.exe`

Redémarrer Claude Desktop, puis demander :
- *"Quelles tables sont dans la base ?"*
- *"Comment les prix immobiliers ont-ils évolué depuis 2008 ?"*
- *"Quelle ville a connu la plus forte hausse entre 2020 et 2023 ?"*

## Connexion à Gemini CLI

Ajouter dans `~/.gemini/settings.json` :

```json
{
  "mcpServers": {
    "data-query-builder": {
      "command": "python",
      "args": ["/chemin/absolu/data-query-builder/server.py"]
    }
  }
}
```

## Sécurité

Le serveur applique les principes de sécurité du cours (slide 68) :

- **Connexion lecture seule** : `sqlite3.connect("file:housing.db?mode=ro", uri=True)`
- **Validation des requêtes** : seuls `SELECT` et `WITH` sont autorisés comme premier mot-clé
- **Liste noire explicite** : DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, ATTACH, DETACH...
- **Pas de print() sur stdout** : stdout est le transport MCP (slide 73)
- **Vérification d'existence des tables** avant description du schéma

## Exemples de requêtes que l'agent peut exécuter

```sql
-- Évolution annuelle des prix nationaux
SELECT year, ROUND(AVG(index_value), 2) as avg_index, ROUND(AVG(yoy_change), 2) as avg_yoy
FROM national_index
GROUP BY year
ORDER BY year;

-- Top 5 des villes avec le plus haut indice (dernière date disponible)
SELECT c.name, c.state_code, cp.index_value, cp.date
FROM city_prices cp
JOIN cities c ON c.id = cp.city_id
WHERE cp.date = (SELECT MAX(date) FROM city_prices)
ORDER BY cp.index_value DESC
LIMIT 5;

-- Impact de la crise 2008 : prix avant et après par ville
WITH before AS (
    SELECT city_id, AVG(index_value) as avg_before
    FROM city_prices WHERE year = 2006 GROUP BY city_id
),
after AS (
    SELECT city_id, AVG(index_value) as avg_after
    FROM city_prices WHERE year = 2012 GROUP BY city_id
)
SELECT c.name, ROUND(b.avg_before, 2) as prix_2006,
       ROUND(a.avg_after, 2) as prix_2012,
       ROUND((a.avg_after - b.avg_before) / b.avg_before * 100, 2) as variation_pct
FROM before b
JOIN after a ON b.city_id = a.city_id
JOIN cities c ON c.id = b.city_id
ORDER BY variation_pct;

-- Événements économiques et leur contexte
SELECT date, event_name, description FROM market_events ORDER BY date;
```

## Auteurs

Projet réalisé dans le cadre du workshop **Building Agentic Systems with MCP** — PGE3.
