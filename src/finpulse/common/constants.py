# Supported transaction sources

SOURCE_TYPES = {
    "BANK_SMS",
    "UPI_CSV",
    "CARD_PDF",
    "MANUAL",
}

# Transaction directions

DIRECTIONS = {
    "DEBIT",
    "CREDIT",
}

# Schema version

SCHEMA_VERSION = "1.0"

# Kafka topics for each source

TOPICS = {
    "BANK_SMS": "raw.bank.sms",
    "UPI_CSV": "raw.upi.csv",
    "CARD_PDF": "raw.card.pdf",
    "MANUAL": "raw.manual",
}

# Dead Letter Queue topics

DLQ_TOPICS = {
    "BANK_SMS": "dlq.bank_sms",
    "UPI_CSV": "dlq.upi_csv",
    "CARD_PDF": "dlq.card_pdf",
    "MANUAL": "dlq.manual",
}
