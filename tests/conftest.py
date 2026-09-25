"""
Test configuration and shared fixtures.

The AuthMiddleware in main.py checks for a session cookie or an
X-Internal-Key header. We set INTERNAL_API_KEY in the environment
*before* importing main so the middleware reads it; every TestClient
call then includes AUTH_HEADERS to bypass authentication.

Database strategy
-----------------
Each test function gets a completely isolated in-memory SQLite database.
We achieve this by:
  1. Creating a new engine + session for every test via the `db` fixture.
  2. Making the `client` fixture depend on `db` so they share the same
     session / connection.  The dependency override replaces `get_db`
     with a generator that yields the same session object.
  3. Because the `client` fixture always depends on `db`, tests that
     only request `client` still get a properly initialised database.
"""
import os

# Must be set before importing main so AuthMiddleware picks it up.
os.environ["INTERNAL_API_KEY"] = "test-internal-key-12345"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app import models
from app.security import hash_password
from main import app

# Header sent with every test request to bypass AuthMiddleware.
AUTH_HEADERS = {"X-Internal-Key": "test-internal-key-12345"}

# Matches the app's own default-admin seed (see main.py) so session-cookie
# login tests have a real user to authenticate against.
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "skgifts"


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db():
    """
    Provides a fresh SQLAlchemy session backed by a new in-memory SQLite
    database for every test function.  All tables are created before the
    test runs and dropped afterwards.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        # StaticPool ensures all connections share the same in-memory DB.
        # Without this, each new connection (e.g. from db.refresh()) would
        # get a separate, empty in-memory database and fail with
        # "no such table" errors.
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(models.User(
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        role="ADMIN",
    ))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db):
    """
    TestClient wired to the same test database session as `db`.
    Because `client` depends on `db`, every test that requests `client`
    automatically gets a fresh, isolated database.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # session lifecycle managed by the `db` fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_item(db):
    """A standard inventory item with quantity=100."""
    item = models.Item(
        name="Test Item",
        quantity=100,
        cost_price=50.0,
        selling_price=100.0,
        gst_rate=18.0,
        low_stock_threshold=10,
        unit="pcs",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def sample_item_b(db):
    """A second inventory item with a lower quantity."""
    item = models.Item(
        name="Item B",
        quantity=50,
        cost_price=20.0,
        selling_price=40.0,
        gst_rate=5.0,
        unit="pcs",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def sample_supplier(db):
    supplier = models.Supplier(name="Test Supplier")
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@pytest.fixture
def sample_customer(db):
    customer = models.Customer(name="Test Customer", customer_type="retailer")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@pytest.fixture
def sample_viewer_user(db):
    """A non-admin user, for testing that role-gated endpoints reject them."""
    user = models.User(username="viewer1", password_hash=hash_password("viewerpass123"), role="VIEWER")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_as(client, username: str, password: str) -> dict:
    """Logs in via the real /login form flow and returns cookies usable on
    subsequent session-authenticated requests."""
    resp = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
    return {"session": resp.cookies.get("session")}
