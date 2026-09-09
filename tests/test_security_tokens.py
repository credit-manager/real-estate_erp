from datetime import datetime, timezone


def test_utc_epoch_does_not_depend_on_local_timezone():
    from security.tokens import _utc_epoch

    value = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert _utc_epoch(value) == 1767225600


def test_utc_epoch_normalizes_aware_datetime():
    from security.tokens import _utc_epoch

    value = datetime(2026, 1, 1, 3, 0, tzinfo=timezone.utc)
    assert _utc_epoch(value) == 1767236400
