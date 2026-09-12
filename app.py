import json
import os
import sys
import logging
import time
import uuid
from datetime import datetime
from flask import Flask, redirect, url_for, request, session, jsonify, current_app
from flask_cors import CORS
from database import db
import config
import server_config
import permissions
from i18n import TRANSLATIONS, DEFAULT_LANG, LANG_CODES, get_lang, make_t
import os
import getpass

def _get_default_admin_username():
    """
    Determine the default admin username.
    Priority order:
    1. Environment variable DYNAMICPRO_ADMIN_USERNAME
    2. Config file {app_dir}/admin_username.cfg (can be set by installer)
    3. Default fallback: 'admin'
    """
    # Check environment variable
    env_user = os.environ.get('DYNAMICPRO_ADMIN_USERNAME', '')
    if env_user and env_user.strip():
        return env_user.strip()
    
    # Check config file (can be set by installer)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(app_dir, 'admin_username.cfg')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                username = f.read().strip()
                if username:
                    return username
        except Exception:
            pass
    
    # Default fallback
    return 'admin'

def _ensure_admin_user(app, db):
    """
    Ensure an admin user exists. If not, create one with temporary password.
    This runs on every app start to guarantee an admin user exists.
    """
    admin_username = _get_default_admin_username()
    
    try:
        admin_user = User.query.filter_by(username=admin_username).first()
        
        if not admin_user:
            # Create new admin user with temporary password
            admin_user = User(
                username=admin_username,
                password_hash=generate_password_hash('temp_password_123'),
                is_active=True,
                must_change_password=True,
            )
            db.session.add(admin_user)
            db.session.commit()
            current_app.logger.info(f'Created new admin user: {admin_username}')
        elif not admin_user.is_active:
            admin_user.is_active = True
            admin_user.must_change_password = True
            db.session.commit()
        elif admin_user.must_change_password:
            # Ensure must_change_password is set
            admin_user.must_change_password = True
            db.session.commit()
    except Exception as e:
        current_app.logger.error(f'Error ensuring admin user: {e}')

def _run_migrations_and_seeds(app, db):
    """Run all migrations and seed data. Only for master (non-company) instances."""
    from models import User, Role
    from werkzeug.security import generate_password_hash
    from sqlalchemy import inspect, text

    is_sqlite = "sqlite" in str(db.engine.url).lower()
    insp = inspect(db.engine)

    admin_username = _get_default_admin_username()

    if is_sqlite:
        # ── وضع Desktop (SQLite): Creating tables from Models then Seed only ──
        db.create_all()
        db.session.commit()
        {---------- Seed admin user with specified username ----------}
        admin_user = User(
            username=admin_username,
            password_hash=generate_password_hash('temp_password_123'),
            is_active=True,
            must_change_password=True,
        )
        db.session.add(admin_user)
        db.session.commit()
        {----------------------------------------------------------------}
    else:
        # ── وضع Cloud (PostgreSQL): migrations كاملة ──
        cols = [c["name"] for c in insp.get_columns("users")]
        if "must_change_password" not in cols:
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"
            ))
            db.session.commit()

        for table in ["invoices", "purchase_orders", "rental_contracts", "payment_plans"]:
            cols = [c["name"] for c in insp.get_columns(table)]
            if "financial_year_id" not in cols:
                db.session.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN financial_year_id INTEGER"
                ))
            db.session.commit()

        fk_plan = {
            "invoices": "fk_invoices_financial_year",
            "purchase_orders": "fk_purchase_orders_financial_year",
            "rental_contracts": "fk_rental_contracts_financial_year",
        }
        for table, fk in fk_plan.items():
            existing_fk = db.session.execute(
                text(f"SELECT constraint_name FROM information_schema.table_constraints WHERE constraint_name = '{fk}' AND table_name = '{table}'")
            ).scalar()
            if not existing_fk:
                db.session.execute(text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {fk} FOREIGN KEY (financial_year_id) REFERENCES financial_years(id)"
                ))
            db.session.commit()

        {---------- Ensure admin user exists with specified username ----------}
        admin_user = User.query.filter_by(username=admin_username).first()
        if not admin_user:
            admin_user = User(
                username=admin_username,
                password_hash=generate_password_hash('temp_password_123'),
                is_active=True,
                must_change_password=True,
            )
            db.session.add(admin_user)
            db.session.commit()
        elif not admin_user.is_active:
            admin_user.is_active = True
            admin_user.must_change_password = True
            db.session.commit()
        {----------------------------------------------------------------}
        {---------- Ensure role permissions exist ----------}
        from security.rbac import ensure_default_roles
        ensure_default_roles(db)
        {----------------------------------------------------------------}
    {----- Update health endpoint with admin info -----}
    # Store admin username in config for health endpoint
    app.config['ADMIN_USERNAME'] = admin_username