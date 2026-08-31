# -*- coding: utf-8 -*-
"""Initial plan data for the licensing system."""

PLANS = [
    {
        "code": "basic",
        "name": "Basic",
        "name_ar": "الأساسية",
        "max_users": 5,
        "max_projects": 10,
        "max_storage_mb": 1024,
        "modules": {
            "accounting": True,
            "projects": True,
            "procurement": True,
            "inventory": True,
            "hr": False,
            "payroll": False,
            "equipment": False,
            "advanced_reports": False,
            "multi_branch": False,
            "api_access": False,
            "priority_support": False,
        },
        "sort_order": 1,
    },
    {
        "code": "professional",
        "name": "Professional",
        "name_ar": "الاحترافية",
        "max_users": 20,
        "max_projects": -1,  # unlimited
        "max_storage_mb": 5120,
        "modules": {
            "accounting": True,
            "projects": True,
            "procurement": True,
            "inventory": True,
            "hr": True,
            "payroll": True,
            "equipment": True,
            "advanced_reports": True,
            "multi_branch": True,
            "api_access": False,
            "priority_support": False,
        },
        "sort_order": 2,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "name_ar": "المؤسسات",
        "max_users": 100,
        "max_projects": -1,  # unlimited
        "max_storage_mb": 20480,
        "modules": {
            "accounting": True,
            "projects": True,
            "procurement": True,
            "inventory": True,
            "hr": True,
            "payroll": True,
            "equipment": True,
            "advanced_reports": True,
            "multi_branch": True,
            "api_access": True,
            "priority_support": True,
        },
        "sort_order": 3,
    },
]

GRACE_PERIOD_DAYS = 7
TRIAL_DAYS = 30
