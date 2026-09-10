from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User, UserRole


client = TestClient(app)

TEST_USERNAME = "testadmin"
TEST_PASSWORD = "StrongPass123!"


def create_test_user(
    *,
    is_active: bool = True,
) -> None:
    """在测试数据库中创建管理员账号。"""

    with SessionLocal() as db:
        user = User(
            username=TEST_USERNAME,
            password_hash=hash_password(
                TEST_PASSWORD
            ),
            display_name="测试管理员",
            role=UserRole.ADMIN,
            is_active=is_active,
        )

        db.add(user)
        db.commit()


def test_login_and_get_current_user() -> None:
    """测试登录并查询当前用户。"""

    create_test_user()

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    login_data = login_response.json()["data"]

    assert login_data["access_token"]
    assert login_data["token_type"] == "bearer"
    assert login_data["expires_in"] == 28800
    assert login_data["user"]["username"] == TEST_USERNAME
    assert login_data["user"]["role"] == "admin"
    assert "password_hash" not in login_data["user"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {login_data['access_token']}"
            ),
        },
    )

    assert me_response.status_code == 200
    assert (
        me_response.json()["data"]["username"]
        == TEST_USERNAME
    )


def test_wrong_password_is_rejected() -> None:
    """测试密码错误时拒绝登录。"""

    create_test_user()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["code"]
        == "INVALID_CREDENTIALS"
    )


def test_unknown_username_is_rejected() -> None:
    """测试用户名不存在时拒绝登录。"""

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "missing-user",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 401
    assert (
        response.json()["code"]
        == "INVALID_CREDENTIALS"
    )


def test_inactive_user_is_rejected() -> None:
    """测试停用账号不能登录。"""

    create_test_user(
        is_active=False,
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "USER_INACTIVE"


def test_missing_token_is_rejected() -> None:
    """测试未携带令牌时不能查询当前用户。"""

    response = client.get(
        "/api/v1/auth/me"
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_invalid_token_is_rejected() -> None:
    """测试伪造令牌不能通过鉴权。"""

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"