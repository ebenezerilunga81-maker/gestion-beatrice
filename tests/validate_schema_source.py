#!/usr/bin/env python3
"""Static guardrails for the GESTION BÉATRICE SQL draft.

This checks source-level invariants only. It is not a PostgreSQL parser and
must never be described as proof that a migration executes successfully.
"""
from pathlib import Path
import re
import sys

path = Path(sys.argv[1] if len(sys.argv) > 1 else "database/schema_v1_corrige.sql")
sql = path.read_text(encoding="utf-8")
errors = []

def require(condition, message):
    if not condition:
        errors.append(message)

require(sql.lstrip().startswith("-- GESTION BÉATRICE"), "Unexpected SQL file header")
require(re.search(r"(?im)^begin;\s*$", sql) is not None, "Missing BEGIN transaction")
require(re.search(r"(?im)^commit;\s*$", sql) is not None, "Missing COMMIT transaction")
require(sql.count("$$") % 2 == 0, "Odd number of $$ function delimiters")
require(not re.search(r"(?im)^\s*(?:as \$|\$;)\s*$", sql), "Malformed standalone dollar delimiter")

functions = list(re.finditer(r"(?is)create\s+function\s+([\w.]+)\s*\(", sql))
require(bool(functions), "No CREATE FUNCTION statements found")
for index, match in enumerate(functions):
    end = functions[index + 1].start() if index + 1 < len(functions) else len(sql)
    body = sql[match.start():end]
    name = match.group(1)
    if re.search(r"(?i)security\s+definer", body):
        require(re.search(r"(?i)set\s+search_path\s*=\s*''", body) is not None,
                f"{name}: SECURITY DEFINER lacks empty search_path")
        require(re.search(r"(?i)revoke\s+all\s+on\s+function", body) is not None,
                f"{name}: no explicit function EXECUTE revocation found before next function")

tables = re.findall(r"(?im)^alter table public\.([a-z_]+) enable row level security;", sql)
require(len(tables) == 14, f"Expected 14 RLS-enabled tables, found {len(tables)}")
require(len(set(tables)) == len(tables), "Duplicate RLS enable statement")
require("grant all privileges on all tables in schema public to service_role;" in sql,
        "Backend service_role grant missing")
require("grant all privileges on all tables in schema public to authenticated;" not in sql,
        "Authenticated role receives broad table privileges")
require("grant all privileges on all tables in schema public to anon;" not in sql,
        "Anon role receives broad table privileges")
require("create unique index school_year_one_active_idx" in sql,
        "Single-active-school-year constraint missing")
require("unique(student_id, school_year_id)" in sql,
        "One-enrollment-per-student-per-year constraint missing")
require("create table public.tickets" in sql and "payment_id uuid not null unique" in sql,
        "Unique ticket-per-payment constraint missing")

if errors:
    print("ÉCHEC — contrôles statiques :")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("OK — contrôles statiques du fichier SQL réussis.")
print("ATTENTION — ceci ne valide ni la syntaxe PostgreSQL complète, ni les politiques RLS en exécution.")
