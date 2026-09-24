"""
Tests for authentication — Phase 11

The app uses session-cookie auth with an in-memory session store.
Credentials: username="admin", password="skgifts"
Internal API calls can use X-Internal-Key header.
"""
import os
import pytest
from fastapi.testclient import TestClient
from tests.conftest import AUTH_HEADERS

# Import the app module-level objects
from main import app
from app.auth import _sessions, create_session, is_valid_session


# ---------------------------------------------------------------------------
# GET /login — public, no auth needed
# ---------------------------------------------------------------------------

def test_login_page_accessible_without_auth(client):
    """GET /login should return 200 without any auth."""
    response = client.get("/login")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET / without session — should redirect to /login
# ---------------------------------------------------------------------------

def test_root_without_session_redirects(client):
    """GET / without session cookie should redirect to /login."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/login" in response.headers.get("location", "")


def test_api_items_without_session_redirects(client):
    """GET /api/items without session should redirect to /login."""
    response = client.get("/api/items", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert "/login" in response.headers.get("location", "")


# ---------------------------------------------------------------------------
# POST /login — correct credentials
# ---------------------------------------------------------------------------

def test_login_correct_credentials(client):
    """POST /login with correct credentials should set session cookie and redirect."""
    response = client.post(
        "/login",
        data={"username": "admin", "password": "skgifts"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/" == response.headers.get("location", "")
    # Session cookie should be set
    assert "session" in response.cookies


def test_login_wrong_credentials(client):
    """POST /login with wrong credentials should return 401."""
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrongpassword"},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_login_wrong_username(client):
    """POST /login with wrong username should fail."""
    response = client.post(
        "/login",
        data={"username": "wronguser", "password": "skgifts"},
        follow_redirects=False,
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# X-Internal-Key header auth
# ---------------------------------------------------------------------------

def test_api_with_internal_key(client):
    """GET /api/items with correct X-Internal-Key should return 200."""
    response = client.get("/api/items", headers=AUTH_HEADERS)
    assert response.status_code == 200


def test_api_with_wrong_internal_key(client):
    """GET /api/items with wrong X-Internal-Key should redirect."""
    response = client.get(
        "/api/items",
        headers={"X-Internal-Key": "wrong-key"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)


def test_api_with_empty_internal_key(client):
    """
    GET /api/items with empty X-Internal-Key.
    The middleware checks: if _INTERNAL_KEY and header == _INTERNAL_KEY.
    Since env var is set to non-empty "test-internal-key-12345", an empty
    header should NOT match, hence redirect.
    """
    response = client.get(
        "/api/items",
        headers={"X-Internal-Key": ""},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)


# ---------------------------------------------------------------------------
# Session-based access after login
# ---------------------------------------------------------------------------

def test_authenticated_access_via_session(client):
    """After logging in, session cookie grants access."""
    # Login
    login_resp = client.post(
        "/login",
        data={"username": "admin", "password": "skgifts"},
        follow_redirects=False,
    )
    session_cookie = login_resp.cookies.get("session")
    assert session_cookie

    # Access protected endpoint
    response = client.get("/api/items", cookies={"session": session_cookie})
    assert response.status_code == 200
