"""Regression tests for CRM settings, report generation, export, trends, and deletion APIs."""
import io
import os
import time
from datetime import date
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

STATE = {}


def wait_until_ready(client, report_id, timeout=60):
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


def build_small_lead_xlsx():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "Course",
        "Lead Stage",
        "Email Verification Status",
        "Mobile Verification Status",
        "Lead Origin(Primary)",
        "Agent Code",
    ])
    sheet.append(["B.Com", "APPLIED", "VERIFIED", "", "API", "A1"])
    sheet.append(["BBA", "APPLIED", "", "VERIFIED", "REDIRECT", ""])
    sheet.append(["PGDM", "APPLIED", "VERIFIED", "VERIFIED", "Organic", "A3"])
    sheet.append(["B.Com", "COLD", "", "", "Organic", ""])
    sheet.append(["BBA", "WARM", "VERIFIED", "", "API", ""])
    sheet.append(["PGDM", "JUNK", "", "", "WIDGET", ""])
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


@pytest.fixture(scope="class")
def api_client():
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    yield session
    session.close()


class TestCRMReportAPI:
    """End-to-end API coverage using the public preview endpoint."""

    def test_01_root_and_settings_persistence(self, api_client):
        root = api_client.get(f"{BASE_URL}/api/", timeout=20)
        assert root.status_code == 200
        assert root.json() == {"message": "CRM Weekly Report API"}

        response = api_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert response.status_code == 200
        original = response.json()
        assert original["programs"] == ["B.Com", "BBA", "PGDM"]
        assert original["verified_logic"] == "any"

        changed = api_client.put(
            f"{BASE_URL}/api/settings", json={"programs": original["programs"], "verified_logic": "all"}, timeout=20
        )
        assert changed.status_code == 200
        assert changed.json()["verified_logic"] == "all"
        persisted = api_client.get(f"{BASE_URL}/api/settings", timeout=20)
        assert persisted.status_code == 200
        assert persisted.json()["verified_logic"] == "all"

        restored = api_client.put(
            f"{BASE_URL}/api/settings", json={"programs": original["programs"], "verified_logic": "any"}, timeout=20
        )
        assert restored.status_code == 200
        assert restored.json()["verified_logic"] == "any"

    def test_02_create_sample_and_validate_computed_matrix(self, api_client):
        response = api_client.post(f"{BASE_URL}/api/reports/sample", timeout=20)
        assert response.status_code == 200
        created = response.json()
        assert isinstance(created.get("id"), str) and created["id"]
        assert created["status"] == "processing"
        STATE["sample_id"] = created["id"]

        report = wait_until_ready(api_client, created["id"])
        assert report["status"] == "ready"
        assert report["source"] == "sample"
        assert report["result"]["programs"] == ["B.Com", "BBA", "PGDM"]
        applied = next(row for row in report["result"]["matrix"] if row["stage"] == "APPLIED")
        assert applied["values"] == {"B.Com": 14, "BBA": 41, "PGDM": 71}
        assert applied["total"] == 126
        assert report["kpis"]["total_leads"] == 22393
        assert report["kpis"]["total_applications"] == 101
        assert isinstance(report["result"]["summary"], list) and len(report["result"]["summary"]) > 10

    def test_03_list_is_newest_first_and_excludes_heavy_fields(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/reports", timeout=20)
        assert response.status_code == 200
        reports = response.json()
        assert isinstance(reports, list) and reports
        assert reports[0]["id"] == STATE["sample_id"]
        assert all("result" not in report and "settings" not in report for report in reports)
        created_times = [report["created_at"] for report in reports]
        assert created_times == sorted(created_times, reverse=True)

    def test_04_export_is_valid_xlsx(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/reports/{STATE['sample_id']}/export", timeout=30)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert response.content[:2] == b"PK"
        workbook = load_workbook(io.BytesIO(response.content), read_only=True, data_only=True)
        assert workbook.sheetnames == ["Weekly Report"]
        sheet = workbook["Weekly Report"]
        assert sheet["A2"].value == "Lead Stage"
        assert sheet["B3"].value == 14

    def test_05_patch_amounts_recomputes_money_rows_and_kpis(self, api_client):
        amounts = {"B.Com": 800.0, "BBA": 7000.0, "PGDM": 11600.0}
        attributed = {"B.Com": 2.0, "BBA": 5.0, "PGDM": 2.0}
        response = api_client.patch(
            f"{BASE_URL}/api/reports/{STATE['sample_id']}/amounts",
            json={"amount_spent": amounts, "additional_attributed": attributed},
            timeout=30,
        )
        assert response.status_code == 200
        report = response.json()
        summary = {row["label"]: row for row in report["result"]["summary"] if "values" in row}
        assert summary["Amount Spent"]["values"] == amounts
        assert summary["Amount Spent"]["total"] == 19400.0
        assert summary["Cost/Application"]["values"] == {"B.Com": 100.0, "BBA": 200.0, "PGDM": 200.0}
        assert summary["Cost/Application"]["total"] == 192.08
        assert summary["Additional Attributed Applications"]["values"] == attributed
        assert summary["Additional Attributed Applications"]["total"] == 9.0
        assert summary["Modified CPA after attribution"]["values"] == {
            "B.Com": 80.0,
            "BBA": 175.0,
            "PGDM": 193.33,
        }
        assert summary["Modified CPA after attribution"]["total"] == 176.36
        assert report["kpis"]["amount_spent"] == 19400.0
        assert report["kpis"]["blended_cpa"] == 192.08

        persisted = api_client.get(f"{BASE_URL}/api/reports/{STATE['sample_id']}", timeout=20).json()
        assert persisted["amount_spent"] == amounts
        assert persisted["additional_attributed"] == attributed

    def test_06_small_real_xlsx_upload_processes_without_crash(self, api_client):
        label = "TEST_Small upload"
        week_date = date.today().isoformat()
        files = {
            "lead_file": (
                "TEST_small_leads.xlsx",
                build_small_lead_xlsx(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        data = {
            "week_label": label,
            "week_date": week_date,
            "amount_spent": '{"B.Com":100,"BBA":200,"PGDM":300}',
            "additional_attributed": "{}",
        }
        response = api_client.post(f"{BASE_URL}/api/reports", data=data, files=files, timeout=30)
        assert response.status_code == 200
        created = response.json()
        assert created["status"] == "processing"
        STATE["upload_id"] = created["id"]

        report = wait_until_ready(api_client, created["id"])
        assert report["source"] == "upload"
        assert report["lead_filename"] == "TEST_small_leads.xlsx"
        assert report["result"]["data_quality"]["total_rows"] == 6
        assert report["result"]["data_quality"]["unclassified_program"] == 0
        applied = next(row for row in report["result"]["matrix"] if row["stage"] == "APPLIED")
        assert applied["values"] == {"B.Com": 1, "BBA": 1, "PGDM": 1}
        assert applied["total"] == 3
        assert report["kpis"]["total_leads"] == 6
        assert report["kpis"]["amount_spent"] == 600.0

    def test_07_trends_are_ready_sorted_and_contain_kpis(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/trends", timeout=20)
        assert response.status_code == 200
        trends = response.json()
        assert isinstance(trends, list)
        assert all(item["status"] == "ready" for item in trends) if trends and "status" in trends[0] else True
        week_dates = [item["week_date"] for item in trends]
        assert week_dates == sorted(week_dates)
        ids = {item["id"] for item in trends}
        assert STATE["sample_id"] in ids and STATE["upload_id"] in ids
        assert all(isinstance(item.get("kpis"), dict) for item in trends)

    def test_08_delete_reports_and_verify_404(self, api_client):
        for key in ("upload_id", "sample_id"):
            report_id = STATE[key]
            response = api_client.delete(f"{BASE_URL}/api/reports/{report_id}", timeout=20)
            assert response.status_code == 200
            assert response.json() == {"deleted": True}
            get_response = api_client.get(f"{BASE_URL}/api/reports/{report_id}", timeout=20)
            assert get_response.status_code == 404
            assert get_response.json()["detail"] == "Report not found"

    def test_09_missing_resource_error_handling(self, api_client):
        missing = "00000000-0000-0000-0000-000000000000"
        get_response = api_client.get(f"{BASE_URL}/api/reports/{missing}", timeout=20)
        assert get_response.status_code == 404
        assert get_response.json() == {"detail": "Report not found"}
        delete_response = api_client.delete(f"{BASE_URL}/api/reports/{missing}", timeout=20)
        assert delete_response.status_code == 404
        assert delete_response.json() == {"detail": "Report not found"}
        export_response = api_client.get(f"{BASE_URL}/api/reports/{missing}/export", timeout=20)
        assert export_response.status_code == 404
        assert export_response.json() == {"detail": "Report not ready"}
