import asyncio
import uuid
from sqlmodel import Session, create_engine
from app.config import settings
from app.routers.users import create_user
from app.schemas import UserCreate

async def run_signup_smoke():
    engine = create_engine(settings.database_url)
    user_in = UserCreate(
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password="Password123!",
        first_name="Test",
        last_name="User",
        role="TRADER"
    )
    
    with Session(engine) as session:
        try:
            print(f"Testing signup for {user_in.email} with role TRADER")
            user = await create_user(user_in=user_in, db=session)
            print(f"Successfully created user: {user.email} with role {user.role}")
        except Exception as e:
            print(f"Signup failed: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_signup_smoke())
