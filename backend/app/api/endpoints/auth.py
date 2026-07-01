from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == data.username.lower(), User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    child_id = None
    if user.role == UserRole.child:
        child_result = await db.execute(
            select(Child).where(Child.user_id == user.id)
        )
        child = child_result.scalar_one_or_none()
        if child:
            child_id = child.id

    token = create_access_token(user.id, {"role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        user_id=user.id,
        child_id=child_id,
    )


@router.post("/register-parent", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_parent(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == data.username.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=data.username.lower(),
        hashed_password=hash_password(data.password),
        role=UserRole.parent,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(user.id, {"role": user.role.value})
    return TokenResponse(access_token=token, role=user.role.value, user_id=user.id)
