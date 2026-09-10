from datetime import date


def test_financial_year_model_defines_company_scoped_years(app):
    from database import db
    from models.financial_year import FinancialYear

    with app.app_context():
        assert FinancialYear.__tablename__ == "financial_years"
        assert "company_id" in FinancialYear.__table__.columns
        assert "start_date" in FinancialYear.__table__.columns
        assert "end_date" in FinancialYear.__table__.columns
        assert date(2026, 1, 1) < date(2026, 12, 31)
        assert any(
            constraint.name == "uq_financial_year_company_name"
            for constraint in FinancialYear.__table__.constraints
            if constraint.name
        )
