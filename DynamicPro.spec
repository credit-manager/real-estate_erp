# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DynamicPro ERP Desktop
Builds a standalone .exe with embedded Python runtime.
Database: SQLite (stored in %APPDATA%\DynamicPro\)
"""
import os
import glob

ROOT = os.path.dirname(os.path.abspath(SPEC))

# Collect all data files
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# Collect all Python source directories
for pkg in ['routes', 'models', 'utils', 'licensing', 'security']:
    pkg_path = os.path.join(ROOT, pkg)
    if os.path.isdir(pkg_path):
        datas.append((pkg, pkg))

# Collect top-level Python modules
for mod in ['i18n.py', 'i18n_en.py', 'i18n_ar.py', 'config.py', 'server_config.py',
            'database.py', 'permissions.py', 'db_indexes.py', 'api_spec.py',
            'factory_reset.py', 'window_theme.py', 'live_pdf_builder.py']:
    if os.path.isfile(os.path.join(ROOT, mod)):
        datas.append((mod, '.'))

a = Analysis(
    ['launcher.pyw'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Flask core
        'flask', 'flask.json', 'flask.globals', 'flask.helpers',
        'flask_cors', 'flask_limiter', 'flask_limiter.util',
        'flask_sqlalchemy', 'flask_smorest',
        # Werkzeug
        'werkzeug', 'werkzeug.serving', 'werkzeug.security',
        'werkzeug.middleware', 'werkzeug.middleware.proxy_fix',
        # SQLAlchemy
        'sqlalchemy', 'sqlalchemy.dialects.sqlite',
        'sqlalchemy.sql.default_comparator', 'sqlalchemy.ext.baked',
        # Database
        'psycopg2', 'psycopg2.extras', 'psycopg2.extensions',
        # Jinja2
        'jinja2', 'markupsafe',
        # PDF
        'fpdf', 'fpdf.fpdf', 'fpdf.image_parsing', 'fpdf.svg',
        # PyWebview
        'webview', 'webview.platforms.edgechromium', 'webview.platforms.winforms',
        # Crypto
        'cryptography', 'cryptography.hazmat.primitives',
        'cryptography.hazmat.primitives.ciphers',
        # HTTP
        'requests',
        # Image
        'pillow',
        # AI
        'google.genai',
        # Misc
        'python_dotenv', 'dotenv',
        'marshmallow',
        'apscheduler', 'apscheduler.schedulers',
        'httpx',
        'certifi', 'charset_normalizer', 'idna', 'urllib3',
        # winreg (used by server_config)
        'winreg',
        # App modules
        'server_config', 'config', 'database', 'permissions',
        'db_indexes', 'api_spec', 'factory_reset',
        'i18n', 'i18n_en', 'i18n_ar',
        'window_theme', 'live_pdf_builder',
        # Routes
        'routes', 'routes.auth', 'routes.pages', 'routes.api',
        'routes.users', 'routes.roles', 'routes.backup',
        'routes.server', 'routes.settings', 'routes.sales',
        'routes.hr', 'routes.payroll', 'routes.manufacturing',
        'routes.rentals', 'routes.project_finance', 'routes.assets',
        'routes.accounting', 'routes.taxes', 'routes.currencies',
        'routes.financial_years', 'routes.companies', 'routes.projects',
        'routes.inventory', 'routes.procurement', 'routes.notifications',
        'routes.payments', 'routes.portal', 'routes.workflow',
        'routes.real_estate_invest', 'routes.escrow', 'routes.offplan',
        'routes.addons', 'routes.esignature', 'routes.bi', 'routes.dms',
        'routes.license', 'routes.crm',
        # Licensing
        'licensing', 'licensing.routes', 'licensing.auth', 'licensing.models',
        'licensing.engine', 'licensing.onboarding', 'licensing.plans_data',
        'licensing.db_manager',
        # Security
        'security', 'security.models', 'security.routes', 'security.rbac',
        'security.modules', 'security.tokens', 'security.two_factor',
        'security.audit', 'security.security_events', 'security.billing',
        'security.company_lifecycle',
        # Models
        'models', 'models.crm', 'models.hr', 'models.finance', 'models.project',
        'models.real_estate', 'models.rental', 'models.inventory',
        'models.manufacturing', 'models.assets', 'models.accounting',
        'models.payroll', 'models.sales', 'models.procurement',
        'models.workflow', 'models.license', 'models.escrow',
        'models.offplan', 'models.addons', 'models.esignature',
        'models.bi', 'models.dms', 'models.notifications', 'models.payments',
        # Utils
        'utils', 'utils.settings', 'utils.pagination', 'utils.pdf',
        'utils.accounting', 'utils.errlog', 'utils.logging_setup',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DynamicPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DynamicPro',
)
