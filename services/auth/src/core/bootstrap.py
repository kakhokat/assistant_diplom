from __future__ import annotations

import logging

from core.security import hash_password
from core.settings import settings
from db.postgres import AsyncSessionLocal
from domain.models.role import RoleCreate
from domain.models.user import UserCreate
from infrastructure.postgres.role_repo import RoleRepo
from infrastructure.postgres.user_repo import UserRepo

logger = logging.getLogger("auth.bootstrap")


async def ensure_bootstrap_admin() -> None:
    if not settings.BOOTSTRAP_ADMIN_ENABLED:
        logger.info("Bootstrap admin disabled")
        return

    login = (settings.BOOTSTRAP_ADMIN_LOGIN or "").strip()
    password = (settings.BOOTSTRAP_ADMIN_PASSWORD or "").strip()

    if not login or not password:
        logger.warning("Bootstrap admin login/password are empty; skipping")
        return

    async with AsyncSessionLocal() as session:
        role_repo = RoleRepo(session)

        # Ensure base roles exist
        for role_name in ("user", "admin"):
            role = await role_repo.get_role_by_name(role_name)
            if not role:
                await role_repo.create_role(
                    RoleCreate(name=role_name, description=None)
                )
                logger.info("Created role: %s", role_name)

        user_repo = UserRepo(session)
        user = await user_repo.get_by_login(login)

        pwd_hash = hash_password(password)

        if not user:
            user = await user_repo.create_user(
                UserCreate(login=login, password=password),
                password_hash=pwd_hash,
                is_superuser=True,
            )
            logger.info("Created bootstrap admin user: %s", login)
        else:
            # Ensure admin flags and password are set deterministically
            user.is_superuser = True
            user.password_hash = pwd_hash
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info("Updated bootstrap admin user: %s", login)

        try:
            await role_repo.assign_role(user.id, "admin")
        except ValueError:
            # role not found shouldn't happen due to ensure above
            pass
