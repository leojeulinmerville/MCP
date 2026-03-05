# Build Your First MCP Server in Python (FastMCP) - Day 1

This project is a minimal MCP server for use with Codex CLI.

## 1) Verify Python version

Python must be `>= 3.10`.

```powershell
python --version
```

## 2) Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Optional macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 3) Create venv and install dependencies

From the project folder:

```powershell
uv venv
.\.venv\Scripts\activate
uv pip install "mcp[cli]"
```

Optional macOS/Linux activation:

```bash
source .venv/bin/activate
```

## 4) Test with MCP Inspector

```powershell
mcp dev server.py
```

In MCP Inspector, verify:
- Tools include `hello`, `add`, `word_count`
- Resource includes `info:/server`
- `hello` returns `Hello, <name>! The server is working.`
- `add` returns `<a> + <b> = <sum>`
- `word_count` returns `Words: X, Chars: Y, Sentences: Z`

## 5) Connect from Codex CLI (stdio MCP)

Make sure Codex CLI is installed and available as `codex`.

Add the MCP server:

```powershell
codex mcp add my-server -- "<ABS_PATH_TO_PYTHON_EXE>" "<ABS_PATH_TO_server.py>"
```

Windows example:

```powershell
codex mcp add my-server -- "C:\Users\you\my-mcp-server\.venv\Scripts\python.exe" "C:\Users\you\my-mcp-server\server.py"
```

Placeholder notes:
- `<ABS_PATH_TO_PYTHON_EXE>` is your virtual environment interpreter path
- `<ABS_PATH_TO_server.py>` is the absolute path to this `server.py`

Confirm in Codex:
- Start Codex with `codex`
- Run `/mcp` in the TUI
- Confirm `my-server` is listed and enabled

Example prompts in Codex:
- `Use the my-server MCP tool hello with name "class".`
- `Use the my-server MCP tool word_count on: "Hello world. This is Day 1!"`

## 6) Common issues

- Wrong Python interpreter causes `ModuleNotFoundError: No module named 'mcp'`
- Paths must be absolute (do not use relative paths in `codex mcp add`)
- If tools/resources do not refresh, run `codex mcp list`, then restart Codex after MCP config changes


# Data Query Builder (Project B): Day 2

## Overview
Ce projet est un serveur d'outils Model Context Protocol (MCP) développé avec `FastMCP` en Python. Il agit comme un assistant de base de données intelligent, permettant de charger des fichiers CSV bruts, de les nettoyer, d'inspecter les schémas, de générer des requêtes SQL et de visualiser les résultats sous forme de graphiques HTML. Il a été conçu et certifié pour fonctionner avec **Gemini CLI**.

## Setup

Pour installer et exécuter ce projet localement, nous recommandons l'utilisation d'Anaconda (`conda`) ou d'un environnement virtuel Python standard (`venv`).

```bash
# 1. Activez votre environnement virtuel (ex: conda)
conda activate gemini_env

# 2. Installez les dépendances nécessaires
# Le paquet principal requis est `mcp[cli]` (FastMCP). `sqlite3` et `csv` sont inclus dans la librairie standard.
pip install mcp[cli]
```

## Gemini CLI Configuration

Pour que Gemini puisse communiquer avec ce serveur, ajoutez la configuration suivante dans le fichier `~/.gemini/settings.json` (ou `C:\Users\VotreNom\.gemini\settings.json` sous Windows) :

```json
{
  "mcpServers": {
    "data-query-builder": {
      "command": "python",
      "args": [
        "C:/chemin/absolu/vers/votre/dossier/Query_project/project_b.py"
      ]
    }
  }
}
```

## System Prompt Recommandé

L'utilisation d'un **Prompt Système strict** (Strategy 3: Expert Workflow) est vitale. Vous le trouverez dans le fichier `prompt.txt`. 
*Assurez-vous de le fournir à Gemini CLI lors de vos interactions pour garantir que l'agent respecte les étapes d'analyse (Phases 1 à 3) et n'hallucine aucune donnée !*

## Tools (9 outils)

| Tool | Paramètres Clés | Description |
| :--- | :--- | :--- |
| `preview_table` | `table_name`, `rows` | Affiche un aperçu rapide (head) d'une table sans faire de lourdes requêtes. |
| `clean_csv` | `input_path`, `output_path` | Lit un CSV, détecte automatiquement son séparateur et écrit une version propre (virgules, UTF-8). |
| `load_csv` | `file_path`, `table_name` | Charge le contenu d'un CSV (propre) dans une nouvelle table SQLite mémoire. Détecte les types. |
| `list_tables` | *(aucun)* | Liste toutes les tables SQLite actuellement en mémoire avec leur nombre de lignes. |
| `describe_schema` | *(aucun)* | Renvoie toutes les tables, ainsi que le nom et le type de toutes leurs colonnes. |
| `get_unique_values` | `table_name`, `column` | Retourne la liste unique/distincte des entrées d'une colonne (parfait pour le requêtage de catégories). |
| `get_statistics` | `table_name`, `column` | Retourne les statistiques mathématiques de base (Min, Max, Moyenne, Count). |
| `run_query` | `sql`, `limit` | Exécute des requêtes de lecture (SELECT) complexes, rejette automatiquement (DROP, DELETE, UPDATE). |
| `visualize_data` | `sql_query`, `chart_type`, `x_column`, `y_column`, `output_html_path` | Exécute une requête et génère un graphique (Chart.js) dans un fichier HTML interactif. |

## Resources

*   `db://schema` : Expose le schéma de la base de données actuelle au format JSON.
*   `db://query-history` : Expose l'historique complet de toutes les requêtes exécutées durant la session courante.

## Limitations et Recommandations (Negative Constraints)

Pour des raisons de sécurité et de performances, des limites strictes doivent être imposées dans le prompt donné à Gemini CLI :
1.  **Read-Only DB** : L'outil `run_query` et la génération de graphiques bloquent explicitement l'écriture SQL. Pensez à l'exiger aussi dans le prompt.
2.  **Usage Conditionnel** : L'agent ne doit **pas** se sentir obligé d'utiliser tous les outils pour des tâches simples.
3.  **No Native Local Parsing** : Gemini a tendance à parser lui-même le dossier de travail. Il est impératif d'interdire cette pratique (via les negative prompts) pour garantir le flux d'orchestration de nos outils `clean_csv` et `load_csv`.
4.  **No Hallucination** : Le prompt doit préciser que l'agent ne doit s'appuyer **que** sur les données sortant des JSON renvoyés par les outils.

## 4 Cas d'Usage (Utilisant `sample_data.csv`)

Voici 4 exemples de requêtes (cas d'usage réels) que vous pouvez envoyer à Gemini CLI, conçues pour déclencher l'orchestration avancée des outils du serveur MCP avec le fichier `sample_data.csv` (qui contient des données de ventes) :

### Cas 1 : Ingestion Sécurisée et Aperçu (Discovery)
**Prompt utilisateur :**  
> *"Je veux analyser mon fichier `sample_data.csv`. Commence par le nettoyer pour être sûr du format, puis charge-le dans une table nommée `sales`. Affiche-moi ensuite un aperçu des 3 premières lignes pour vérifier que tout est correct."*
**Comportement attendu :** Gemini appelle `clean_csv` -> `load_csv` -> `preview_table`.

### Cas 2 : Analyse Catégorielle Exploratoire (Analysis)
**Prompt utilisateur :**  
> *"Dans la table `sales` que nous venons de charger, quelles sont les régions uniques ? et quelles sont les catégories uniques de produits ?"*
**Comportement attendu :** Gemini vérifie le schéma si nécessaire, puis appelle `get_unique_values` pour la colonne "region" et `get_unique_values` pour la colonne "category".

### Cas 3 : Statistiques Mathématiques Détaillées (Statistics)
**Prompt utilisateur :**  
> *"Donne-moi un résumé statistique complet du prix (price) et de la quantité (quantity) dans la table `sales`. Quel est le prix moyen et la quantité totale en stock (MAX) ?"*
**Comportement attendu :** L'agent utilise intelligemment l'outil `get_statistics` sur les deux colonnes numériques au lieu d'écrire de multiples requêtes SQL manuelles.

### Cas 4 : Requête Complexe et Visualisation Interactive (Synthesis & Visualization)
**Prompt utilisateur :**  
> *"Écris une requête SQL pour obtenir le revenu total (price * quantity) par catégorie dans la table `sales`. Ensuite, génère un graphique en barres (bar chart) de ces revenus et sauvegarde-le sous `revenue_chart.html`."*
**Comportement attendu :** L'agent réfléchit à la requête, puis appelle directement `visualize_data` en lui passant la requête SQL `SELECT category, sum(price*quantity) as revenue...`, `bar`, `category`, `revenue`, et le chemin du fichier de sortie. Il vous répondra avec un lien vers le fichier HTML interactif.
