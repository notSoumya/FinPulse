"""
Ingest Synthetic Financial Data into FinPulse Main Lake & Warehouse.

This script populates the default platform storage locations:
- Bronze: data/lake/bronze
- Silver: data/lake/silver/transactions (Delta Lake)
- Checkpoints: data/lake/checkpoints/silver_checkpoint.json
- Quarantine: data/lake/quarantine/rejected_transactions
- Warehouse: data/warehouse/finpulse.duckdb
- Runs dbt transformations and data quality tests

Once run, you can immediately start the Streamlit dashboard:
    streamlit run dashboard/app.py
"""

import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project root to sys.path so tests modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dbt.cli.main import dbtRunner

from finpulse.bronze.storage import BronzeStorage
from finpulse.common.models import Transaction
from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.manual_parser import parse_manual
from finpulse.ingestion.parsers.sms_parser import parse_bank_sms
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv
from finpulse.processing.bronze_reader import BronzeReader
from finpulse.processing.checkpoint import CheckpointManager
from finpulse.processing.merchant_normalizer import MerchantNormalizer
from finpulse.processing.quarantine import QuarantineManager
from finpulse.processing.silver_pipeline import SilverPipeline
from finpulse.silver.writer import SilverWriter
from finpulse.warehouse.loader import WarehouseLoader
from tests.fixtures.synthetic_data.generate_synthetic_data import (
    SyntheticConfig,
    generate_all_synthetic_files,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def ingest_synthetic_into_main():
    manifest_path = Path("data/synthetic/manifest.json")
    if not manifest_path.exists():
        logger.info("Generating fresh synthetic dataset...")
        generate_all_synthetic_files(SyntheticConfig())

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    bronze_dir = Path("data/lake/bronze")
    silver_dir = Path("data/lake/silver/transactions")
    checkpoint_file = Path("data/lake/checkpoints/silver_checkpoint.json")
    quarantine_dir = Path("data/lake/quarantine/rejected_transactions")
    warehouse_db = Path("data/warehouse/finpulse.duckdb")

    logger.info("--------------------------------------------------")
    logger.info("Step 1: Ingesting synthetic data into Bronze storage...")
    logger.info("--------------------------------------------------")

    bronze_storage = BronzeStorage(bronze_dir)
    primary_user = manifest["primary_user"]
    secondary_user = manifest["secondary_user"]
    all_txs: list[Transaction] = []

    # 1. UPI CSV
    upi_txs = parse_upi_csv(manifest["files"]["upi_csv"], user_id=primary_user)
    with open(manifest["files"]["upi_csv"], encoding="utf-8") as f:
        lines = f.readlines()[1:]
        for i, line in enumerate(lines):
            if "synthetic_user_2" in line or "U2" in line:
                upi_txs[i].user_id = secondary_user

    all_txs.extend(upi_txs)
    for tx in upi_txs:
        bronze_storage.write_event({
            "event_id": f"evt_{tx.transaction_id}",
            "event_timestamp": tx.transaction_timestamp.isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": tx.model_dump(mode="json"),
        })

    # 2. Card PDF
    card_txs = parse_card_pdf(manifest["files"]["card_pdf"], user_id=primary_user)
    for tx in card_txs:
        is_u2_amount = tx.amount in [Decimal("1850.00"), Decimal("620.00"), Decimal("410.00")]
        if is_u2_amount and tx.transaction_timestamp.month in [10, 11]:
            tx.user_id = secondary_user

    all_txs.extend(card_txs)
    for tx in card_txs:
        bronze_storage.write_event({
            "event_id": f"evt_{tx.transaction_id}",
            "event_timestamp": tx.transaction_timestamp.isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": tx.model_dump(mode="json"),
        })

    # 3. Bank SMS
    with open(manifest["files"]["bank_sms_json"], encoding="utf-8") as f:
        sms_raw = json.load(f)
    sms_txs = []
    for r in sms_raw:
        ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        tx = parse_bank_sms(r["message"], r["user_id"], ts, r.get("reference_id"))
        sms_txs.append(tx)
    all_txs.extend(sms_txs)
    for tx in sms_txs:
        bronze_storage.write_event({
            "event_id": f"evt_{tx.transaction_id}",
            "event_timestamp": tx.transaction_timestamp.isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": tx.model_dump(mode="json"),
        })

    # 4. Manual entries
    with open(manifest["files"]["manual_json"], encoding="utf-8") as f:
        man_raw = json.load(f)
    man_txs = [parse_manual(r) for r in man_raw]
    all_txs.extend(man_txs)
    for tx in man_txs:
        bronze_storage.write_event({
            "event_id": f"evt_{tx.transaction_id}",
            "event_timestamp": tx.transaction_timestamp.isoformat(),
            "schema_version": "1.0",
            "event_type": "TRANSACTION_CREATED",
            "payload": tx.model_dump(mode="json"),
        })

    logger.info("Bronze layer populated with %d source transactions.", len(all_txs))

    logger.info("--------------------------------------------------")
    logger.info("Step 2: Running Silver Pipeline & Delta Lake writer...")
    logger.info("--------------------------------------------------")

    silver_pipeline = SilverPipeline(
        bronze_reader=BronzeReader(bronze_dir),
        merchant_normalizer=MerchantNormalizer("config/merchant_mapping.json"),
        quarantine_manager=QuarantineManager(quarantine_dir),
        silver_writer=SilverWriter(silver_dir),
        checkpoint_manager=CheckpointManager(checkpoint_file),
    )
    silver_stats = silver_pipeline.run()
    logger.info("Silver pipeline completed: %s", silver_stats)

    logger.info("--------------------------------------------------")
    logger.info("Step 3: Syncing Silver Delta Lake to DuckDB...")
    logger.info("--------------------------------------------------")

    loader = WarehouseLoader(silver_path=silver_dir, db_path=warehouse_db)
    rows_synced = loader.sync()
    logger.info("DuckDB warehouse synchronized: %d records loaded.", rows_synced)

    logger.info("--------------------------------------------------")
    logger.info("Step 4: Executing dbt transformations & tests...")
    logger.info("--------------------------------------------------")

    os.environ["FINPULSE_DUCKDB_PATH"] = str(warehouse_db.resolve())
    dbt = dbtRunner()
    run_res = dbt.invoke(["run", "--project-dir", "dbt", "--profiles-dir", "dbt"])
    if not run_res.success:
        logger.error("dbt run failed: %s", run_res.exception)
        return False

    test_res = dbt.invoke(["test", "--project-dir", "dbt", "--profiles-dir", "dbt"])
    if not test_res.success:
        logger.error("dbt test failed: %s", test_res.exception)
        return False

    logger.info(
        "dbt run & test successful! (%d models, %d tests passed)",
        len(run_res.result),
        len(test_res.result),
    )

    logger.info("==================================================")
    logger.info("SUCCESS: Main warehouse is fully populated!")
    logger.info("You can now start the dashboard using:")
    logger.info("    streamlit run dashboard/app.py")
    logger.info("==================================================")
    return True


if __name__ == "__main__":
    ingest_synthetic_into_main()
