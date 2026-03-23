import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_access_token,
    is_refresh_token,
    verify_password,
)
from core.settings import settings
from db.postgres import get_session
from db.redis import get_redis
from domain.models.tokens import TokenPair
from domain.models.user import LoginRequest, UserCreate, UserProfile, UserRead
from infrastructure.postgres.role_repo import RoleRepo
from infrastructure.postgres.social_repo import SocialRepo
from infrastructure.postgres.token_repo import TokenRepo
from infrastructure.postgres.user_repo import UserRepo
from infrastructure.redis.cache import TokenBlacklist


def _now_utc() -> datetime:
    aware = datetime.now(timezone.utc)
    return aware.replace(tzinfo=None)


def _hash_token(token: str) -> str:
    """Храним refresh-токен в БД не в сыром виде, а как digest."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Optional[Redis],
    ):
        self.session = session
        self.user_repo = UserRepo(session)
        self.role_repo = RoleRepo(session)
        self.token_repo = TokenRepo(session)
        self.social_repo = SocialRepo(session)
        self.blacklist = TokenBlacklist(redis)

    # ---------- ВСПОМОГАТЕЛЬНОЕ ----------

    async def _issue_token_pair(
        self,
        *,
        user,
        roles: list[str],
        user_agent: str | None,
        client_ip: str | None,
        action: str,
    ) -> TokenPair:
        access = create_access_token(
            subject=str(user.id),
            roles=roles,
            is_superuser=user.is_superuser,
            token_version=user.token_version,
        )

        refresh_raw = create_refresh_token(subject=str(user.id))
        refresh_hash = _hash_token(refresh_raw)

        now = _now_utc()
        expires_at = now + timedelta(seconds=settings.REFRESH_TOKEN_EXPIRES_IN)

        await self.token_repo.add_refresh_token(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            client_ip=client_ip,
        )
        await self.token_repo.add_login_event(
            user_id=user.id,
            action=action,
            user_agent=user_agent,
            client_ip=client_ip,
        )

        return TokenPair(
            access_token=access,
            refresh_token=refresh_raw,
            expires_in=settings.ACCESS_TOKEN_EXPIRES_IN,
        )

    async def _unique_login(self, base: str) -> str:
        login = base
        i = 0
        while await self.user_repo.get_by_login(login):
            i += 1
            login = f"{base}_{i}"
        return login

    async def _load_user_profile(self, user_id: UUID) -> UserProfile:
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        roles = await self.role_repo.get_user_roles(user.id)
        return UserProfile(
            id=user.id,
            login=user.login,
            roles=roles,
            is_superuser=user.is_superuser,
        )

    # ---------- OAuth social login ----------

    async def login_via_social(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str | None,
        user_agent: str | None,
        client_ip: str | None,
    ) -> TokenPair:
        linked = await self.social_repo.get_by_provider_user_id(
            provider, provider_user_id
        )
        if linked:
            user = await self.user_repo.get_by_id(linked.user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=401, detail="User not found or inactive"
                )
            roles = await self.role_repo.get_user_roles(user.id)
            return await self._issue_token_pair(
                user=user,
                roles=roles,
                user_agent=user_agent,
                client_ip=client_ip,
                action=f"oauth:{provider}",
            )

        # нет линка — создаём пользователя или линкуем к существующему по login=email (если совпадает)
        chosen_login = None
        user = None

        if email:
            existing = await self.user_repo.get_by_login(email)
            if existing:
                user = existing
                chosen_login = existing.login
            else:
                chosen_login = await self._unique_login(email)

        if not chosen_login:
            chosen_login = await self._unique_login(f"{provider}_{provider_user_id}")

        if user is None:
            # пароль пользователю не нужен (он будет логиниться через OAuth),
            # но в БД password_hash обязателен
            raw_pwd = secrets.token_urlsafe(24)
            pwd_hash = hash_password(raw_pwd)
            user = await self.user_repo.create_user(
                UserCreate(login=chosen_login, password="123456"),
                password_hash=pwd_hash,
                is_superuser=False,
            )

        await self.social_repo.create(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )

        try:
            await self.role_repo.assign_role(user.id, "user")
        except ValueError:
            pass

        roles = await self.role_repo.get_user_roles(user.id)
        return await self._issue_token_pair(
            user=user,
            roles=roles,
            user_agent=user_agent,
            client_ip=client_ip,
            action=f"oauth:{provider}",
        )

    # ---------- API: signup / login / refresh ----------

    async def register_user(self, data: UserCreate) -> UserRead:
        existing = await self.user_repo.get_by_login(data.login)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this login already exists",
            )
        pwd_hash = hash_password(data.password)
        try:
            user = await self.user_repo.create_user(
                data, password_hash=pwd_hash, is_superuser=False
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this login already exists",
            )

        # назначим базовую роль user, если она существует
        try:
            await self.role_repo.assign_role(user.id, "user")
        except ValueError:
            pass

        return UserRead(id=user.id, login=user.login)

    async def login(
        self,
        credentials: LoginRequest,
        user_agent: str | None,
        client_ip: str | None,
    ) -> TokenPair:
        user = await self.user_repo.get_by_login(credentials.login)
        if not user or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid login or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is inactive",
            )

        roles = await self.role_repo.get_user_roles(user.id)
        return await self._issue_token_pair(
            user=user,
            roles=roles,
            user_agent=user_agent,
            client_ip=client_ip,
            action="login",
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: str | None,
        client_ip: str | None,
    ) -> TokenPair:
        try:
            payload = decode_token(refresh_token)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token is invalid",
            )
        if not is_refresh_token(payload):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not refresh",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload",
            )

        refresh_hash = _hash_token(refresh_token)

        token_row = await self.token_repo.get_by_hash(refresh_hash)
        if not token_row or token_row.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token revoked or not found",
            )
        if token_row.expires_at < _now_utc():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        roles = await self.role_repo.get_user_roles(user.id)

        # old refresh -> revoked, выдаём новую пару
        await self.token_repo.revoke(token_row)

        return await self._issue_token_pair(
            user=user,
            roles=roles,
            user_agent=user_agent,
            client_ip=client_ip,
            action="refresh",
        )

    # ---------- API: текущий пользователь / logout ----------

    async def get_current_user(self, access_token: str) -> UserProfile:
        try:
            payload = decode_token(access_token)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )
        if not is_access_token(payload):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not access",
            )

        jti = payload.get("jti")
        if jti and await self.blacklist.is_blacklisted(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is revoked",
            )

        user_id = payload.get("sub")
        token_version = payload.get("token_version")
        if not user_id or token_version is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload",
            )

        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        if user.token_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is outdated (logout from other devices performed)",
            )

        roles = await self.role_repo.get_user_roles(user.id)
        return UserProfile(
            id=user.id,
            login=user.login,
            roles=roles,
            is_superuser=user.is_superuser,
        )

    async def logout(
        self,
        access_token: str,
        user: UserProfile,
        *,
        user_agent: str | None,
        client_ip: str | None,
    ) -> None:
        """Logout из текущей сессии.

        - Кладёт access-токен в blacklist (best-effort через Redis).
        - Отзывает refresh-токены текущей сессии по (user_agent, client_ip).
        """
        try:
            payload = decode_token(access_token)
        except jwt.PyJWTError:
            payload = None

        if payload and is_access_token(payload):
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                now = int(_now_utc().timestamp())
                ttl = exp - now
                if ttl > 0:
                    await self.blacklist.blacklist(jti, ttl)

        # revoke refresh-токены текущей "сессии"
        await self.token_repo.revoke_for_user_session(
            user_id=user.id,
            user_agent=user_agent,
            client_ip=client_ip,
        )

        await self.token_repo.add_login_event(
            user_id=user.id,
            action="logout",
            user_agent=user_agent,
            client_ip=client_ip,
        )

    async def logout_others(self, user: UserProfile) -> None:
        """Выход из остальных аккаунтов.

        Увеличивает `token_version` и ревокает все refresh-токены пользователя.
        """
        await self.user_repo.increment_token_version(user.id)
        await self.token_repo.revoke_all_for_user(user.id)
        await self.token_repo.add_login_event(
            user_id=user.id,
            action="logout_all",
            user_agent=None,
            client_ip=None,
        )


# ---------- DI ----------


def get_auth_service(
    session: AsyncSession = Depends(get_session),
    redis: Optional[Redis] = Depends(get_redis),
) -> AuthService:
    return AuthService(session=session, redis=redis)
