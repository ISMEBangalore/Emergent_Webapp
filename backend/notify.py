"""Proactive alert delivery via Resend (https://resend.com) — the same
transactional-email provider the org already uses elsewhere. Deliberately a
thin, dependency-free wrapper (plain `requests`, no SDK) since sending one
email a week doesn't need more than that.

Silently no-ops (with a log line) when RESEND_API_KEY isn't set, mirroring
the existing "AI Insight isn't configured yet" pattern for ANTHROPIC_API_KEY
in server.py - a missing optional integration should degrade gracefully,
not 500 the request that triggered it."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

logger = logging.getLogger("crm_report.notify")

RESEND_API_URL = "https://api.resend.com/emails"
SEVERITY_COLOR = {"critical": "#DC2626", "warning": "#F59E0B"}


def _alerts_html(alerts: List[Dict[str, str]]) -> str:
    rows = "".join(
        f'<tr><td style="padding:10px 14px;border-left:4px solid {SEVERITY_COLOR.get(a.get("severity"), "#64748B")};'
        f'background:#F8FAFC;margin-bottom:8px;display:block;border-radius:4px;">'
        f'<div style="font-weight:700;color:#0F172A;font-size:14px;">{a.get("title", "")}</div>'
        f'<div style="color:#475569;font-size:13px;margin-top:2px;">{a.get("message", "")}</div>'
        f'</td></tr>'
        for a in alerts
    )
    return (
        '<div style="font-family:Arial,sans-serif;max-width:560px;">'
        '<h2 style="color:#002FA7;margin:0 0 12px;">LeadPulse — new alerts</h2>'
        '<p style="color:#475569;font-size:13px;margin:0 0 16px;">'
        "The following were flagged in the cumulative Application Insight numbers:</p>"
        f'<table style="width:100%;border-collapse:separate;border-spacing:0 8px;">{rows}</table>'
        '<p style="color:#94A3B8;font-size:11px;margin-top:20px;">'
        "Sent automatically by LeadPulse. Manage this in Settings.</p>"
        "</div>"
    )


def send_alert_email(alerts: List[Dict[str, str]], to_email: str) -> bool:
    """Returns True if an email was actually sent (or would have been, absent
    real credentials in a dev/test environment), False if skipped."""
    if not alerts or not to_email:
        return False
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping alert email to %s (%d alert(s)).", to_email, len(alerts))
        return False
    from_addr = os.environ.get("ALERT_EMAIL_FROM", "LeadPulse Alerts <onboarding@resend.dev>")
    subject = f"LeadPulse: {len(alerts)} new alert{'s' if len(alerts) != 1 else ''}"
    payload: Dict[str, Any] = {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": _alerts_html(alerts),
    }
    try:
        resp = requests.post(
            RESEND_API_URL, json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error("Failed to send alert email: %s", e)
        return False
