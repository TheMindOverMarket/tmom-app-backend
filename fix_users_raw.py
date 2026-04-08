from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.database_url)

def fix_existing_users_raw():
    with engine.connect() as conn:
        print("Updating users with 'STANDARD' role to 'TRADER'...")
        res1 = conn.execute(text("UPDATE users SET role = 'TRADER' WHERE role::text IN ('STANDARD', 'standard')"))
        print(f"Updated {res1.rowcount} traders.")
        
        print("Updating users with 'ADMIN' role to 'MANAGER'...")
        res2 = conn.execute(text("UPDATE users SET role = 'MANAGER' WHERE role::text IN ('ADMIN', 'admin')"))
        print(f"Updated {res2.rowcount} managers.")
        
        conn.commit()
        print("Done fixing users raw.")

if __name__ == "__main__":
    fix_existing_users_raw()
