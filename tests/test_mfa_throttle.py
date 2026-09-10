"""Focused tests for master MFA brute-force protection."""


def test_mfa_verification_attempts_are_throttled(monkeypatch):
    import security.two_factor as two_factor

    two_factor._MFA_FAILURES.clear()
    user_id = 987654321
    assert two_factor._mfa_attempt_allowed(user_id)

    for _ in range(two_factor.MFA_MAX_ATTEMPTS):
        two_factor._register_mfa_failure(user_id)

    assert not two_factor._mfa_attempt_allowed(user_id)

    rec = two_factor._MFA_FAILURES[user_id]
    monkeypatch.setattr(two_factor.time, "time", lambda: rec["lock_until"] + 1)
    assert two_factor._mfa_attempt_allowed(user_id)
    assert user_id not in two_factor._MFA_FAILURES
