# FastMCP Training Projects

Ce dépôt regroupe les projets réalisés lors de la formation sur le Model Context Protocol (MCP) avec le framework Python **FastMCP**.

---

## Day 1 : Build Your First MCP Server

Ce projet est un serveur MCP minimaliste conçu pour comprendre les bases de FastMCP et l'interaction avec des clients comme MCP Inspector et Gemini CLI.

### 1. Prérequis & Installation

Python doit être en version `>= 3.10`.

```powershell
# Vérifier la version de Python
python --version
```

**Installation de `uv` (Gestionnaire de paquets ultra-rapide)** :
*   **Windows PowerShell** :
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
*   **macOS/Linux** :
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

**Création de l'environnement virtuel** :
```powershell
# Depuis le dossier du projet Day 1
uv venv
.\.venv\Scripts\activate
uv pip install "mcp[cli]"
```

### 2. Tester avec MCP Inspector (Interface Web)

Lancez l'interface de test visuelle :
```powershell
mcp dev server.py
```
Vérifiez que les outils `hello`, `add`, et `word_count` fonctionnent correctement, ainsi que la ressource `info:/server`.

### 3. Connecter depuis Gemini CLI (stdio MCP)

Ajoutez le serveur à Gemini CLI en insérant cette configuration dans `~/.gemini/settings.json` (ou `C:\Users\VotreNom\.gemini\settings.json` sous Windows) :
```json
{
  "mcpServers": {
    "my-server": {
      "command": "C:/Users/you/my-mcp-server/.venv/Scripts/python.exe",
      "args": [
        "C:/Users/you/my-mcp-server/server.py"
      ]
    }
  }
}
```

*   Lancez Gemini CLI et vérifiez que `my-server` est activé et que les outils sont disponibles.
*   **Prompt d'exemple :** *"Utilise l'outil MCP `hello` avec le nom 'Alice', puis l'outil `word_count` avec la phrase 'Hello world'."*

---

## Day 2 : Data Query Builder (Project B)

Ce projet est la mise en pratique avancée des concepts MCP. C'est un **assistant de base de données intelligent** qui permet de charger des fichiers CSV, d'inspecter les schémas, de générer des requêtes SQL et de créer des visualisations HTML interactives, le tout orchestré par **Gemini CLI**.

### Setup (Environnement Anaconda)

Pour Project B, nous recommandons l'utilisation d'Anaconda (`conda`) :

```bash
# 1. Activez votre environnement virtuel
conda activate gemini_env

# 2. Installez les dépendances nécessaires
pip install mcp[cli]
# sqlite3 et csv sont déjà inclus dans Python standard.
```

### Gemini CLI Configuration

Pour que Gemini puisse communiquer avec ce serveur, ajoutez la configuration suivante dans le fichier `~/.gemini/settings.json` (ou `C:\Users\VotreNom\.gemini\settings.json` sous Windows). **Utilisez des chemins absolus !**

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

### Prompt Système & Contraintes (CRITICAL)

L'utilisation d'un **Prompt Système strict** (*Strategy 3: Expert Workflow*) est vitale pour ce projet. Le contenu exact à fournir à Gemini se trouve dans le fichier `prompt.txt`. 

**Pourquoi ces contraintes sont-elles importantes ?**
1.  **Read-Only DB** : Empêche formellement l'agent d'exécuter des requêtes destructives (`DROP`, `DELETE`, `UPDATE`).
2.  **No Native Local Parsing** : Interdit à Gemini d'utiliser ses propres capacités pour lire le dossier local. Il *doit* utiliser les outils MCP (`load_csv`, `clean_csv`) pour garantir le bon flux d'orchestration.
3.  **No Hallucination** : Force l'agent à s'appuyer uniquement sur les retours JSON des outils.
4.  **Usage Intelligent** : Empêche l'agent d'appeler inutilement tous ses outils pour des questions simples.

### Outils Exposés (9 Tools)

| Tool | Paramètres Clés | Description |
| :--- | :--- | :--- |
| `preview_table` | `table_name`, `rows` | Affiche un aperçu rapide (head) d'une table sans faire de lourdes requêtes. |
| `clean_csv` | `input_path`, `out_path` | Lit un CSV, détecte automatiquement son séparateur et écrit une version propre (virgules, UTF-8). |
| `load_csv` | `file_path`, `table_name` | Charge le contenu d'un CSV dans une table SQLite mémoire et détecte les types. |
| `list_tables` | *(aucun)* | Liste toutes les tables SQLite actuellement en mémoire avec leur nombre de lignes. |
| `describe_schema`| *(aucun)* | Renvoie toutes les tables, ainsi que le nom et le type de toutes leurs colonnes. |
| `get_unique_values`| `table_name`, `column`| Retourne la liste unique des entrées d'une colonne (parfait pour l'analyse catégorielle). |
| `get_statistics` | `table_name`, `column`| Retourne les statistiques mathématiques de base (Min, Max, Moyenne, Count). |
| `run_query` | `sql`, `limit` | Exécute des requêtes SQL de lecture (SELECT) complexes. |
| `visualize_data` | `sql`, `type`, `x`, `y`, `out` | Exécute une requête et génère un graphique (Chart.js) dans un fichier HTML interactif externe. |

*(Le projet expose également les ressources `db://schema` et `db://query-history`)*

### 4 Cas d'Usage Pratiques (avec `movies.csv`)

Testez la puissance de l'orchestration en envoyant ces prompts complets à Gemini CLI après avoir chargé le prompt système :

**Cas 1 : Ingestion Sécurisée et Aperçu (Discovery)**
> *"Je veux analyser le fichier `movies.csv`. Commence par le nettoyer pour être sûr du format, puis charge-le dans une table nommée `movies`. Affiche-moi ensuite un aperçu des 5 premières lignes pour vérifier que tout est correct."*

*Action de l'agent : `clean_csv` -> `load_csv` -> `preview_table`*

Résultat attendu (extrait) :
```
| title       | release_date | vote_average | revenue     | runtime |
|-------------|--------------|--------------|-------------|---------|
| Toy Story   | 1995-10-30   | 7.7          | 373554033   | 81.0    |
| Jumanji     | 1995-12-15   | 6.9          | 262797249   | 104.0   |
| Heat        | 1995-12-15   | 7.7          | 187436818   | 170.0   |
| Se7en       | 1995-09-22   | 8.1          | 327311859   | 127.0   |
| Braveheart  | 1995-05-24   | 7.7          | 210000000   | 177.0   |
```

**Cas 2 : Analyse Catégorielle Exploratoire (Analysis)**
> *"Dans la table `movies`, quelles sont les langues originales disponibles ? Donne-moi aussi la liste des statuts de sortie uniques (colonne `status`)."*

*Action de l'agent : `describe_schema` (optionnel) -> `get_unique_values` (original_language) -> `get_unique_values` (status)*

Résultat attendu :
```
original_language (top valeurs) : en, fr, it, de, zh, ja, es, ko, ...
status (valeurs uniques) : Released, Rumored, Post Production, In Production, Planned, Canceled
```

**Cas 3 : Statistiques Mathématiques Détaillées (Statistics)**
> *"Donne-moi un résumé statistique complet de la note moyenne (vote_average) et du revenu (revenue) dans la table `movies`. Quel est le film le mieux noté et le revenu maximum enregistré ?"*

*Action de l'agent : `get_statistics` (vote_average) -> `get_statistics` (revenue)*

Résultat attendu :
```
vote_average → Min: 0.0 | Max: 10.0 | Moyenne: 5.62 | Count: 45573
revenue      → Min: 0   | Max: 2787965087 | Moyenne: 11462442 | Count: 45573
```

**Cas 4 : Requête Complexe et Visualisation Interactive (Synthesis & Viz)**
> *"Écris une requête SQL pour obtenir les 10 films anglais avec le plus haut revenu dans la table `movies` (uniquement ceux dont le revenu est supérieur à 0). Génère ensuite un graphique en barres horizontales et sauvegarde-le sous `C:/votre/chemin/top10_movies_revenue.html`."*

*Action de l'agent : `run_query` -> `visualize_data`*

Résultat attendu (requête SQL générée) :
```sql
SELECT title, revenue
FROM movies
WHERE original_language = 'en' AND revenue > 0
ORDER BY revenue DESC
LIMIT 10;
```
```
| title                              | revenue        |
|------------------------------------|----------------|
| Avatar                             | 2787965087     |
| Titanic                            | 1845034188     |
| The Avengers                       | 1519557910     |
| The Dark Knight                    | 1004558444     |
| Star Wars: The Force Awakens       | 936662225      |
```
L'agent génère ensuite un fichier `top10_movies_revenue.html` avec un graphique Chart.js interactif.
