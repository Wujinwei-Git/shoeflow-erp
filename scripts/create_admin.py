from getpass import getpass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def read_required_value(prompt: str) -> str:
    """读取不能为空的终端输入。"""

    while True:
        value = input(prompt).strip()

        if value:
            return value

        print("该内容不能为空，请重新输入。")


def read_password() -> str:
    """安全读取并确认密码。"""

    while True:
        password = getpass("登录密码（至少 8 位）：")

        if len(password) < 8:
            print("密码不能少于 8 位，请重新输入。")
            continue

        password_confirmation = getpass("再次输入密码：")

        if password != password_confirmation:
            print("两次密码不一致，请重新输入。")
            continue

        return password


def main() -> None:
    """创建第一个管理员账号。"""

    print("创建 ShoeFlow 管理员账号")

    username = read_required_value(
        "登录用户名："
    ).lower()

    display_name = input(
        "显示名称（直接回车默认为“管理员”）："
    ).strip() or "管理员"

    password = read_password()

    with SessionLocal() as db:
        existing_user = db.scalar(
            select(User).where(
                User.username == username
            )
        )

        if existing_user is not None:
            print("创建失败：该用户名已经存在。")
            return

        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add(user)

        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            print("创建失败：该用户名已经存在。")
            return

        print(
            f"管理员创建成功：{user.username}，"
            f"用户编号：{user.id}"
        )


if __name__ == "__main__":
    main()