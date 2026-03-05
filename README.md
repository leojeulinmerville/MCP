# Data Query Builder — Serveur MCP SQLite

**Projet Day 2 — Building Agentic Systems with MCP (PGE3)**

Serveur MCP Python qui permet à un agent IA (Claude, Gemini) d'interroger une base de données SQLite en langage naturel via 3 outils.

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
├── server.py          # Serveur MCP avec 3 outils + 1 ressource
├── create_db.py       # Script de création de la base de démo
├── demo.db            # Base SQLite (e-commerce : clients, produits, commandes)
└── README.md
```

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

### 3. Créer la base de données de démo

```bash
python create_db.py
```

## Test avec MCP Inspector

**Règle d'or du cours** : toujours tester dans l'Inspector AVANT de connecter à Claude/Gemini.

```bash
mcp dev server.py
```

Puis dans l'Inspector (http://localhost:6274) :

1. **Tools tab** → vérifier que `list_tables`, `describe_schema`, `run_query` apparaissent
2. Exécuter `list_tables` → voir les 4 tables
3. Exécuter `describe_schema` avec `table_name: "orders"` → voir le schéma
4. Exécuter `run_query` avec `sql: "SELECT * FROM customers LIMIT 3"` → voir les résultats
5. Tester la sécurité : `run_query` avec `sql: "DROP TABLE customers"` → doit être rejeté

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
- *"Montre-moi les 5 clients les plus récents"*
- *"Quel est le chiffre d'affaires par catégorie de produit ?"*

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

- **Connexion lecture seule** : `sqlite3.connect("file:demo.db?mode=ro", uri=True)`
- **Validation des requêtes** : seuls `SELECT` et `WITH` sont autorisés comme premier mot-clé
- **Liste noire explicite** : DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, ATTACH, DETACH...
- **Pas de print() sur stdout** : stdout est le transport MCP (slide 73)
- **Vérification d'existence des tables** avant description du schéma

## Exemples de requêtes que l'agent peut exécuter

```sql
-- Chiffre d'affaires total par client
SELECT c.first_name, c.last_name, SUM(o.total) as ca_total
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.status != 'cancelled'
GROUP BY c.id
ORDER BY ca_total DESC;

-- Produits les plus commandés
SELECT p.name, p.category, SUM(oi.quantity) as total_vendu
FROM products p
JOIN order_items oi ON p.id = oi.product_id
GROUP BY p.id
ORDER BY total_vendu DESC;

-- Commandes en attente avec détails client
SELECT o.id, c.first_name, c.last_name, o.order_date, o.total
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'pending';
```

## Auteurs

Projet réalisé dans le cadre du workshop **Building Agentic Systems with MCP** — PGE3.
