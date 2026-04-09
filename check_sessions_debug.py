import asyncio
from sqlalchemy import text
from app.database import get_session

async def check_sessions():
    async for db in get_session():
        try:
            # Check column names
            result = db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'sessions'"))
            columns = result.fetchall()
            print("Columns in 'sessions' table:")
            for col in columns:
                print(f" - {col[0]}: {col[1]}")
            
            # Check if any rows exist and if they match schema
            result = db.execute(text("SELECT * FROM sessions LIMIT 5"))
            rows = result.fetchall()
            print(f"\nFound {len(rows)} rows in 'sessions'.")
            
        except Exception as e:
            print(f"Error checking sessions: {e}")
        break

if __name__ == "__main__":
    asyncio.run(check_sessions())
