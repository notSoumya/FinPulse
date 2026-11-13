from unittest.mock import Mock, patch

import pytest

from finpulse.messaging.retry import (
    RetryExhaustedError,
    execute_with_retry,
)


def test_retry_succeeds_on_first_attempt():
    operation = Mock(return_value="success")

    result = execute_with_retry(operation, delay_seconds=0)

    assert result == "success"
    operation.assert_called_once()


def test_retry_succeeds_after_failure():
    operation = Mock(
        side_effect=[
            ValueError("Temporary failure"),
            "success",
        ]
    )

    result = execute_with_retry(
        operation,
        max_attempts=3,
        delay_seconds=0,
    )

    assert result == "success"
    assert operation.call_count == 2


def test_retry_exhausts_all_attempts():
    operation = Mock(side_effect=ValueError("Permanent failure"))

    with pytest.raises(RetryExhaustedError):
        execute_with_retry(
            operation,
            max_attempts=3,
            delay_seconds=0,
        )

    assert operation.call_count == 3


def test_retry_uses_configured_delay():
    operation = Mock(
        side_effect=[
            ValueError("Temporary failure"),
            "success",
        ]
    )

    with patch("finpulse.messaging.retry.time.sleep") as mock_sleep:
        execute_with_retry(
            operation,
            max_attempts=3,
            delay_seconds=2,
        )

    mock_sleep.assert_called_once_with(2)


def test_retry_rejects_invalid_attempt_count():
    with pytest.raises(ValueError, match="max_attempts"):
        execute_with_retry(lambda: "success", max_attempts=0)


def test_retry_rejects_negative_delay():
    with pytest.raises(ValueError, match="delay_seconds"):
        execute_with_retry(lambda: "success", delay_seconds=-1)
