"""Print an argon2 hash for the admin password.

    python -m app.hashpw

Prompts without echoing. The hash goes in QM_ADMIN_PASSWORD_HASH; the
password itself is never stored anywhere.
"""
import getpass

from argon2 import PasswordHasher

if __name__ == "__main__":
    pw = getpass.getpass("Admin password: ")
    again = getpass.getpass("Again: ")
    if pw != again:
        raise SystemExit("they do not match")
    if len(pw) < 12:
        raise SystemExit("use at least 12 characters")
    print(PasswordHasher().hash(pw))
