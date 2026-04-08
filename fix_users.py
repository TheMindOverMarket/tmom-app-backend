from sqlmodel import Session, select, create_engine
from app.models import User, UserRole
from app.config import settings

engine = create_engine(settings.database_url)

def fix_existing_users():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        for user in users:
            print(f"Checking user {user.email} with role {user.role}")
            # If role is standard or admin (case insensitive or whatever it was), update it
            role_str = str(user.role).upper()
            if role_str == "STANDARD":
                user.role = UserRole.TRADER
                session.add(user)
            elif role_str == "ADMIN":
                user.role = UserRole.MANAGER
                session.add(user)
            elif role_str == "MANAGER":
                 pass # already correct
            elif role_str == "TRADER":
                 pass # already correct
            else:
                 # Default to TRADER if unknown
                 user.role = UserRole.TRADER
                 session.add(user)
        session.commit()
        print("Done fixing users.")

if __name__ == "__main__":
    fix_existing_users()
