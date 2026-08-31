# -*- coding: utf-8 -*-
"""Licensing module for DynamicPro ERP.

All model classes prefixed with 'Lic' to avoid conflicts.
"""
from licensing.models import (
    LicPlan, LicCompany, LicSubscription, LicLicense, LicPayment,
    LicMasterUser, LicCompanyUser, LicDatabaseRegistry,
)
from licensing.plans_data import PLANS, GRACE_PERIOD_DAYS, TRIAL_DAYS

# Aliases for convenience
Plan = LicPlan
Company = LicCompany
Subscription = LicSubscription
License = LicLicense
Payment = LicPayment
MasterUser = LicMasterUser
CompanyUser = LicCompanyUser
DatabaseRegistry = LicDatabaseRegistry

__all__ = [
    "LicPlan", "LicCompany", "LicSubscription", "LicLicense", "LicPayment",
    "LicMasterUser", "LicCompanyUser", "LicDatabaseRegistry",
    "Plan", "Company", "Subscription", "License", "Payment",
    "MasterUser", "CompanyUser", "DatabaseRegistry",
    "PLANS", "GRACE_PERIOD_DAYS", "TRIAL_DAYS",
]
