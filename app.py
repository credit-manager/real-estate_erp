import json
import os
import sys
import logging
from datetime import datetime
from flask import Flask, redirect, url_for, request, session, jsonify, current_app
from flask_cors import CORS
from database import db
import config
import server_config
import permissions
from i18n import TRANSLATIONS, DEFAULT_LANG, LANG_CODES, make_t


def _run_migrations_and_seeds(app, db):
    """Run all migrations and seed data. Only for master (non-company) instances."""
    from models import User, Role
    from werkzeug.security import generate_password_hash
    from sqlalchemy import inspect, text

    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("users")]
    if "must_change_password" not in cols:
        db.session.execute(text(
            "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE"