import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from bb_paxdata.infrastructure.auth.jwt_auth import create_jwt, decode_jwt
from bb_paxdata.infrastructure.db.models import ReviewerAssignment
from bb_paxdata.interfaces.api.dependencies import (
    PermissionChecker,
    get_current_reviewer,
)
from bb_paxdata.interfaces.api.main import app

# Create test router to mount endpoints that verify JWT and RBAC logic
router = APIRouter(prefix="/test-auth")


@router.get("/protected")
def protected_route(reviewer: dict = Depends(get_current_reviewer)):
    return {"reviewer_id": reviewer["reviewer_id"]}


@router.get("/admin")
def admin_route(allowed: bool = Depends(PermissionChecker("admin"))):
    return {"status": "ok"}


# Include the test router in the main app configuration
app.include_router(router)
client = TestClient(app)


@pytest.mark.asyncio
async def test_jwt_lifecycle():
    """Verify that JWT can be generated and decoded correctly."""
    reviewer_id = "test-analyst@paxdata.local"
    token = create_jwt(reviewer_id, roles=["verdict"])

    assert isinstance(token, str)

    decoded = decode_jwt(token)
    assert decoded["reviewer_id"] == reviewer_id
    assert "verdict" in decoded["roles"]


def test_protected_route_unauthorized():
    """Verify that accessing protected route without token returns 403 or 401."""
    response = client.get("/test-auth/protected")
    assert (
        response.status_code == 401
    )  # HTTPBearer returns 401 Unauthorized when credentials missing


def test_protected_route_authorized():
    """Verify that accessing protected route with valid token returns 200."""
    token = create_jwt("reviewer_1@paxdata.int", roles=["verdict"])
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test-auth/protected", headers=headers)

    assert response.status_code == 200
    assert response.json()["reviewer_id"] == "reviewer_1@paxdata.int"


@pytest.mark.asyncio
async def test_admin_route_authorized(test_db_session):
    """Verify that users with administrative assignments can access admin route."""
    # Seed db with an admin reviewer assignment
    admin_assignment = ReviewerAssignment(
        reviewer_id="admin@paxdata.local",
        scope_type="global",
        scope_value="global",
        permission_level="admin",
        is_active=True,
        max_daily_reviews=100,
    )
    test_db_session.add(admin_assignment)
    await test_db_session.commit()

    token = create_jwt("admin@paxdata.local", roles=["admin"])
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test-auth/admin", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_admin_route_forbidden_unassigned(test_db_session):
    """Verify that users without valid database assignments are forbidden."""
    token = create_jwt("unassigned@paxdata.local", roles=["verdict"])
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test-auth/admin", headers=headers)

    # Missing database assignment should trigger a 403 Forbidden
    assert response.status_code == 403
