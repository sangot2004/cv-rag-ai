import argparse

from getpass import getpass
from datetime import datetime

from src.auth.service import _create_user, hash_password
from src.db.models import AppUser, AuthSession, ChatConversation, Department
from src.db.session import SessionLocal


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("username")
    create.add_argument("--role", choices=["admin", "tester"], required=True)
    create.add_argument("--department-id")
    claim = sub.add_parser("claim-legacy")
    claim.add_argument("username")
    reset = sub.add_parser("reset-password")
    reset.add_argument("username")
    sub.add_parser("departments")
    args = parser.parse_args()

    if args.command == "create":
        password = getpass("Mật khẩu (12–256 ký tự): ")
        if password != getpass("Nhập lại mật khẩu: "):
            parser.error("Hai mật khẩu không khớp.")
        print("Created:", _create_user(args.username, password, args.role, args.department_id))

    elif args.command == "departments":
        with SessionLocal() as db:
            for d in db.query(Department).all():
                print(d.department_id, d.department_name)

    else:
        with SessionLocal() as db:
            user = db.query(AppUser).filter_by(username=args.username.strip().lower()).first()
            if not user:
                parser.error("Không có tài khoản này.")

            if args.command == "claim-legacy":
                if user.role != "admin":
                    parser.error("Chỉ gán hội thoại cũ cho admin.")
                count = db.query(ChatConversation).filter(
                    ChatConversation.owner_user_id.is_(None), ChatConversation.deleted_at.is_(None)
                ).update({"owner_user_id": user.user_id}, synchronize_session=False)
                print("Assigned:", count)
            else:
                password = getpass("Mật khẩu mới: ")
                if password != getpass("Nhập lại mật khẩu: "):
                    parser.error("Hai mật khẩu không khớp.")
                user.password_hash = hash_password(password)
                user.failed_attempts = 0
                user.locked_until = None
                db.query(AuthSession).filter_by(user_id=user.user_id).delete()

            db.commit()


if __name__ == "__main__":
    main()
