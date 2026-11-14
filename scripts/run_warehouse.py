import argparse
import json
import logging
import sys

from finpulse.warehouse.pipeline import run_warehouse_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="FinPulse Analytical Warehouse Pipeline")
    parser.add_argument(
        "--silver-path",
        default="data/lake/silver/transactions",
        help="Silver Delta table path",
    )
    parser.add_argument(
        "--db-path",
        default="data/warehouse/finpulse.duckdb",
        help="DuckDB database path",
    )
    parser.add_argument("--project-dir", default="dbt", help="dbt project directory")
    parser.add_argument("--profiles-dir", default="dbt", help="dbt profiles directory")

    args = parser.parse_args()

    results = run_warehouse_pipeline(
        silver_path=args.silver_path,
        db_path=args.db_path,
        project_dir=args.project_dir,
        profiles_dir=args.profiles_dir,
    )

    print("\n========== WAREHOUSE PIPELINE RESULTS ==========")
    print(json.dumps(results, indent=4))
    print("================================================")

    if not results.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
