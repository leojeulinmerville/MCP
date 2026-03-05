"""
Data Query Builder — Serveur MCP pour interagir avec une base SQLite.

Ce serveur expose 3 outils MCP via FastMCP :
  - list_tables   : lister toutes les tables de la base
  - describe_schema : décrire le schéma complet d'une table (colonnes, types, contraintes)
  - run_query     : exécuter une requête SQL SELECT (lecture seule)

Et 1 ressource :
  - info://server  : métadonnées du serveur

Concepts du cours appliqués :
  - ReAct loop     : Think → Act → Observe (l'agent choisit quel outil appeler)
  - Tool descriptions = prompt engineering (descriptions claires pour guider le LLM)
  - Negative instructions (interdire DROP, DELETE, etc.)
  - Capability fencing (lecture seule, pas d'écriture)
  - Security : requêtes paramétrées, validation des entrées
"""

import json
import os
import re
import sqlite3
import sys

from mcp.server.fastmcp import FastMCP

# ── Configuration ───────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.db")

mcp = FastMCP("data-query-builder")

# ── Helpers ─────────────────────────────────────────────────────


def get_connection() -> sqlite3.Connection:
    """Ouvre une connexion SQLite en mode lecture seule."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Base de données introuvable : {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def is_safe_query(sql: str) -> bool:
    """
    Vérifie qu'une requête SQL est sûre (lecture seule).
    INTERDIT : DROP, DELETE, INSERT, UPDATE, ALTER, CREATE, ATTACH, DETACH, PRAGMA (écriture).
    Pattern de sécurité du cours : negative instructions + allowlist.
    """
    # Normaliser : supprimer commentaires et espaces excessifs
    cleaned = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)  # commentaires --
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)  # commentaires /* */
    cleaned = cleaned.strip().upper()

    # Liste noire explicite (negative instructions du cours)
    dangerous_keywords = [
        "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
        "ATTACH", "DETACH", "REPLACE", "TRUNCATE", "GRANT", "REVOKE",
    ]
    # Vérifier que le premier mot-clé est SELECT ou WITH (CTE)
    first_word = cleaned.split()[0] if cleaned.split() else ""
    if first_word not in ("SELECT", "WITH", "EXPLAIN"):
        return False

    # Vérifier qu'aucun mot-clé dangereux n'apparaît
    for keyword in dangerous_keywords:
        # Recherche en tant que mot entier pour éviter les faux positifs
        if re.search(rf"\b{keyword}\b", cleaned):
            return False

    return True


# ── Outils MCP ──────────────────────────────────────────────────


@mcp.tool()
def list_tables() -> str:
    """
    Liste toutes les tables de la base de données avec leur nombre de lignes.

    Utilise cet outil EN PREMIER pour découvrir quelles tables existent
    avant de construire une requête SQL. Ne prend aucun paramètre.

    Retourne un tableau formaté avec le nom de chaque table et son nombre de lignes.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]

        if not tables:
            return "Aucune table trouvée dans la base de données."

        results = []
        for table_name in tables:
            cursor.execute(f'SELECT COUNT(*) as count FROM "{table_name}"')
            count = cursor.fetchone()["count"]
            results.append(f"  - {table_name} ({count} lignes)")

        return "Tables disponibles :\n" + "\n".join(results)
    finally:
        conn.close()


@mcp.tool()
def describe_schema(table_name: str) -> str:
    """
    Décrit le schéma complet d'une table : colonnes, types, clés primaires et clés étrangères.

    Utilise cet outil APRÈS list_tables pour comprendre la structure d'une table
    spécifique avant d'écrire une requête SQL. Donne le nom exact de la table.

    Args:
        table_name: Le nom exact de la table à décrire (ex: "customers", "orders").
                    DOIT correspondre exactement à un nom retourné par list_tables.

    Retourne le schéma détaillé de la table avec colonnes, types, contraintes
    et clés étrangères.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Vérifier que la table existe
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            available = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_list = ", ".join(r["name"] for r in available)
            return (
                f"Erreur : la table '{table_name}' n'existe pas.\n"
                f"Tables disponibles : {table_list}"
            )

        # Récupérer les infos des colonnes
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = cursor.fetchall()

        # Récupérer les clés étrangères
        cursor.execute(f'PRAGMA foreign_key_list("{table_name}")')
        fkeys = cursor.fetchall()

        # Récupérer le SQL de création pour les contraintes CHECK
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        create_sql = cursor.fetchone()["sql"]

        # Formater le résultat
        lines = [f"Schema de la table '{table_name}' :", ""]
        lines.append(f"{'Colonne':<20} {'Type':<15} {'PK':<5} {'Nullable':<10} {'Défaut'}")
        lines.append("-" * 70)

        for col in columns:
            pk = "OUI" if col["pk"] else ""
            nullable = "NON" if col["notnull"] else "OUI"
            default = str(col["dflt_value"]) if col["dflt_value"] is not None else ""
            lines.append(
                f"{col['name']:<20} {col['type']:<15} {pk:<5} {nullable:<10} {default}"
            )

        if fkeys:
            lines.append("")
            lines.append("Clés étrangères :")
            for fk in fkeys:
                lines.append(
                    f"  - {fk['from']} → {fk['table']}.{fk['to']}"
                )

        lines.append("")
        lines.append("SQL de création :")
        lines.append(create_sql)

        return "\n".join(lines)
    finally:
        conn.close()


@mcp.tool()
def run_query(sql: str) -> str:
    """
    Exécute une requête SQL SELECT sur la base de données et retourne les résultats formatés.

    UNIQUEMENT les requêtes SELECT et WITH (CTE) sont autorisées.
    Les requêtes d'écriture (INSERT, UPDATE, DELETE, DROP, etc.) sont INTERDITES
    et seront rejetées avec un message d'erreur.

    Conseils pour construire ta requête :
    - Appelle d'abord list_tables pour voir les tables disponibles
    - Appelle describe_schema pour comprendre les colonnes et les relations
    - Utilise des JOIN pour combiner les tables via les clés étrangères
    - Limite les résultats avec LIMIT si tu ne connais pas la taille des données

    Args:
        sql: La requête SQL SELECT à exécuter. DOIT commencer par SELECT ou WITH.
             Exemples valides :
               - "SELECT * FROM customers LIMIT 5"
               - "SELECT c.first_name, COUNT(o.id) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.id"

    Retourne les résultats sous forme de tableau formaté, ou un message d'erreur
    si la requête est invalide ou échoue.
    """
    # ── Validation de sécurité ──
    if not sql or not sql.strip():
        return "Erreur : requête vide. Fournis une requête SQL SELECT valide."

    if not is_safe_query(sql):
        return (
            "ERREUR DE SÉCURITÉ : seules les requêtes SELECT et WITH sont autorisées.\n"
            "Les opérations d'écriture (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE) "
            "sont INTERDITES.\n"
            "Reformule ta requête en utilisant uniquement SELECT."
        )

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

        if not rows:
            return "La requête n'a retourné aucun résultat."

        # Récupérer les noms de colonnes
        col_names = [description[0] for description in cursor.description]

        # Calculer les largeurs de colonnes
        widths = [len(name) for name in col_names]
        str_rows = []
        for row in rows:
            str_row = [str(val) if val is not None else "NULL" for val in row]
            str_rows.append(str_row)
            for i, val in enumerate(str_row):
                widths[i] = max(widths[i], len(val))

        # Formater le tableau
        header = " | ".join(name.ljust(widths[i]) for i, name in enumerate(col_names))
        separator = "-+-".join("-" * w for w in widths)

        lines = [header, separator]
        for str_row in str_rows:
            line = " | ".join(val.ljust(widths[i]) for i, val in enumerate(str_row))
            lines.append(line)

        lines.append(f"\n({len(rows)} ligne(s) retournée(s))")

        return "\n".join(lines)

    except sqlite3.Error as e:
        return f"Erreur SQL : {e}\nVérifie la syntaxe de ta requête et les noms de tables/colonnes."
    finally:
        conn.close()


# ── Ressource MCP ───────────────────────────────────────────────


@mcp.resource("info://server")
def server_info() -> str:
    """Métadonnées du serveur et informations de version."""
    return json.dumps(
        {
            "name": "data-query-builder",
            "version": "1.0.0",
            "description": "Serveur MCP pour interroger une base SQLite via des requêtes SQL",
            "tools": ["list_tables", "describe_schema", "run_query"],
            "database": os.path.basename(DB_PATH),
            "security": "Lecture seule — les requêtes d'écriture sont bloquées",
        },
        indent=2,
        ensure_ascii=False,
    )


# ── Point d'entrée ──────────────────────────────────────────────

if __name__ == "__main__":
    # IMPORTANT : ne jamais utiliser print() — stdout est le transport MCP.
    # Pour le debug : print("debug", file=sys.stderr)
    print("Démarrage du serveur data-query-builder...", file=sys.stderr)
    mcp.run()
