"""Minimal demo data: the 7 OG-PIOS roles plus one admin user to log in with.

Run after migrations are applied: `docker compose exec backend python -m app.db.seed`.
Full synthetic production/equipment data generation is planned separately —
see scripts/seed/README.md.
"""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User

ROLE_NAMES = [
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
    "Viewer",
]

DEMO_ADMIN_EMAIL = "admin@ogpios.dev"
DEMO_ADMIN_PASSWORD = "ChangeMe123!"


def seed() -> None:
    db = SessionLocal()
    try:
        roles = {}
        for name in ROLE_NAMES:
            role = db.query(Role).filter(Role.name == name).first()
            if role is None:
                role = Role(name=name)
                db.add(role)
                db.flush()
            roles[name] = role

        admin = db.query(User).filter(User.email == DEMO_ADMIN_EMAIL).first()
        if admin is None:
            admin = User(
                email=DEMO_ADMIN_EMAIL,
                full_name="Demo Administrator",
                hashed_password=hash_password(DEMO_ADMIN_PASSWORD),
                role_id=roles["Administrator"].id,
            )
            db.add(admin)

        db.commit()
        print(f"Seeded {len(ROLE_NAMES)} roles.")
        print(f"Demo admin: {DEMO_ADMIN_EMAIL} / {DEMO_ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
