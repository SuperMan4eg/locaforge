import pytest

from locaforge.application.services.retry_policy import BatchRetryPolicy


def test_retry_policy_requires_at_least_one_attempt() -> None:
    with pytest.raises(ValueError, match="positive"):
        BatchRetryPolicy(attempts_per_group=0)
