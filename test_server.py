"""
Test script pour vérifier que les 3 outils du serveur MCP fonctionnent correctement
avec la base de données immobilière (Case-Shiller House Price Index).
Teste les fonctions directement (sans transport MCP).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import list_tables, describe_schema, run_query, is_safe_query

print("=" * 60)
print("TEST 1 : list_tables()")
print("=" * 60)
result = list_tables()
print(result)
assert "cities" in result
assert "national_index" in result
assert "city_prices" in result
assert "market_events" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 2 : describe_schema('cities')")
print("=" * 60)
result = describe_schema("cities")
print(result)
assert "name" in result
assert "state" in result
assert "state_code" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 3 : describe_schema('national_index')")
print("=" * 60)
result = describe_schema("national_index")
print(result)
assert "date" in result
assert "index_value" in result
assert "yoy_change" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 4 : describe_schema('city_prices') — clé étrangère")
print("=" * 60)
result = describe_schema("city_prices")
print(result)
assert "city_id" in result
assert "cities" in result  # FK vers cities
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 5 : describe_schema('nonexistent') — table inexistante")
print("=" * 60)
result = describe_schema("nonexistent")
print(result)
assert "n'existe pas" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 6 : run_query SELECT — villes")
print("=" * 60)
result = run_query("SELECT name, state_code FROM cities ORDER BY name LIMIT 5")
print(result)
assert "Atlanta" in result
assert "5 ligne(s)" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 7 : run_query SELECT — indice national")
print("=" * 60)
result = run_query("SELECT date, index_value, yoy_change FROM national_index ORDER BY date DESC LIMIT 5")
print(result)
assert "ligne(s)" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 8 : run_query JOIN — prix par ville")
print("=" * 60)
result = run_query("""
    SELECT c.name, cp.date, cp.index_value
    FROM city_prices cp
    JOIN cities c ON c.id = cp.city_id
    WHERE c.name = 'Miami'
    ORDER BY cp.date DESC
    LIMIT 3
""")
print(result)
assert "Miami" in result
assert "3 ligne(s)" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 9 : run_query WITH (CTE) — moyennes annuelles")
print("=" * 60)
result = run_query("""
    WITH yearly_avg AS (
        SELECT year, ROUND(AVG(index_value), 2) as avg_index
        FROM national_index
        GROUP BY year
    )
    SELECT * FROM yearly_avg
    ORDER BY year DESC
    LIMIT 5
""")
print(result)
assert "ligne(s)" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 10 : run_query — événements de marché")
print("=" * 60)
result = run_query("SELECT event_name, date FROM market_events ORDER BY date LIMIT 3")
print(result)
assert "ligne(s)" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 11 : SÉCURITÉ — DROP interdit")
print("=" * 60)
result = run_query("DROP TABLE cities")
print(result)
assert "ERREUR DE SÉCURITÉ" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 12 : SÉCURITÉ — DELETE interdit")
print("=" * 60)
result = run_query("DELETE FROM cities WHERE id = 1")
print(result)
assert "ERREUR DE SÉCURITÉ" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 13 : SÉCURITÉ — INSERT interdit")
print("=" * 60)
result = run_query("INSERT INTO cities (name) VALUES ('Hacker')")
print(result)
assert "ERREUR DE SÉCURITÉ" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 14 : SÉCURITÉ — UPDATE interdit")
print("=" * 60)
result = run_query("UPDATE cities SET name='Hacked' WHERE id=1")
print(result)
assert "ERREUR DE SÉCURITÉ" in result
print("\n✓ PASS\n")

print("=" * 60)
print("TEST 15 : is_safe_query edge cases")
print("=" * 60)
assert is_safe_query("SELECT * FROM cities") == True
assert is_safe_query("  select * from cities  ") == True
assert is_safe_query("WITH cte AS (SELECT 1) SELECT * FROM cte") == True
assert is_safe_query("EXPLAIN SELECT * FROM cities") == True
assert is_safe_query("DROP TABLE cities") == False
assert is_safe_query("SELECT * FROM cities; DROP TABLE cities") == False
assert is_safe_query("") == False
assert is_safe_query("   ") == False
# Injection via commentaire
assert is_safe_query("SELECT * FROM cities -- DROP TABLE cities") == True  # commentaire ignoré
assert is_safe_query("/* DROP */ SELECT * FROM cities") == True  # commentaire bloc ignoré
print("Tous les edge cases passent")
print("\n✓ PASS\n")

print("=" * 60)
print("TOUS LES 15 TESTS PASSENT ✓")
print("=" * 60)
