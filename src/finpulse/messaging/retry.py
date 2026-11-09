
import logging
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


class RetryExhaustedError(Exception):
    """Raised when all processing attempts fail."""


def execute_with_retry(
    operation: Callable[[], T],
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
) -> T:
    """
    Execute an operation with retries.

    Returns the operation result if successful.
    Raises RetryExhaustedError after all attempts fail.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()

        except Exception as exc:
            logger.warning(
                "Processing attempt %s/%s failed: %s",
                attempt,
                max_attempts,
                exc,
            )

            if attempt == max_attempts:
                raise RetryExhaustedError(
                    f"Operation failed after {max_attempts} attempts"
                ) from exc

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    raise RetryExhaustedError("Operation failed")
