"""
Generate the admin password hash and JWT secret for your .env file.

Run from anywhere:
    python scripts/make_admin_credentials.py

Then paste the two printed lines into your .env file.
"""

import getpass
import secrets
import sys

import bcrypt


def main() -> None:
    password = getpass.getpass("Choose an admin password: ")
    confirm = getpass.getpass("Repeat the password: ")

    if password != confirm:
        sys.exit("Passwords do not match.")

    if len(password) < 10:
        sys.exit("Use at least 10 characters.")

    if len(password.encode("utf-8")) > 72:
        sys.exit("bcrypt only supports passwords up to 72 bytes.")

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()

    print("\nAdd these lines to your .env file")
    print("(single quotes around the hash are required because it contains $):\n")
    print(f"ADMIN_USERNAME=admin")
    print(f"ADMIN_PASSWORD_HASH='{hashed}'")
    print(f"JWT_SECRET_KEY={secrets.token_urlsafe(48)}")


if __name__ == "__main__":
    main()
