"""
Parser Validation Suite for FinPulse Synthetic Dataset.

Validates:
1. parse_upi_csv (valid CSV, edge cases, missing columns, empty file)
2. parse_card_pdf (valid PDF, internal deduplication, unparseable lines)
3. parse_bank_sms (valid debits/credits, keywords, extraction, invalid messages)
4. parse_manual (valid entries, extractions, validation errors)

Produces: data/synthetic/reports/parser_validation.json
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.manual_parser import parse_manual
from finpulse.ingestion.parsers.sms_parser import parse_bank_sms
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def validate_all_parsers(manifest_path: str | Path = "data/synthetic/manifest.json") -> dict:
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    files = manifest["files"]
    report = {
        "timestamp": datetime.now().isoformat(),
        "parsers": {},
        "overall_status": "PASS",
    }

    # 1. UPI Parser Validation
    upi_path = files["upi_csv"]
    upi_results = {
        "parser": "parse_upi_csv",
        "file": upi_path,
        "valid_count_expected": manifest["counts"]["upi_valid"],
        "valid_count_parsed": 0,
        "checks": {},
        "status": "PASS",
    }
    try:
        txs = parse_upi_csv(upi_path, user_id=manifest["primary_user"])
        upi_results["valid_count_parsed"] = len(txs)
        assert len(txs) == manifest["counts"]["upi_valid"], (
            f"Expected {manifest['counts']['upi_valid']}, got {len(txs)}"
        )
        upi_results["checks"]["record_count_matches"] = True

        # Verify fields on first record
        t0 = txs[0]
        assert t0.amount == Decimal("450.00"), f"Wrong amount {t0.amount}"
        assert t0.direction == "DEBIT"
        assert t0.source_type == "UPI_CSV"
        assert t0.merchant_raw == "Swiggy"
        assert t0.currency == "INR"
        upi_results["checks"]["field_extraction_accuracy"] = True

        # Test empty CSV
        with NamedTemporaryFile(delete=False, suffix=".csv", mode="w") as tmp:
            tmp.write("")
            empty_path = tmp.name
        try:
            parse_upi_csv(empty_path, "u1")
            upi_results["checks"]["empty_csv_handled"] = False
        except Exception:
            upi_results["checks"]["empty_csv_handled"] = True
        finally:
            Path(empty_path).unlink(missing_ok=True)

        # Test missing required columns
        with NamedTemporaryFile(delete=False, suffix=".csv", mode="w") as tmp:
            tmp.write("date,amount\n2026-09-01,100\n")
            bad_path = tmp.name
        try:
            parse_upi_csv(bad_path, "u1")
            upi_results["checks"]["missing_columns_rejected"] = False
        except ValueError:
            upi_results["checks"]["missing_columns_rejected"] = True
        finally:
            Path(bad_path).unlink(missing_ok=True)

    except Exception as exc:
        logger.error("UPI parser validation error: %s", exc)
        upi_results["status"] = "FAIL"
        upi_results["error"] = str(exc)
        report["overall_status"] = "FAIL"

    report["parsers"]["upi"] = upi_results

    # 2. Card PDF Parser Validation
    card_path = files["card_pdf"]
    card_results = {
        "parser": "parse_card_pdf",
        "file": card_path,
        "valid_count_expected": manifest["counts"]["card_valid"],
        "valid_count_parsed": 0,
        "checks": {},
        "status": "PASS",
    }
    try:
        card_txs = parse_card_pdf(card_path, user_id=manifest["primary_user"])
        card_results["valid_count_parsed"] = len(card_txs)
        # Internal deduplication should suppress the repeated duplicate line in the PDF
        assert len(card_txs) == manifest["counts"]["card_valid"], (
            f"Expected {manifest['counts']['card_valid']}, got {len(card_txs)}"
        )
        card_results["checks"]["internal_deduplication_verified"] = True

        c0 = card_txs[0]
        assert c0.direction == "DEBIT"
        assert c0.source_type == "CARD_PDF"
        assert c0.amount == Decimal("2499.00")
        assert c0.merchant_raw == "AMZN PAYMENTS"
        card_results["checks"]["field_extraction_accuracy"] = True

    except Exception as exc:
        logger.error("Card PDF parser validation error: %s", exc)
        card_results["status"] = "FAIL"
        card_results["error"] = str(exc)
        report["overall_status"] = "FAIL"

    report["parsers"]["card"] = card_results

    # 3. Bank SMS Parser Validation
    sms_path = files["bank_sms_json"]
    sms_results = {
        "parser": "parse_bank_sms",
        "file": sms_path,
        "valid_count_expected": manifest["counts"]["sms_valid"],
        "valid_count_parsed": 0,
        "checks": {},
        "status": "PASS",
    }
    try:
        with open(sms_path, encoding="utf-8") as f:
            sms_records = json.load(f)

        parsed_sms = []
        for r in sms_records:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            tx = parse_bank_sms(
                message=r["message"],
                user_id=r["user_id"],
                timestamp=ts,
                reference_id=r.get("reference_id"),
            )
            parsed_sms.append(tx)

        sms_results["valid_count_parsed"] = len(parsed_sms)
        assert len(parsed_sms) == manifest["counts"]["sms_valid"]
        sms_results["checks"]["all_valid_sms_parsed"] = True

        # Salary credit check
        sal_tx = parsed_sms[0]
        assert sal_tx.direction == "CREDIT"
        assert sal_tx.amount == Decimal("85000.00")
        assert sal_tx.source_type == "BANK_SMS"

        # Debit check
        deb_tx = parsed_sms[1]
        assert deb_tx.direction == "DEBIT"
        assert deb_tx.amount == Decimal("1250.00")
        assert deb_tx.merchant_raw == "D-MART"
        sms_results["checks"]["direction_and_amount_accuracy"] = True

        # Invalid SMS check
        with open(files["bank_sms_edge_cases_json"], encoding="utf-8") as f:
            edge_sms = json.load(f)
        rejected = 0
        for r in edge_sms:
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            try:
                parse_bank_sms(r["message"], r["user_id"], ts)
            except ValueError:
                rejected += 1
        assert rejected == len(edge_sms)
        sms_results["checks"]["edge_cases_rejected_properly"] = True

    except Exception as exc:
        logger.error("SMS parser validation error: %s", exc)
        sms_results["status"] = "FAIL"
        sms_results["error"] = str(exc)
        report["overall_status"] = "FAIL"

    report["parsers"]["bank_sms"] = sms_results

    # 4. Manual Parser Validation
    man_path = files["manual_json"]
    man_results = {
        "parser": "parse_manual",
        "file": man_path,
        "valid_count_expected": manifest["counts"]["manual_valid"],
        "valid_count_parsed": 0,
        "checks": {},
        "status": "PASS",
    }
    try:
        with open(man_path, encoding="utf-8") as f:
            man_records = json.load(f)

        parsed_man = [parse_manual(r) for r in man_records]
        man_results["valid_count_parsed"] = len(parsed_man)
        assert len(parsed_man) == manifest["counts"]["manual_valid"]
        man_results["checks"]["all_valid_manual_parsed"] = True

        m0 = parsed_man[0]
        assert m0.amount == Decimal("350.00")
        assert m0.direction == "DEBIT"
        assert m0.source_type == "MANUAL"
        assert m0.merchant_raw == "Local Vegetable Vendor"
        man_results["checks"]["field_extraction_accuracy"] = True

        # Invalid manual payload check
        with open(files["manual_edge_cases_json"], encoding="utf-8") as f:
            edge_man = json.load(f)
        rejected_man = 0
        for r in edge_man:
            try:
                parse_manual(r)
            except (ValueError, Exception):
                rejected_man += 1
        assert rejected_man == len(edge_man)
        man_results["checks"]["edge_cases_rejected_properly"] = True

    except Exception as exc:
        logger.error("Manual parser validation error: %s", exc)
        man_results["status"] = "FAIL"
        man_results["error"] = str(exc)
        report["overall_status"] = "FAIL"

    report["parsers"]["manual"] = man_results

    # Save report
    out_dir = Path("data/synthetic/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "parser_validation.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(
        "Saved parser validation report to %s. Status: %s", report_file, report["overall_status"]
    )
    return report


if __name__ == "__main__":
    validate_all_parsers()
