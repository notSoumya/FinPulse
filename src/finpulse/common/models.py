
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceType = Literal[
    "BANK_SMS",
    "UPI_CSV",
    "CARD_PDF",
    "MANUAL",
]

Direction = Literal["DEBIT", "CREDIT"]


class Transaction(BaseModel):
    """
    Canonical transaction representation used across FinPulse.
    """

    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)

    amount: Decimal = Field(gt=0)
    currency: str = "INR"

    direction: Direction

    transaction_timestamp: datetime

    merchant_raw: str | None = None
    merchant_normalized: str | None = None

    reference_id: str | None = None

    source_type: SourceType

    @field_validator("transaction_timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must include timezone information")

        return value.astimezone(UTC)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()

        if len(value) != 3 or not value.isalpha():
            raise ValueError("Currency must be a 3-letter code")

        return value
