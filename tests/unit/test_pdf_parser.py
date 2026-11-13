from finpulse.ingestion.parsers.card_pdf_parser import (
    extract_pdf_text,
    parse_card_pdf,
)


def test_pdf_without_transaction_rows(tmp_path):
    # Create a simple PDF with text.
    import fitz

    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Credit Card Statement\nNo transaction rows here")
    doc.save(pdf_path)
    doc.close()

    transactions = parse_card_pdf(
        str(pdf_path),
        "user_001",
    )

    assert transactions == []


def test_pdf_text_extraction(tmp_path):
    import fitz

    pdf_path = tmp_path / "sample.pdf"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "FinPulse Test Statement")
    doc.save(pdf_path)
    doc.close()

    text = extract_pdf_text(str(pdf_path))

    assert "FinPulse Test Statement" in text
