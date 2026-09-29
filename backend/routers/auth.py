import hashlib
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models_db import User, AuditLog  # This might also need fixing
from backend.schemas import UserLogin, Token, UserOut, AuditLogSchema, UserCreate, UserUpdate

VALID_ROLES = ["Admin", "Operator", "Analyst", "Evaluator"]

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ISSUER = os.getenv("JWT_ISSUER", "urbantransit-iq")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "urbantransit-iq-api")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", "3600"))

router = APIRouter(prefix="/api/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

def _require_jwt_secret() -> str:
    if not JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY must be configured before starting the API")
    return JWT_SECRET_KEY

import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        # Fallback to sha256 temporarily to support seeded demo users who have sha256 hashes
        import hashlib
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == hashed_password


def create_access_token(data: dict, expires_delta_seconds: Optional[int] = None) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update({
        "iat": now,
        "exp": now + timedelta(seconds=expires_delta_seconds or JWT_EXPIRE_SECONDS),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    })
    return jwt.encode(payload, _require_jwt_secret(), algorithm="HS256")

def decode_access_token(token_str: str) -> dict:
    try:
        return jwt.decode(
            token_str,
            _require_jwt_secret(),
            algorithms=["HS256"],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid authentication token") from exc

def log_audit(db: Session, username: str, role: str, action: str, endpoint: str, details: Optional[str] = None):
    audit_entry = AuditLog(
        username=username,
        role=role,
        action=action,
        endpoint=endpoint,
        details=details
    )
    db.add(audit_entry)
    db.commit()

def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = decode_access_token(token)
            username: str = payload.get("sub")
            if username:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_active:
                    return user
        except Exception:
            pass
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid authentication token")

def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access forbidden: requires one of roles {allowed_roles}")
        return current_user
    return role_checker


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == credentials.username).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    log_audit(db, user.username, user.role, "USER_LOGIN", "/api/auth/login", "Successful authentication")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name
        }
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        full_name=current_user.full_name,
        is_active=current_user.is_active
    )

@admin_router.get("/audit-trail", response_model=List[AuditLogSchema])
def get_audit_trail(db: Session = Depends(get_db), current_user: User = Depends(require_roles(["Admin", "Evaluator"]))):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(100).all()
    return [
        AuditLogSchema(
            id=l.id,
            username=l.username,
            role=l.role,
            action=l.action,
            endpoint=l.endpoint,
            details=l.details,
            timestamp=str(l.timestamp)
        )
        for l in logs
    ]

def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email or "",
        role=u.role,
        full_name=u.full_name or "",
        is_active=u.is_active
    )

@admin_router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_roles(["Admin", "Evaluator"]))):
    users = db.query(User).order_by(User.id.asc()).all()
    return [_user_out(u) for u in users]

@admin_router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["Admin"]))):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {VALID_ROLES}")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    if body.email and db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        full_name=body.full_name,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(db, current_user.username, current_user.role, "CREATE_USER", "/api/admin/users", f"Created user {user.username} ({user.role})")
    return _user_out(user)

@admin_router.put("/users/{username}", response_model=UserOut)
def update_user(username: str, body: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["Admin"]))):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    changes = []
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of {VALID_ROLES}")
        if user.role != body.role:
            changes.append(f"role {user.role}->{body.role}")
            if user.role == "Admin" and body.role != "Admin":
                admins = db.query(User).filter(User.role == "Admin", User.is_active == True).count()
                if admins <= 1:
                    raise HTTPException(status_code=400, detail="Cannot demote the last active Admin")
        user.role = body.role
    if body.email is not None and body.email != user.email:
        if body.email and db.query(User).filter(User.email == body.email, User.username != username).first():
            raise HTTPException(status_code=400, detail="Email already in use")
        changes.append("email")
        user.email = body.email
    if body.full_name is not None and body.full_name != user.full_name:
        changes.append("full_name")
        user.full_name = body.full_name
    if body.is_active is not None and body.is_active != user.is_active:
        if user.username == current_user.username and body.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        if user.role == "Admin" and user.is_active and not body.is_active:
            admins = db.query(User).filter(User.role == "Admin", User.is_active == True).count()
            if admins <= 1:
                raise HTTPException(status_code=400, detail="Cannot deactivate the last active Admin")
        changes.append(f"active->{body.is_active}")
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = hash_password(body.password)
        changes.append("password reset")
    if not changes:
        return _user_out(user)
    db.commit()
    db.refresh(user)
    log_audit(db, current_user.username, current_user.role, "UPDATE_USER", f"/api/admin/users/{username}", f"Updated {username}: {', '.join(changes)}")
    return _user_out(user)

@admin_router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(username: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["Admin"]))):
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "Admin":
        admins = db.query(User).filter(User.role == "Admin", User.is_active == True).count()
        if admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last active Admin")
    db.delete(user)
    db.commit()
    log_audit(db, current_user.username, current_user.role, "DELETE_USER", f"/api/admin/users/{username}", f"Deleted user {username}")
