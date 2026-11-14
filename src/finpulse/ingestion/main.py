from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError

from finpulse.ingestion.parsers.card_pdf_parser import parse_card_pdf
from finpulse.ingestion.parsers.manual_parser import parse_manual
from finpulse.ingestion.parsers.sms_parser import parse_bank_sms
from finpulse.ingestion.parsers.upi_parser import parse_upi_csv
from finpulse.messaging.producer import KafkaTransactionProducer


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kafka_producer = KafkaTransactionProducer()

    yield

    app.state.kafka_producer.close()


app = FastAPI(
    title="FinPulse Ingestion API",
    description="API for ingesting financial transactions",
    version="0.2.0",
    lifespan=lifespan,
)


class SMSRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    timestamp: datetime
    reference_id: str | None = None


def serialize_transactions(transactions):
    return [transaction.model_dump(mode="json") for transaction in transactions]


def publish_transaction(transaction):
    try:
        event_id = app.state.kafka_producer.publish(transaction)
        return event_id

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Transaction could not be published to Kafka",
        ) from exc


def publish_transactions(transactions):
    event_ids = []

    for transaction in transactions:
        event_id = publish_transaction(transaction)
        event_ids.append(event_id)

    return event_ids


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "finpulse-ingestion",
    }


@app.post("/transactions")
def ingest_manual_transaction(payload: dict):
    try:
        transaction = parse_manual(payload)

        event_id = publish_transaction(transaction)

        return {
            "status": "accepted",
            "event_ids": [event_id],
            "transactions": serialize_transactions([transaction]),
            "count": 1,
        }

    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.post("/sms")
def ingest_sms(payload: SMSRequest):
    try:
        transaction = parse_bank_sms(
            message=payload.message,
            user_id=payload.user_id,
            timestamp=payload.timestamp,
            reference_id=payload.reference_id,
        )

        event_id = publish_transaction(transaction)

        return {
            "status": "accepted",
            "event_ids": [event_id],
            "transactions": serialize_transactions([transaction]),
            "count": 1,
        }

    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.post("/upload/upi")
async def upload_upi_csv(
    user_id: str,
    file: UploadFile = File(...),
):
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded CSV is empty",
        )

    temp_path = None

    try:
        with NamedTemporaryFile(
            delete=False,
            suffix=".csv",
        ) as temp:
            temp.write(content)
            temp_path = temp.name

        transactions = parse_upi_csv(temp_path, user_id)

        event_ids = publish_transactions(transactions)

        return {
            "status": "accepted",
            "event_ids": event_ids,
            "transactions": serialize_transactions(transactions),
            "count": len(transactions),
        }

    except HTTPException:
        raise

    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()


@app.post("/upload/card-statement")
async def upload_card_statement(
    user_id: str,
    file: UploadFile = File(...),
):
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded PDF is empty",
        )

    temp_path = None

    try:
        with NamedTemporaryFile(
            delete=False,
            suffix=".pdf",
        ) as temp:
            temp.write(content)
            temp_path = temp.name

        transactions = parse_card_pdf(temp_path, user_id)

        event_ids = publish_transactions(transactions)

        return {
            "status": "accepted",
            "event_ids": event_ids,
            "transactions": serialize_transactions(transactions),
            "count": len(transactions),
        }

    except HTTPException:
        raise

    except (ValidationError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()
