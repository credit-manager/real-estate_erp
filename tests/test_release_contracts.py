from pathlib import Path


def test_release_migration_chain_reaches_journal_sealing():
    migrations = Path("migrations/versions")
    expected = [
        "0000_initial_schema.py",
        "0001_accounting_integrity.py",
        "0002_legacy_schema_alignment.py",
        "0003_financial_safety_checks.py",
        "0004_journal_cancelled_status.py",
        "0005_financial_year_integrity.py",
        "0006_journal_entry_immutability.py",
        "0007_harden_journal_delete_guards.py",
        "0008_seal_cancelled_journals.py",
    ]
    missing = [name for name in expected if not (migrations / name).is_file()]
    assert not missing, f"Missing release migration(s): {missing}"

    final = (migrations / expected[-1]).read_text(encoding="utf-8")
    assert 'revision = "0008_seal_cancelled_journals"' in final
    assert 'down_revision = "0007_harden_journal_delete_guards"' in final
    assert "cancelled" in final


def test_nginx_keeps_same_origin_gps_available():
    config = Path("deployment/nginx/nginx.conf").read_text(encoding="utf-8")
    assert 'geolocation=(self)' in config
    assert 'geolocation=()' not in config
