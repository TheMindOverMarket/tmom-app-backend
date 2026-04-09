from app.routers.sessions import list_sessions
from app.database import get_session
import uuid

def debug_sessions():
    for db in get_session():
        try:
            # We want to see if the Pydantic validation fails
            # list_sessions returns a list of dictionaries/models
            # but FastAPI handles the response_model validation.
            # Let's simulate that validation.
            from app.schemas import SessionRead
            from pydantic import TypeAdapter
            
            sessions = list_sessions(db=db)
            print(f"Raw query fetched {len(sessions)} sessions.")
            
            adapter = TypeAdapter(list[SessionRead])
            validated = adapter.validate_python(sessions)
            print(f"Validation successful for {len(validated)} sessions.")
            
        except Exception as e:
            print(f" [DEBUG ERROR] {e}")
            import traceback
            traceback.print_exc()
        break

if __name__ == "__main__":
    debug_sessions()
