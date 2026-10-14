"""Administrative account bootstrap and password-reset CLI utility.

Safely provisions or resets the local development platform administrator account
without exposing secrets in source control or guessing passwords.
"""

import argparse
import asyncio
import logging
import os
import secrets
import sys
import uuid
from sqlalchemy import func, select

from backend.auth.crypto import hash_password
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
    full_name: str,
    password: str | None = None,
) -> dict[str, str]:
    """
    Provisions or resets the specified administrator account in PostgreSQL.
    Returns account details including login email, user ID, and password used.
    """
    normalized_email = email.strip().lower()
    
    # Generate secure high-entropy password if not explicitly supplied
    generated_pw = False
    if not password:
        password = secrets.token_urlsafe(16)
        generated_pw = True

    if len(password) < 8:
        raise ValueError("Admin password must be at least 8 characters long.")

    hashed_pw = hash_password(password)

    async with AsyncSessionLocal() as session:
        auth_service = AuthService(session)

        # Check existing user
        result = await session.execute(
            select(User).where(func.lower(User.email) == normalized_email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info(f"Found existing user '{existing_user.email}' (ID: {existing_user.id}). Updating to active admin...")
            existing_user.role = "admin"
            existing_user.is_active = True
            existing_user.hashed_password = hashed_pw
            if full_name:
                existing_user.full_name = full_name.strip()

            # Revoke existing sessions upon password reset
            await auth_service.revoke_all_user_sessions(existing_user.id)

            record_audit_log(
                session=session,
                action="admin_account_reset",
                entity_type="user",
                entity_id=str(existing_user.id),
                actor_id=existing_user.id,
                details={"email": normalized_email, "role": "admin", "reason": "bootstrap_cli_reset"},
            )
            await session.commit()
            await session.refresh(existing_user)
            admin_user = existing_user
            action_performed = "reset"
        else:
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
                details={"email": normalized_email, "role": "admin", "reason": "bootstrap_cli_create"},
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
        "password": password,
        "was_generated": str(generated_pw),
    }


def main():
    parser = argparse.ArgumentParser(description="Bootstrap or reset the local RouteX administrator account.")
    parser.add_argument(
        "--email",
        type=str,
        default=os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@routex.ai"),
        help="Administrator email (default: env ADMIN_BOOTSTRAP_EMAIL or admin@routex.ai)",
    )
    parser.add_argument(
        "--full-name",
        type=str,
        default=os.environ.get("ADMIN_BOOTSTRAP_NAME", "RouteX Administrator"),
        help="Administrator full name (default: RouteX Administrator)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=os.environ.get("ADMIN_BOOTSTRAP_PASSWORD"),
        help="Administrator password (optional; auto-generates secure random password if omitted)",
    )

    args = parser.parse_args()

    try:
        details = asyncio.run(bootstrap_admin(
            email=args.email,
            full_name=args.full_name,
            password=args.password,
        ))
        print("\n" + "=" * 60)
        print(f" RouteX Administrator Account Successfully {details['action'].upper()}! ")
        print("=" * 60)
        print(f" User ID:    {details['user_id']}")
        print(f" Email:      {details['email']}")
        print(f" Full Name:  {details['full_name']}")
        print(f" Role:       {details['role']}")
        print(f" Active:     {details['is_active']}")
        print(f" Password:   {details['password']}")
        if details["was_generated"] == "True":
            print(" Note:       Password was cryptographically generated. Store it securely.")
        print("=" * 60 + "\n")
    except Exception as exc:
        logger.error(f"Failed to bootstrap administrator account: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
