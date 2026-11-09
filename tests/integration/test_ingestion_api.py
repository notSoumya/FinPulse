
from unittest.mock import MagicMock, patch

import fitz
from fastapi.testclient import TestClient

from finpulse.ingestion.main import app


def create_test_pdf():
    doc = fitz.open()
    page = doc.new_page()

    page.insert_text(
        (50, 50),
        "CREDIT CARD STATEMENT\n"
        "07-11-2026 AMAZON PURCHASE 1,250.00\n"
        "08-11-2026 NETFLIX SUBSCRIPTION 649.00\n"
        "09-11-2026 UBER TRIP 350.00",
    )

    pdf_bytes = doc.tobytes()
    doc.close()

    return pdf_bytes


def create_mock_producer():
    producer = MagicMock()
    producer.publish.side_effect = [
        "event_001",
        "event_002",
        "event_003",
        "event_004",
    ]
    return producer


def test_health_endpoint():
    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        mock_class.return_value = create_mock_producer()

        with TestClient(app) as client:
            response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_manual_transaction_endpoint():
    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        mock_class.return_value = create_mock_producer()

        with TestClient(app) as client:
            payload = {
                "user_id": "user_001",
                "amount": 1250.50,
                "currency": "INR",
                "direction": "DEBIT",
                "transaction_timestamp": "2026-11-09T10:30:00+05:30",
                "merchant_raw": "Amazon",
                "reference_id": "REF12345",
                "source_type": "MANUAL",
            }

            response = client.post("/transactions", json=payload)

            assert response.status_code == 200
            assert response.json()["count"] == 1
            assert response.json()["event_ids"] == ["event_001"]

            mock_class.return_value.publish.assert_called_once()


def test_sms_endpoint():
    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        mock_class.return_value = create_mock_producer()

        with TestClient(app) as client:
            payload = {
                "user_id": "user_001",
                "message": "Rs. 750.00 debited from your account at AMAZON",
                "timestamp": "2026-11-09T11:00:00+05:30",
                "reference_id": "SMS987654",
            }

            response = client.post("/sms", json=payload)

            assert response.status_code == 200
            assert response.json()["count"] == 1
            assert response.json()["event_ids"] == ["event_001"]


def test_upi_csv_upload():
    csv_content = (
        "date,amount,type,merchant,reference_id,currency\n"
        "2026-11-07 10:30:00,450.00,DR,Swiggy,UPI001,INR\n"
        "2026-11-07 12:15:00,1200.00,DR,Amazon,UPI002,INR\n"
        "2026-11-07 14:00:00,5000.00,CR,Salary,UPI003,INR\n"
    )

    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        producer = create_mock_producer()
        mock_class.return_value = producer

        with TestClient(app) as client:
            response = client.post(
                "/upload/upi",
                params={"user_id": "user_001"},
                files={
                    "file": (
                        "test_upi.csv",
                        csv_content.encode("utf-8"),
                        "text/csv",
                    )
                },
            )

            assert response.status_code == 200
            assert response.json()["count"] == 3
            assert len(response.json()["event_ids"]) == 3
            assert producer.publish.call_count == 3


def test_card_pdf_upload():
    pdf_content = create_test_pdf()

    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        producer = create_mock_producer()
        mock_class.return_value = producer

        with TestClient(app) as client:
            response = client.post(
                "/upload/card-statement",
                params={"user_id": "user_001"},
                files={
                    "file": (
                        "test_card.pdf",
                        pdf_content,
                        "application/pdf",
                    )
                },
            )

            assert response.status_code == 200
            assert response.json()["count"] == 3
            assert len(response.json()["event_ids"]) == 3
            assert producer.publish.call_count == 3


def test_invalid_manual_transaction():
    with patch(
        "finpulse.ingestion.main.KafkaTransactionProducer"
    ) as mock_class:
        mock_class.return_value = create_mock_producer()

        with TestClient(app) as client:
            payload = {
                "user_id": "user_001",
                "amount": -500,
                "currency": "INR",
                "direction": "DEBIT",
                "transaction_timestamp": "2026-11-09T10:30:00+05:30",
                "source_type": "MANUAL",
            }

            response = client.post("/transactions", json=payload)

            assert response.status_code == 422
            mock_class.return_value.publish.assert_not_called()