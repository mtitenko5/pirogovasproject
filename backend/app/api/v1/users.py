from fastapi import APIRouter, Depends, HTTPException,status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import UserLogin,TokenOut

from app.services import user_service

from app.core.database import get_db
from app.core.security import create_access_token
 
router = APIRouter(prefix="/users", tags=["users"])
   
@router.post("/login", response_model=TokenOut, status_code=status.HTTP_200_OK)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    try:
        user_data = UserLogin(
            login=form_data.username,
            password=form_data.password,
        )
        user = await user_service.login_user(db, user_data)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login or password", headers={"WWW-Authenticate": "Bearer"})

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")

    data_for_token = {"sub": user.login, "role": user.role.value, "organization_name": user.organization_name}
    jwt_token = create_access_token(data_for_token)
    return TokenOut(access_token=jwt_token, token_type="bearer")
