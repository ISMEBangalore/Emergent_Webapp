"""E2E regression tests for per-program publisher reports, cumulative ranges, filtering, settings, exports, and trends."""
import io
import os
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from openpyxl import Workbook, load_workbook

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")

STATE = {"created_ids": []}


def summary_row(result, label):
    """Return a named summary row and fail clearly if the report is incomplete."""
    return next(row for row in result["summary"] if row.get("label") == label)


def assert_publisher_report_shape(report, expected_total):
    """Validate full publisher report structure, totals, and rightmost Total column."""
    assert isinstance(report, dict)
    assert report["programs"]
    assert report["columns"] == report["programs"] + ["Total"]
    assert summary_row(report, "Total Leads")["total"] == expected_total
    assert len(report["matrix"]) == 10
    assert len(report["summary"]) >= 20
    for row in report["matrix"]:
        assert set(row["values"]) == set(report["programs"])
        assert row["total"] == sum(row["values"].values())


def wait_until_ready(client, report_id, timeout=60):
    """Poll a created report until background processing is complete."""
    deadline = time.time() + timeout
    latest = None
    while time.time() < deadline:
        response = client.get(f"{BASE_URL}/api/reports/{report_id}", timeout=20)
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest.get("status") == "ready":
            return latest
        if latest.get("status") == "error":
            pytest.fail(f"Report processing failed: {latest.get('error')}")
        time.sleep(1)
    pytest.fail(f"Report {report_id} did not become ready in {timeout}s; latest={latest}")


def build_test_lead_xlsx():
    """Build rows covering test name/email/remark/stage plus boundary and normal controls."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "Registered Name",
        "Course",
        "Lead Stage",
        "Email",
        "Lead Remark",
        "Email Verification Status",
        "Mobile Verification Status",
        "Publisher Name",
        "Lead Origin(Primary)",
    ])
    sheet.append(["Test User", "B.Com", "APPLIED", "real1@x.com", "", "VERIFIED", "", "Pub A", "API"])
    sheet.append(["Email Control", "BBA", "WARM", "test123@x.com", "", "", "VERIFIED", "Pub B", "REDIRECT"])
    sheet.append(["Remark Control", "PGDM", "COLD", "real2@x.com", "test lead", "VERIFIED", "", "Pub C", "Organic"])
    sheet.append(["Stage Control", "B.Com", "TEST LEADS", "real3@x.com", "", "", "", "Pub A", "Organic"])
    sheet.append(["Latest Kumar", "BBA", "APPLIED", "kumar@x.com", "", "VERIFIED", "", "Pub B", "API"])
    sheet.append(["Normal Kumar", "PGDM", "WARM", "normal@x.com", "customer", "", "VERIFIED", "Pub C", "REDIRECT"])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def upload_leads(client, payload, label):
    """Upload the TEST-lead workbook and track it for teardown."""
    files = {
        "lead_file": (
            "TEST_lead_filter.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {
        "week_label": label,
        "week_date": "2026-08-12",
        "amount_spent": "{}",
        "additional_attributed": "{}",
    }
    response = client.post(f"{BASE_URL}/api/reports", data=data, files=files, timeout=30)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["status"] == "processing"
    assert isinstance(created["id"], str) and created["id"]
    STATE["created_ids"].append(created["id"])
    return wait_until_ready(client, created["id"])


@pytest.fixture(scope="class")
def api_client():
    """Public API client which restores global settings and removes only test-created reports."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    original_response = session.get(f"{BASE_URL}/api/settings", timeout=20)
    assert original_response.status_code == 200
    STATE["original_settings"] = original_response.json()
    yield session
    original = STATE.get("original_settings")
    if original:
        allowed = {
            key: original.get(key)
            for key in (
                "programs", "verified_logic", "relevant_stages", "api_patterns",
                "redirect_patterns", "application_code_field", "application_code_field_apps",
                "exclude_test_leads", "test_keywords",
            )
            if key in original
        }
        session.put(f"{BASE_URL}/api/settings", json=allowed, timeout=20)
    for report_id in STATE["created_ids"]:
        session.delete(f"{BASE_URL}/api/reports/{report_id}", timeout=20)
    session.close()


class TestLeadPulseNewFeatures:
    """New cumulative-range and TEST-lead exclusion coverage plus core regressions."""

    def test_01_root_and_new_settings_defaults(self, api_client):
        root = api_client.get(f"{BASE_URL}/api/", timeout=20)
        assert root.status_code == 200
        assert root.json() == {"message": "CRM Weekly Report API"}

        response = api_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert response.status_code == 200
        settings = response.json()
        assert settings["exclude_test_leads"] is True
        assert settings["test_keywords"] == ["test"]
        assert settings["programs"] == ["B.Com", "BBA", "PGDM"]

    def test_02_cumulative_all_time_and_custom_ranges(self, api_client):
        all_time_response = api_client.get(f"{BASE_URL}/api/reports/cumulative", timeout=60)
        assert all_time_response.status_code == 200
        all_time = all_time_response.json()
        assert all_time["week_label"].startswith("Report Till Date")
        assert all_time["range"] == {"start": None, "end": None}
        assert all_time["result"]["data_quality"]["weeks_aggregated"] == 2
        assert all_time["kpis"]["total_leads"] == 44786
        assert isinstance(all_time["result"].get("publisher_report"), dict)

        publisher_reports = all_time["result"].get("publisher_reports")
        assert list(publisher_reports) == ["All", "B.Com", "BBA", "PGDM"]
        expected_totals = {"All": 44786, "B.Com": 5388, "BBA": 11494, "PGDM": 27904}
        all_publishers = set(publisher_reports["All"]["programs"])
        for program, expected_total in expected_totals.items():
            assert_publisher_report_shape(publisher_reports[program], expected_total)
            assert set(publisher_reports[program]["programs"]) == all_publishers
        assert all_time["result"]["publisher_report"] == publisher_reports["All"]

        ranged_response = api_client.get(
            f"{BASE_URL}/api/reports/cumulative",
            params={"start": "2026-01-01", "end": "2026-12-31"},
            timeout=60,
        )
        assert ranged_response.status_code == 200
        ranged = ranged_response.json()
        assert ranged["week_label"].startswith("Custom Report")
        assert ranged["range"] == {"start": "2026-01-01", "end": "2026-12-31"}
        assert ranged["result"]["data_quality"]["weeks_aggregated"] >= 2
        assert ranged["kpis"]["total_leads"] > 0

        future_response = api_client.get(
            f"{BASE_URL}/api/reports/cumulative",
            params={"start": "2030-01-01", "end": "2030-12-31"},
            timeout=60,
        )
        assert future_response.status_code == 200
        future = future_response.json()
        assert future["week_label"].startswith("Custom Report")
        assert future["result"]["data_quality"]["weeks_aggregated"] == 0
        assert future["kpis"]["total_leads"] == 0

    def test_03_cumulative_export_with_partial_range_is_valid_xlsx(self, api_client):
        response = api_client.get(
            f"{BASE_URL}/api/reports/cumulative/export",
            params={"start": "2026-01-01"},
            timeout=60,
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "report_range.xlsx" in response.headers.get("content-disposition", "")
        assert response.content[:2] == b"PK"
        workbook = load_workbook(io.BytesIO(response.content), read_only=True, data_only=True)
        assert workbook.sheetnames == ["Weekly Report"]
        assert workbook["Weekly Report"]["A2"].value == "Lead Stage"

    def test_04_test_leads_are_excluded_with_word_boundary(self, api_client):
        settings_response = api_client.put(
            f"{BASE_URL}/api/settings",
            json={"exclude_test_leads": True, "test_keywords": ["test"]},
            timeout=20,
        )
        assert settings_response.status_code == 200
        assert settings_response.json()["exclude_test_leads"] is True
        assert settings_response.json()["test_keywords"] == ["test"]

        report = upload_leads(api_client, build_test_lead_xlsx(), "TEST_Filter enabled")
        STATE["filter_enabled_id"] = report["id"]
        quality = report["result"]["data_quality"]
        assert quality["raw_rows"] == 6
        assert quality["test_leads_excluded"] == 4
        assert quality["total_rows"] == 2
        assert report["kpis"]["total_leads"] == 2
        applied = next(row for row in report["result"]["matrix"] if row["stage"] == "APPLIED")
        assert applied["values"] == {"B.Com": 0, "BBA": 1, "PGDM": 0}
        warm = next(row for row in report["result"]["matrix"] if row["stage"] == "WARM")
        assert warm["values"] == {"B.Com": 0, "BBA": 0, "PGDM": 1}
        assert isinstance(report["result"]["publisher_report"], dict)

        persisted = api_client.get(f"{BASE_URL}/api/reports/{report['id']}", timeout=20)
        assert persisted.status_code == 200
        assert persisted.json()["result"]["data_quality"] == quality

    def test_05_disabling_test_filter_persists_and_keeps_all_rows(self, api_client):
        changed = api_client.put(
            f"{BASE_URL}/api/settings",
            json={"exclude_test_leads": False, "test_keywords": ["test", "dummy"]},
            timeout=20,
        )
        assert changed.status_code == 200
        assert changed.json()["exclude_test_leads"] is False
        assert changed.json()["test_keywords"] == ["test", "dummy"]
        persisted = api_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert persisted.status_code == 200
        assert persisted.json()["exclude_test_leads"] is False
        assert persisted.json()["test_keywords"] == ["test", "dummy"]

        report = upload_leads(api_client, build_test_lead_xlsx(), "TEST_Filter disabled")
        quality = report["result"]["data_quality"]
        assert quality["raw_rows"] == 6
        assert quality["test_leads_excluded"] == 0
        assert quality["total_rows"] == 6
        assert report["kpis"]["total_leads"] == 6

        restored = api_client.put(
            f"{BASE_URL}/api/settings",
            json={"exclude_test_leads": True, "test_keywords": ["test"]},
            timeout=20,
        )
        assert restored.status_code == 200
        assert restored.json()["exclude_test_leads"] is True
        assert restored.json()["test_keywords"] == ["test"]

    def test_06_sample_report_matrix_and_program_amounts_regression(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/reports/sample", timeout=20)
        assert response.status_code == 200
        created = response.json()
        STATE["created_ids"].append(created["id"])
        STATE["sample_id"] = created["id"]
        report = wait_until_ready(api_client, created["id"])
        assert report["status"] == "ready"
        applied = next(row for row in report["result"]["matrix"] if row["stage"] == "APPLIED")
        assert applied["values"] == {"B.Com": 14, "BBA": 41, "PGDM": 71}
        assert applied["total"] == 126
        publisher_report = report["result"]["publisher_report"]
        publisher_reports = report["result"].get("publisher_reports")
        assert list(publisher_reports) == ["All", "B.Com", "BBA", "PGDM"]
        assert publisher_report == publisher_reports["All"]
        expected_totals = {"All": 22393, "B.Com": 2694, "BBA": 5747, "PGDM": 13952}
        all_publishers = set(publisher_reports["All"]["programs"])
        for program, expected_total in expected_totals.items():
            assert_publisher_report_shape(publisher_reports[program], expected_total)
            assert set(publisher_reports[program]["programs"]) == all_publishers
        assert report["result"]["data_quality"]["test_leads_excluded"] >= 0

        amounts = {"B.Com": 800.0, "BBA": 7000.0, "PGDM": 11600.0}
        attributed = {"B.Com": 2.0, "BBA": 5.0, "PGDM": 2.0}
        patched = api_client.patch(
            f"{BASE_URL}/api/reports/{created['id']}/amounts",
            json={"amount_spent": amounts, "additional_attributed": attributed},
            timeout=30,
        )
        assert patched.status_code == 200
        patched_doc = patched.json()
        summary = {row["label"]: row for row in patched_doc["result"]["summary"] if "values" in row}
        assert summary["Amount Spent"]["values"] == amounts
        assert summary["Amount Spent"]["total"] == 19400.0
        assert summary["Additional Attributed Applications"]["values"] == attributed
        assert summary["Additional Attributed Applications"]["total"] == 9.0
        assert patched_doc["kpis"]["amount_spent"] == 19400.0

        persisted = api_client.get(f"{BASE_URL}/api/reports/{created['id']}", timeout=20)
        assert persisted.status_code == 200
        assert persisted.json()["amount_spent"] == amounts
        assert persisted.json()["additional_attributed"] == attributed

        exported = api_client.get(f"{BASE_URL}/api/reports/{created['id']}/export", timeout=60)
        assert exported.status_code == 200
        assert exported.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert exported.content[:2] == b"PK"
        workbook = load_workbook(io.BytesIO(exported.content), read_only=True, data_only=True)
        assert workbook.sheetnames == ["Weekly Report"]
        assert workbook["Weekly Report"]["A2"].value == "Lead Stage"

    def test_07_publisher_amounts_regression(self, api_client):
        report_url = f"{BASE_URL}/api/reports/{STATE['sample_id']}"
        current_response = api_client.get(report_url, timeout=20)
        assert current_response.status_code == 200
        publisher_report = current_response.json()["result"]["publisher_report"]
        app_row = next(
            row for row in publisher_report["summary"]
            if row["label"] == "Total No. of Applications"
        )
        publisher = next(name for name in publisher_report["programs"] if app_row["values"].get(name, 0) > 0)
        applied_count = app_row["values"][publisher]
        response = api_client.patch(
            f"{report_url}/publisher-amounts",
            json={"amount_spent": {}, "cpa": {publisher: 5000}},
            timeout=30,
        )
        assert response.status_code == 200
        doc = response.json()
        summary = {
            row["label"]: row for row in doc["result"]["publisher_report"]["summary"]
            if "values" in row
        }
        assert summary["Amount Spent"]["values"][publisher] == 5000 * applied_count
        assert summary["Cost/Application"]["values"][publisher] == 5000
        assert doc["publisher_cpa"][publisher] == 5000
        assert doc["result"]["publisher_reports"]["All"] == doc["result"]["publisher_report"]

        persisted = api_client.get(report_url, timeout=20)
        assert persisted.status_code == 200
        persisted_result = persisted.json()["result"]
        assert persisted_result["publisher_reports"]["All"] == persisted_result["publisher_report"]

    def test_08_trends_contains_created_ready_reports(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trends", timeout=20)
        assert response.status_code == 200
        trends = response.json()
        assert isinstance(trends, list) and trends
        week_dates = [item["week_date"] for item in trends]
        assert week_dates == sorted(week_dates)
        ids = {item["id"] for item in trends}
        assert STATE["sample_id"] in ids
        assert STATE["filter_enabled_id"] in ids
        assert all(isinstance(item.get("kpis"), dict) for item in trends)

    def test_09_range_parameters_reject_invalid_dates(self, api_client):
        malformed = api_client.get(
            f"{BASE_URL}/api/reports/cumulative", params={"start": "not-a-date"}, timeout=30
        )
        assert malformed.status_code == 400
        assert "Invalid start date" in malformed.json()["detail"]

        reversed_range = api_client.get(
            f"{BASE_URL}/api/reports/cumulative",
            params={"start": "2026-12-31", "end": "2026-01-01"},
            timeout=30,
        )
        assert reversed_range.status_code == 400
        assert "start date must be on or before end date" in reversed_range.json()["detail"]
