import asyncio
import logging
import uuid
from sqlmodel import Session, select
from app.database import engine
from app.models import Playbook, GenerationStatus, Rule, Condition

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

async def analyze_playbook_execution(playbook_id: uuid.UUID):
    """
    TRIGGERS EXTERNAL RULE ENGINE ANALYSIS:
    1. Fetches the playbook and user identity.
    2. Calls the Rule Engine's /api/rules/trigger endpoint.
    3. Updates local GenerationStatus to COMPLETED (if trigger succeeds) or FAILED.
    """
    logger.info(f"[INTELLIGENCE][TRIGGER_START] Triggering analysis for playbook ID: {playbook_id}")
    
    # 1. Fetch record for User Identity
    with Session(engine) as db:
        playbook = db.get(Playbook, playbook_id)
        if not playbook:
            logger.error(f"[INTELLIGENCE][FAILED] Playbook {playbook_id} not found.")
            return
        user_id = playbook.user_id

    # 2. Call External Rule Engine (Updated Spec: POST /api/rules/compile)
    trigger_url = f"{settings.rule_engine_base_url}/api/rules/compile"
    params = {
        "playbook_id": str(playbook_id)
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"[INTELLIGENCE][REQUEST] POST {trigger_url} (playbook:{playbook_id})")
            # Note: External API requires playbook_id as a query parameter, not in the body.
            response = await client.post(trigger_url, params=params)
            
            if response.status_code >= 400:
                error_body = response.text
                logger.error(f"[INTELLIGENCE][REMOTE_ERROR] Rule Engine returned {response.status_code}: {error_body}")
                raise Exception(f"Remote Rule Engine Error: {response.status_code}")
            
            logger.info(f"[INTELLIGENCE][SUCCESS] Rule Engine triggered. Response: {response.json()}")
            
            # NOTE: We no longer mark status as COMPLETED here. 
            # The Rule Engine service now handles patching the status itself 
            # once compilation is physically finished.
            
    except Exception as e:
        logger.error(f"[INTELLIGENCE][EXCEPTION] Analysis trigger failed: {str(e)}")
        with Session(engine) as db:
            playbook = db.get(Playbook, playbook_id)
            if playbook:
                playbook.generation_status = GenerationStatus.FAILED
                db.add(playbook)
                db.commit()

async def trigger_session_execution(playbook_id: uuid.UUID, session_id: uuid.UUID, user_id: uuid.UUID):
    """
    Called by /sessions/start to trigger rule evaluation in the 
    remote Rule Engine service.
    """
    trigger_url = f"{settings.rule_engine_base_url}/api/rules/execute"
    params = {
        "playbook_id": str(playbook_id),
        "session_id": str(session_id),
        "user_id": str(user_id)
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"[RULE_ENGINE][EXECUTE] POST {trigger_url} (playbook:{playbook_id}, session:{session_id})")
            response = await client.post(trigger_url, params=params)
            response.raise_for_status()
            logger.info(f"[RULE_ENGINE][EXECUTE][SUCCESS] response: {response.json()}")
    except Exception as e:
        logger.error(f"[RULE_ENGINE][EXECUTE][ERROR] Trigger failed for playbook {playbook_id}: {str(e)}")

async def trigger_session_stop(playbook_id: uuid.UUID):
    """
    Called by /sessions/end to shut down rule engine processing
    for a specific strategy.
    """
    stop_url = f"{settings.rule_engine_base_url}/api/rules/stop"
    params = {"playbook_id": str(playbook_id)}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"[RULE_ENGINE][STOP] GET {stop_url} (playbook:{playbook_id})")
            response = await client.get(stop_url, params=params)
            response.raise_for_status()
            logger.info(f"[RULE_ENGINE][STOP][SUCCESS] response: {response.json()}")
    except Exception as e:
        logger.error(f"[RULE_ENGINE][STOP][ERROR] Shutdown failed for playbook {playbook_id}: {str(e)}")
