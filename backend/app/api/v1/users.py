from fastapi import APIRouter, Depends, HTTPException,status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.user import (
    UserLogin,
    TokenOut,
    UserFioRoleOut,
    UserShortOut,
    UserFullOut,
    ChangePasswordRequest,
)

from app.services import user_service

from app.core.database import get_db
from app.core.security import create_access_token

from app.models.user import User
from app.api.dependencies import get_current_active_user
 
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

@router.get("/me/fio-role", response_model=UserFioRoleOut)
async def get_my_fio_role(
    current_user: User = Depends(get_current_active_user),
):
    return UserFioRoleOut(
        fio=user_service.build_fio(current_user),
        role=current_user.role,
    )

@router.get("/me/short", response_model=UserShortOut)
async def get_my_short_info(
    current_user: User = Depends(get_current_active_user),
):
    return UserShortOut(
        fio=user_service.build_fio(current_user),
        login=current_user.login,
        organization_name=current_user.organization_name,
    )

@router.get("/me/full", response_model=UserFullOut)
async def get_my_full_info(
    current_user: User = Depends(get_current_active_user),
):
    return current_user

@router.post("/me/change-password")
async def change_my_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    await user_service.change_password(
        db=db,
        user=current_user,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    return {"message": "Password changed successfully"}