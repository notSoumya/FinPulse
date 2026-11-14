
import duckdb
from pathlib import Path

databases = [
    Path("data/synthetic/warehouse/finpulse_synthetic.duckdb"),
    Path("data/warehouse/finpulse.duckdb"),
]

for db_path in databases:
    print(f"\n{'=' * 60}")
    print(f"DATABASE: {db_path}")

    if not db_path.exists():
        print("NOT FOUND")
        continue

    con = duckdb.connect(str(db_path), read_only=True)

    tables = con.execute("SHOW TABLES").fetchall()

    print("\nTables:")

    for (table_name,) in tables:
        count = con.execute(
            f'SELECT COUNT(*) FROM main."{table_name}"'
        ).fetchone()[0]

        print(f"  {table_name}: {count} rows")

    con.close()
