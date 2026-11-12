
import json
import re
from pathlib import Path

from finpulse.common.models import Transaction


class MerchantNormalizer:
    """Normalize merchant names using an external JSON mapping."""

    def __init__(
        self,
        mapping_path: str | Path = "config/merchant_mapping.json",
    ):
        self.mapping_path = Path(mapping_path)
        self.mapping = self._load_mapping()

    def _load_mapping(self) -> dict[str, str]:
        if not self.mapping_path.exists():
            raise FileNotFoundError(
                f"Merchant mapping file not found: {self.mapping_path}"
            )

        with self.mapping_path.open("r", encoding="utf-8") as file:
            mapping = json.load(file)

        if not isinstance(mapping, dict):
            raise ValueError("Merchant mapping must be a JSON object")

        return {
            self._clean_name(key).upper(): self._clean_name(value)
            for key, value in mapping.items()
            if isinstance(key, str)
            and isinstance(value, str)
            and self._clean_name(key)
            and self._clean_name(value)
        }

    @staticmethod
    def _clean_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip())

    def normalize(self, merchant_raw: str | None) -> str | None:
        if not merchant_raw or not merchant_raw.strip():
            return None

        cleaned_name = self._clean_name(merchant_raw)
        lookup_name = cleaned_name.upper()

        if lookup_name in self.mapping:
            return self.mapping[lookup_name]

        # Preserve unknown merchant names rather than guessing.
        return cleaned_name.title()

    def normalize_transaction(
        self,
        transaction: Transaction,
    ) -> Transaction:
        data = transaction.model_dump()

        data["merchant_normalized"] = self.normalize(
            transaction.merchant_raw
        )

        return Transaction.model_validate(data)
        