import asyncio

import typer

from core.security import hash_password
from db.postgres import AsyncSessionLocal, init_models
from domain.models.user import UserCreate
from infrastructure.postgres.user_repo import UserRepo

app = typer.Typer(help="Auth service management CLI")


@app.command("create-superuser")
def create_superuser(
    login: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    async def _inner():
        await init_models()
        async with AsyncSessionLocal() as session:
            repo = UserRepo(session)
            existing = await repo.get_by_login(login)
            if existing:
                typer.echo("User with this login already exists")
                raise typer.Exit(code=1)
            pwd_hash = hash_password(password)
            user = await repo.create_user(
                UserCreate(login=login, password=password),
                password_hash=pwd_hash,
                is_superuser=True,
            )
            typer.echo(f"Superuser created: {user.login} (id={user.id})")

    asyncio.run(_inner())


if __name__ == "__main__":
    app()
