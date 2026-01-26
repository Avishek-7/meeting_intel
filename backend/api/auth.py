from fastapi import APIRouter, HTTPException, status
from core.security import create_access_token, verify_password
from schemas.auth import LoginRequest
from core.users import fake_users_db

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login")
def login(request: LoginRequest):
    user = fake_users_db.get(request.username)

    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}