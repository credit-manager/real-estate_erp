"""Expose the server-side session CSRF token through a response header.

The session cookie remains HttpOnly. The browser SPA receives the current CSRF
value through ``X-CSRF-Token`` on authenticated responses and keeps it only in
memory, so a page reload can recover the token without weakening cookie safety.
"""
from flask import request, session
from flask.signals import request_finished


def _attach_csrf_header(sender, response):
    if not request.path.startswith(("/api/", "/admin/")):
        return
    if not session.get("_csrf_token"):
        return
    if not (
        session.get("user_id")
        or session.get("lic_company_id")
        or session.get("master_user_id")
    ):
        return
    response.headers.setdefault("X-CSRF-Token", session["_csrf_token"])


request_finished.connect(_attach_csrf_header, weak=False)
