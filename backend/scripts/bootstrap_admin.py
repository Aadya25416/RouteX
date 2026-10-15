"""Administrative account bootstrap and password-reset CLI utility.

Safely provisions or resets the RouteX platform administrator account in PostgreSQL
without exposing secrets in source control or overwriting existing administrator accounts.

Security guarantees:
1. Idempotency: Running this script when an admin already exists is a safe no-op unless --reset-password is explicitly passed.
2. Conflict prevention: If an existing user has a non-admin role (e.g. 'driver'), the script aborts immediately to prevent accidental privilege escalation.
3. Session invalidation: Resetting an admin password terminates all active refresh tokens and sessions.
4. Secret privacy: User-supplied passwords are never echoed back to stdout or logs. Cryptographically generated passwords are displayed exactly once.
"""

import argparse
import asyncio
import getpass
import logging
import os
import secrets
import sys
import uuid
from typing import Any

from sqlalchemy import func, select

from backend.auth.crypto import hash_password
from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.models.users import User
from backend.services.auth_service import AuthService
from backend.services.events import record_audit_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bootstrap_admin")


async def bootstrap_admin(
    email: str,
    full_name: str | None = None,
    password: str | None = None,
    reset_password: bool = False,
    is_interactive: bool = False,
) -> dict[str, Any]:
    """
    Provisions or verifies the specified administrator account in PostgreSQL.
    
    Returns account details dictionary describing the action performed.
    """
    normalized_email = email.strip().lower()
    if "@" not in normalized_email or len(normalized_email) < 5:
        raise ValueError(f"Invalid email address provided: '{email}'")

    async with AsyncSessionLocal() as session:
        auth_service = AuthService(session)

        # 1. Check existing user
        result = await session.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        existing_user = result.scalar_one_or_none()

        # 2. Check for role conflict (e.g., driver account)
        if existing_user and existing_user.role != "admin":
            raise ValueError(
                f"User '{normalized_email}' already exists with role '{existing_user.role}'. "
                f"Cannot convert non-admin user to admin via bootstrap script to prevent privilege escalation."
            )

        # 3. Handle existing admin account
        if existing_user and existing_user.role == "admin":
            if not reset_password:
                logger.info(
                    f"Administrator '{normalized_email}' (ID: {existing_user.id}) already exists. "
                    "Account is active and credentials were not modified (use --reset-password to overwrite)."
                )
                return {
                    "action": "verified_existing",
                    "user_id": str(existing_user.id),
                    "email": existing_user.email,
                    "full_name": existing_user.full_name,
                    "role": existing_user.role,
                    "is_active": str(existing_user.is_active),
                    "password_changed": False,
                    "generated_password": None,
                }

        # 4. Determine password to use (for creation or reset)
        was_generated = False
        resolved_password = password
        if not resolved_password:
            resolved_password = (
                os.environ.get("ADMIN_PASSWORD")
                or os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
                or getattr(settings, "ADMIN_PASSWORD", getattr(settings, "ADMIN_BOOTSTRAP_PASSWORD", None))
            )

        if not resolved_password and is_interactive and sys.stdin.isatty():
            prompt_text = "Enter new administrator password (leave blank to auto-generate): "
            entered = getpass.getpass(prompt_text).strip()
            if entered:
                confirm = getpass.getpass("Confirm password: ").strip()
                if entered != confirm:
                    raise ValueError("Passwords entered do not match.")
                resolved_password = entered
            else:
                resolved_password = secrets.token_urlsafe(20)
                was_generated = True
        elif not resolved_password:
            resolved_password = secrets.token_urlsafe(20)
            was_generated = True

        if len(resolved_password) < 8:
            raise ValueError("Admin password must be at least 8 characters long.")

        hashed_pw = hash_password(resolved_password)

        if existing_user:
            # Updating existing admin
            logger.info(f"Resetting credentials for administrator '{normalized_email}' (ID: {existing_user.id})...")
            existing_user.is_active = True
            existing_user.hashed_password = hashed_pw
            if full_name:
                existing_user.full_name = full_name.strip()

            # Revoke all active sessions upon password reset
            await auth_service.revoke_all_user_sessions(existing_user.id)

            record_audit_log(
                session=session,
                action="admin_account_reset",
                entity_type="user",
                entity_id=str(existing_user.id),
                actor_id=existing_user.id,
                details={
                    "email": normalized_email,
                    "role": "admin",
                    "reason": "bootstrap_cli_reset",
                },
            )
            await session.commit()
            await session.refresh(existing_user)
            admin_user = existing_user
            action_performed = "reset"
        else:
            # Creating new admin
            logger.info(f"Creating new administrator account for '{normalized_email}'...")
            admin_user = User(
                id=uuid.uuid4(),
                email=normalized_email,
                full_name=full_name.strip() if full_name else "RouteX Administrator",
                hashed_password=hashed_pw,
                role="admin",
                is_active=True,
                preferred_language="en",
            )
            session.add(admin_user)
            await session.flush()

            record_audit_log(
                session=session,
                action="admin_account_bootstrapped",
                entity_type="user",
                entity_id=str(admin_user.id),
                actor_id=admin_user.id,
                details={
                    "email": normalized_email,
                    "role": "admin",
                    "reason": "bootstrap_cli_create",
                },
            )
            await session.commit()
            await session.refresh(admin_user)
            action_performed = "created"

    return {
        "action": action_performed,
        "user_id": str(admin_user.id),
        "email": admin_user.email,
        "full_name": admin_user.full_name,
        "role": admin_user.role,
        "is_active": str(admin_user.is_active),
        "password_changed": True,
        "generated_password": resolved_password if was_generated else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap or reset the RouteX administrator account in PostgreSQL."
    )
    default_email = (
        os.environ.get("ADMIN_EMAIL")
        or os.environ.get("ADMIN_BOOTSTRAP_EMAIL")
        or getattr(settings, "ADMIN_EMAIL", getattr(settings, "ADMIN_BOOTSTRAP_EMAIL", "admin@routex.ai"))
    )
    default_name = (
        os.environ.get("ADMIN_NAME")
        or os.environ.get("ADMIN_BOOTSTRAP_NAME")
        or getattr(settings, "ADMIN_NAME", getattr(settings, "ADMIN_BOOTSTRAP_NAME", "RouteX Administrator"))
    )
    default_pw = (
        os.environ.get("ADMIN_PASSWORD")
        or os.environ.get("ADMIN_BOOTSTRAP_PASSWORD")
        or getattr(settings, "ADMIN_PASSWORD", getattr(settings, "ADMIN_BOOTSTRAP_PASSWORD", None))
    )

    parser.add_argument(
        "--email",
        type=str,
        default=default_email,
        help=f"Administrator email (default: {default_email})",
    )
    parser.add_argument(
        "--full-name",
        type=str,
        default=default_name,
        help=f"Administrator full name (default: {default_name})",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=default_pw,
        help="Administrator password (if omitted, prompts interactively or generates random secret)",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        default=False,
        help="Explicitly reset password and revoke sessions if administrator already exists",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        default=False,
        help="Do not prompt interactively for password; generate random if omitted",
    )

    args = parser.parse_args()

    try:
        details = asyncio.run(
            bootstrap_admin(
                email=args.email,
                full_name=args.full_name,
                password=args.password,
                reset_password=args.reset_password,
                is_interactive=not args.non_interactive,
            )
        )
        print("\n" + "=" * 65)
        print(f" RouteX Administrator Account: {details['action'].upper()} ")
        print("=" * 65)
        print(f" User ID:    {details['user_id']}")
        print(f" Email:      {details['email']}")
        print(f" Full Name:  {details['full_name']}")
        print(f" Role:       {details['role']}")
        print(f" Active:     {details['is_active']}")

        if details["action"] == "verified_existing":
            print(" Status:     Admin account already present. Credentials untouched.")
            print(" Note:       Pass --reset-password if you wish to overwrite credentials.")
        elif details["generated_password"]:
            print(f" Password:   {details['generated_password']}")
            print(" Notice:     Generated cryptographically. Store this password securely now!")
        else:
            print(" Password:   [CONFIGURED - Suppressed for security]")
        print("=" * 65 + "\n")
    except Exception as exc:
        logger.error(f"Failed to bootstrap administrator account: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
