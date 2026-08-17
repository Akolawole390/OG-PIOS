from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import get_current_user, require_role
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit import AuditAction, record_audit_event

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    role: str | None = Query(None, description="Filter by exact role name, e.g. 'Maintenance Engineer'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    """Read-only user lookup — used to populate the Maintenance module's technician-assignment
    dropdown. Deliberately left unpaginated and active-only, exactly as it was before this
    module, so that existing caller is unaffected. The Administration module's own paginated,
    fully-filterable user list is a separate endpoint — see `GET /administration/users`."""
    query = db.query(User).filter(User.is_active.is_(True)).order_by(User.full_name)
    if role:
        query = query.join(Role).filter(Role.name == role)
    return query.all()


def _get_user_or_404(db: Session, id: int) -> User:
    user = db.query(User).options(joinedload(User.role)).filter(User.id == id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/{id}", response_model=UserRead)
def get_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> User:
    return _get_user_or_404(db, id)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> User:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user with this email already exists")
    if db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=payload.role_id,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    record_audit_event(
        db, current_user, AuditAction.USER_CREATED, "user", resource_id=user.id,
        details=f"Created user {user.email}",
        metadata={"role_id": user.role_id},
    )
    return _get_user_or_404(db, user.id)


@router.put("/{id}", response_model=UserRead)
def update_user(
    id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> User:
    """Never accepts a password change here — this endpoint is for profile/role/active-status
    administration only, never for touching `hashed_password`, and never returns it either
    (`UserRead` has no such field)."""
    user = _get_user_or_404(db, id)

    name_changed = payload.full_name is not None and payload.full_name != user.full_name
    role_changed = payload.role_id is not None and payload.role_id != user.role_id
    active_changed = payload.is_active is not None and payload.is_active != user.is_active

    if role_changed and db.get(Role, payload.role_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    old_role_name = user.role.name

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role_id is not None:
        user.role_id = payload.role_id
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.commit()
    db.refresh(user)

    if role_changed:
        record_audit_event(
            db, current_user, AuditAction.ROLE_CHANGED, "user", resource_id=user.id,
            details=f"Changed role for {user.email}",
            metadata={"from_role": old_role_name, "to_role": user.role.name},
        )
    if active_changed:
        record_audit_event(
            db,
            current_user,
            AuditAction.USER_ACTIVATED if payload.is_active else AuditAction.USER_DEACTIVATED,
            "user",
            resource_id=user.id,
            details=f"{'Activated' if payload.is_active else 'Deactivated'} {user.email}",
        )
    if name_changed:
        record_audit_event(
            db, current_user, AuditAction.USER_UPDATED, "user", resource_id=user.id,
            details=f"Updated profile for {user.email}",
        )

    return _get_user_or_404(db, id)
