from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserLogin
from app.core.security import get_password_hash, verify_password


async def login_user(db: AsyncSession, user_data: UserLogin) -> User:
    result = await db.execute(select(User).where(User.login == user_data.login))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("Invalid login")
    if not verify_password(user_data.password, user.hashed_password):
        raise ValueError("Invalid password")
    return user