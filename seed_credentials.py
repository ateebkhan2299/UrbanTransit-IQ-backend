"""Generate one-time credentials for local database seed scripts."""

import os
import secrets


def get_seed_password(username: str) -> str:
    """Return an explicitly supplied local password or a one-time random value."""
    return os.getenv(f"INITIAL_{username.upper()}_PASSWORD") or secrets.token_urlsafe(18)


def print_seed_credentials(users: list[dict]) -> None:
    print("\nIMPORTANT: If these credentials replaced hardcoded passwords in a prior commit, you MUST clean your Git history (e.g. using BFG or git filter-repo).\nOne-time seed credentials (store securely; they will not be written to disk):")
    for user in users:
        print(f"  {user['username']}: {user['password']}")
