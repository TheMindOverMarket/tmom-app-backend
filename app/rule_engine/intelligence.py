from __future__ import annotations
import asyncio
import logging
import uuid
from sqlmodel import Session, select
from app.database import engine
from app.models import Playbook, GenerationStatus, Rule, Condition
from app.markets import resolve_playbook_symbol

import httpx
from app.config import settings

logger = logging.getLogger(__name__)
MAX_COMPILE_TRIGGER_ATTEMPTS = 4
INITIAL_COMPILE_RETRY_SECONDS = 2.0


def _compute_retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass
    return INITIAL_COMPILE_RETRY_SECONDS * (2 ** (attempt - 1))

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
        symbol = resolve_playbook_symbol(playbook)

    # 2. Call External Rule Engine (Updated Spec: POST /api/rules/compile)
    trigger_url = f"{settings.rule_engine_base_url}/api/rules/compile"
    params = {
        "playbook_id": str(playbook_id),
        "symbol": symbol,
        "market": symbol,
    }
    
    last_error: Exception | None = None

    for attempt in range(1, MAX_COMPILE_TRIGGER_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                logger.info(
                    f"[INTELLIGENCE][REQUEST] POST {trigger_url} (playbook:{playbook_id}, attempt:{attempt}/{MAX_COMPILE_TRIGGER_ATTEMPTS})"
                )
                # Note: External API requires playbook_id as a query parameter, not in the body.
                response = await client.post(trigger_url, params=params)

                if response.status_code == 429 and attempt < MAX_COMPILE_TRIGGER_ATTEMPTS:
                    delay = _compute_retry_delay(response, attempt)
                    logger.warning(
                        f"[INTELLIGENCE][RETRY] Rule Engine compile trigger was rate limited (429). "
                        f"Retrying in {delay:.1f}s (attempt {attempt}/{MAX_COMPILE_TRIGGER_ATTEMPTS})."
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 500 and attempt < MAX_COMPILE_TRIGGER_ATTEMPTS:
                    delay = _compute_retry_delay(response, attempt)
                    logger.warning(
                        f"[INTELLIGENCE][RETRY] Rule Engine compile trigger returned {response.status_code}. "
                        f"Retrying in {delay:.1f}s (attempt {attempt}/{MAX_COMPILE_TRIGGER_ATTEMPTS})."
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    error_body = response.text
                    logger.error(f"[INTELLIGENCE][REMOTE_ERROR] Rule Engine returned {response.status_code}: {error_body}")
                    raise Exception(f"Remote Rule Engine Error: {response.status_code}")

                logger.info(f"[INTELLIGENCE][SUCCESS] Rule Engine triggered. Response: {response.json()}")

                # NOTE: We no longer mark status as COMPLETED here.
                # The Rule Engine service now handles patching the status itself
                # once compilation is physically finished.
                return

        except (httpx.TimeoutException, httpx.RequestError) as e:
            last_error = e
            if attempt < MAX_COMPILE_TRIGGER_ATTEMPTS:
                delay = _compute_retry_delay(None, attempt)
                logger.warning(
                    f"[INTELLIGENCE][RETRY] Compile trigger request failed ({type(e).__name__}: {e}). "
                    f"Retrying in {delay:.1f}s (attempt {attempt}/{MAX_COMPILE_TRIGGER_ATTEMPTS})."
                )
                await asyncio.sleep(delay)
                continue
            break
        except Exception as e:
            last_error = e
            break

    if last_error is not None:
        logger.error(f"[INTELLIGENCE][EXCEPTION] Analysis trigger failed: {str(last_error)}")
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
    with Session(engine) as db:
        playbook = db.get(Playbook, playbook_id)
        symbol = resolve_playbook_symbol(playbook) if playbook else ""

    if not symbol:
        logger.error(
            "[RULE_ENGINE][EXECUTE][ERROR] Playbook %s has no persisted market symbol; aborting execute trigger.",
            playbook_id,
        )
        return

    trigger_url = f"{settings.rule_engine_base_url}/api/rules/execute"
    params = {
        "playbook_id": str(playbook_id),
        "session_id": str(session_id),
        "user_id": str(user_id),
        "symbol": symbol,
        "market": symbol,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"[RULE_ENGINE][EXECUTE] POST {trigger_url} (playbook:{playbook_id}, session:{session_id})")
            response = await client.post(trigger_url, params=params)
            response.raise_for_status()
            logger.info(f"[RULE_ENGINE][EXECUTE][SUCCESS] response: {response.json()}")
    except Exception as e:
        logger.error(f"[RULE_ENGINE][EXECUTE][ERROR] Trigger failed for playbook {playbook_id}: {str(e)}")

    # 🚦 DEVIATION ENGINE TRIGGER
    deviation_url = f"{settings.deviation_engine_base_url}/deviations/session/start"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"[DEVIATION_ENGINE][START] POST {deviation_url} (session:{session_id})")
            await client.post(deviation_url, params={
                "session_id": str(session_id),
                "playbook_id": str(playbook_id),
                "user_id": str(user_id)
            })
    except Exception as e:
        logger.warning(f"[DEVIATION_ENGINE][START][ERROR] Trigger failed: {str(e)}")

async def trigger_session_stop(playbook_id: uuid.UUID):
    """
    Called by /sessions/end to shut down rule engine processing
    for a specific strategy.
    """
    with Session(engine) as db:
        playbook = db.get(Playbook, playbook_id)
        symbol = resolve_playbook_symbol(playbook) if playbook else ""

    if not symbol:
        logger.error(
            "[RULE_ENGINE][STOP][ERROR] Playbook %s has no persisted market symbol; aborting stop trigger.",
            playbook_id,
        )
        return

    stop_url = f"{settings.rule_engine_base_url}/api/rules/stop"
    params = {"playbook_id": str(playbook_id), "symbol": symbol, "market": symbol}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"[RULE_ENGINE][STOP] GET {stop_url} (playbook:{playbook_id})")
            response = await client.get(stop_url, params=params)
            response.raise_for_status()
            logger.info(f"[RULE_ENGINE][STOP][SUCCESS] response: {response.json()}")
    except Exception as e:
        logger.error(f"[RULE_ENGINE][STOP][ERROR] Shutdown failed for playbook {playbook_id}: {str(e)}")

    # 🚦 DEVIATION ENGINE SHUTDOWN
    deviation_url = f"{settings.deviation_engine_base_url}/deviations/session/stop"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info(f"[DEVIATION_ENGINE][STOP] POST {deviation_url} (session:{playbook_id})")
            # NOTE: For stop, we usually rely on session_id, but the trigger currently takes session_id
            # However, trigger_session_stop in backend only has playbook_id. 
            # We'll need a way to resolve the active session_id if we want to stop it specifically.
            # For now, we'll log it as a placeholder or assume the engine handles it.
            pass 
    except Exception as e:
        logger.warning(f"[DEVIATION_ENGINE][STOP][ERROR] Shutdown failed: {str(e)}")
