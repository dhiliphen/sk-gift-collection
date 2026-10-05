"""
Tests for GET /api/admin/export-db — ADMIN-only raw SQLite file download,
used to pull a local/production copy of the database (e.g. ahead of a
Postgres/MySQL migration). The endpoint serves the real on-disk file at
DB_PATH, not the test harness's isolated in-memory database, so these
tests check access control and response shape rather than DB content.
"""
from tests.conftest import AUTH_HEADERS, ADMIN_USERNAME, ADMIN_PASSWORD, login_as


def test_admin_can_export_db(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.get("/api/admin/export-db", cookies=cookies)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    assert "inventory_export.db" in resp.headers["content-disposition"]
    assert len(resp.content) > 0


def test_viewer_cannot_export_db(client, sample_viewer_user):
    cookies = login_as(client, "viewer1", "viewerpass123")
    resp = client.get("/api/admin/export-db", cookies=cookies)
    assert resp.status_code == 403


def test_export_db_requires_auth(client):
    resp = client.get("/api/admin/export-db", follow_redirects=False)
    assert resp.status_code in (302, 303, 307)


def test_internal_service_calls_bypass_role_check_for_export(client):
    resp = client.get("/api/admin/export-db", headers=AUTH_HEADERS)
    assert resp.status_code == 200
