from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from schemas.meeting import (
    MeetingRequest,
    MeetingResponse,
    MeetingJobEnqueueResponse,
    MeetingJobStatusResponse,
    MeetingJobResult,
    MeetingMetadata,
    MeetingDetail,
    PaginatedMeetings,
    UserStats,
    GlobalStats,
    DailyStats,
)
from services.meeting_service import (
    process_meeting_transcript,
    enqueue_meeting_analysis_job,
    get_user_meetings,
    get_meeting_detail,
)
from services.analytics_service import (
    get_user_stats,
    get_user_daily_stats,
    get_global_stats,
    get_global_daily_stats,
    parse_date_range,
)
from services.usage_service import enforce_daily_usage_limits
from services.user_service import get_or_create_user_by_email
from core.exceptions import ValidationError, AIServiceError, DatabaseError, NotFoundError
from core.dependencies import get_current_user
from core.security import verify_access_token
from core.authorization import get_admin_user
from core.rbac import log_admin_action
from core.database import get_db
from core.transcript import estimate_token_count
from core.config import settings
from core.queue import redis_client as queue_redis_client, default_queue
from core.storage import save_audio_upload
from models.meeting import Meeting
from jobs.transcription import run_transcription_job_sync
from services.ai.transcription import transcribe_audio_bytes, WHISPER_MODEL
from rq.job import Job
from rq.exceptions import NoSuchJobError
from redis.exceptions import RedisError
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
import os
import uuid
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.websocket("/transcribe/live")
async def live_transcribe(websocket: WebSocket):
    """
    Live transcription over WebSocket using OpenAI Whisper.

    Protocol:
    - Client sends binary audio chunks (e.g., webm/ogg/mp4 chunks).
    - Optional client text message: {"event": "finalize"}
    - Server sends events:
      - {"event":"ready", ...}
      - {"event":"partial", "text":..., "chunk_index":..., "full_text":...}
      - {"event":"final", "text":...}
      - {"event":"error", "detail":...}
    """
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    payload = verify_access_token(token) if token else None

    if payload is None or not payload.get("sub"):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    await websocket.send_json({
        "event": "ready",
        "model": WHISPER_MODEL,
        "max_chunk_bytes": settings.LIVE_TRANSCRIBE_MAX_CHUNK_BYTES,
    })

    transcript_parts: list[str] = []
    chunk_index = 0

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type")

            if msg_type == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                audio_chunk: bytes = message["bytes"]
                if not audio_chunk:
                    continue

                if len(audio_chunk) > settings.LIVE_TRANSCRIBE_MAX_CHUNK_BYTES:
                    await websocket.send_json({
                        "event": "error",
                        "detail": "Audio chunk too large.",
                        "max_chunk_bytes": settings.LIVE_TRANSCRIBE_MAX_CHUNK_BYTES,
                    })
                    continue

                chunk_index += 1
                try:
                    text = await transcribe_audio_bytes(audio_chunk, filename=f"live_chunk_{chunk_index}.webm")
                except Exception:
                    logger.exception("Live transcription failed for chunk", extra={"chunk_index": chunk_index})
                    await websocket.send_json({
                        "event": "error",
                        "detail": "Transcription failed for a chunk.",
                        "chunk_index": chunk_index,
                    })
                    continue

                clean_text = (text or "").strip()
                if clean_text:
                    transcript_parts.append(clean_text)

                await websocket.send_json({
                    "event": "partial",
                    "chunk_index": chunk_index,
                    "text": clean_text,
                    "full_text": " ".join(transcript_parts),
                })
                continue

            text_payload = message.get("text")
            if text_payload is None:
                continue

            event = ""
            try:
                parsed = json.loads(text_payload)
                event = str(parsed.get("event", "")).lower()
            except json.JSONDecodeError:
                event = text_payload.strip().lower()

            if event in {"finalize", "stop", "done"}:
                await websocket.send_json({
                    "event": "final",
                    "text": " ".join(transcript_parts),
                    "chunks": chunk_index,
                })
                break

            if event == "ping":
                await websocket.send_json({"event": "pong"})
                continue

            await websocket.send_json({
                "event": "error",
                "detail": "Unsupported event. Use binary audio chunks or event=finalize.",
            })

    except WebSocketDisconnect:
        logger.info("Live transcription websocket disconnected")
    except Exception:
        logger.exception("Unexpected error in live transcription websocket")
        try:
            await websocket.send_json({"event": "error", "detail": "Live transcription session failed."})
        except Exception:
            pass
        await websocket.close(code=1011)

@router.post(
    "/analyze",
    response_model=MeetingResponse,
    status_code=status.HTTP_200_OK
)
async def process_meeting(
    request: MeetingRequest, 
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate user identity before processing
    # This must be outside the try block to avoid being masked by the generic exception handler
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available"
        )
    
    try:
        # Use email as username@domain or just username if no email available
        # In future, JWT token should contain email or user UUID
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        estimated_tokens = estimate_token_count(request.transcript)
        if estimated_tokens > settings.MAX_TRANSCRIPT_TOKENS:
            raise ValidationError("Transcript exceeds the maximum token limit.")
        await enforce_daily_usage_limits(db, user.id, estimated_tokens=estimated_tokens)
        
        return await process_meeting_transcript(request.transcript, db, str(user.id))
    
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    
    except AIServiceError:
        logger.exception("AI service error during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meeting processing service is currently unavailable."
        )
    
    except DatabaseError:
        logger.exception("Database error during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save meeting data."
        )
    
    except Exception as e:
        # Catch-all safety net - re-raise HTTPException to avoid masking auth errors
        if isinstance(e, HTTPException):
            raise
        logger.exception("Unexpected error during meeting processing.") 
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post(
    "/analyze-async",
    response_model=MeetingJobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_meeting_analysis(
    request: MeetingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)

        estimated_tokens = estimate_token_count(request.transcript)
        if estimated_tokens > settings.MAX_TRANSCRIPT_TOKENS:
            raise ValidationError("Transcript exceeds the maximum token limit.")
        await enforce_daily_usage_limits(db, user.id, estimated_tokens=estimated_tokens)
        job_id = enqueue_meeting_analysis_job(request.transcript, str(user.id))
        return MeetingJobEnqueueResponse(job_id=job_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except (AIServiceError, RedisError) as e:
        logger.exception("Queue unavailable during meeting processing.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meeting analysis queue is currently unavailable.",
        )
    except DatabaseError:
        logger.exception("Database error while enqueueing meeting analysis.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare meeting analysis request.",
        )
    except Exception:
        logger.exception("Unexpected error while enqueueing meeting analysis.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.get(
    "/jobs/{job_id}",
    response_model=MeetingJobStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_meeting_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    if queue_redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background queue is not available.",
        )

    try:
        job = Job.fetch(job_id, connection=queue_redis_client)
    except NoSuchJobError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )
    except RedisError:
        logger.exception("Redis error fetching job status.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background queue is temporarily unavailable.",
        )

    email = current_user.get("email") or f"{username}@meetingintel.local"
    user = await get_or_create_user_by_email(db, email)
    job_user_id = job.meta.get("user_id") if job.meta else None
    if not job_user_id or job_user_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    status_name = job.get_status()
    result_payload = None
    if job.is_finished and isinstance(job.result, dict):
        result_payload = MeetingJobResult(**job.result)

    error_message = None
    if job.is_failed:
        error_message = "Job failed."

    return MeetingJobStatusResponse(
        job_id=job.id,
        status=status_name,
        result=result_payload,
        error=error_message,
    )


# Meeting History & Analytics Endpoints

@router.get(
    "/history",
    response_model=PaginatedMeetings,
    status_code=status.HTTP_200_OK,
)
async def get_meeting_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get user's meeting history with metadata (paginated)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        meetings_data, total_count = await get_user_meetings(
            db=db,
            user_id=str(user.id),
            limit=limit,
            offset=offset
        )
        
        items = [MeetingMetadata(**m) for m in meetings_data]
        has_more = (offset + limit) < total_count
        
        return PaginatedMeetings(
            items=items,
            total=total_count,
            limit=limit,
            offset=offset,
            has_more=has_more
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except DatabaseError:
        logger.exception("Database error listing meetings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meetings.",
        )
    except Exception:
        logger.exception("Unexpected error listing meetings.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get(
    "/analytics/user",
    response_model=UserStats,
    status_code=status.HTTP_200_OK,
)
async def get_user_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("today", pattern="^(today|7d|30d|all)$"),
):
    """Get user's aggregated stats."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        stats = await get_user_stats(
            db=db,
            user_id=str(user.id),
            date_from=date_from,
            date_to=date_to
        )
        
        return UserStats(**stats)
    except Exception:
        logger.exception("Error retrieving user analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics.",
        )


@router.get(
    "/analytics/user/daily",
    response_model=list[DailyStats],
    status_code=status.HTTP_200_OK,
)
async def get_user_daily_analytics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get user's daily breakdown."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        daily_stats = await get_user_daily_stats(
            db=db,
            user_id=str(user.id),
            date_from=date_from,
            date_to=date_to
        )
        
        return [DailyStats(**stat) for stat in daily_stats]
    except Exception:
        logger.exception("Error retrieving user daily analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daily analytics.",
        )


@router.get(
    "/analytics/global",
    response_model=GlobalStats,
    status_code=status.HTTP_200_OK,
)
async def get_global_analytics(
    current_user: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get global stats (admin only)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        stats = await get_global_stats(
            db=db,
            date_from=date_from,
            date_to=date_to
        )
        
        return GlobalStats(**stats)
    except Exception:
        logger.exception("Error retrieving global analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global analytics.",
        )


@router.get(
    "/analytics/global/daily",
    response_model=list[DailyStats],
    status_code=status.HTTP_200_OK,
)
async def get_global_daily_analytics(
    current_user: dict = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
    from_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    preset: str = Query("7d", pattern="^(today|7d|30d|all)$"),
):
    """Get global daily breakdown (admin only)."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        date_from, date_to = parse_date_range(from_date, to_date, preset)
        
        daily_stats = await get_global_daily_stats(
            db=db,
            date_from=date_from,
            date_to=date_to
        )
        
        return [DailyStats(**stat) for stat in daily_stats]
    except Exception:
        logger.exception("Error retrieving global daily analytics.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve global daily analytics.",
        )


# Catch-all route for getting meeting details
# IMPORTANT: This must be defined LAST after all specific routes like /analytics/*
# because FastAPI matches routes in registration order
@router.get(
    "/{meeting_id}",
    response_model=MeetingDetail,
    status_code=status.HTTP_200_OK,
)
async def get_meeting(
    meeting_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a meeting."""
    username = current_user.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User identification not available",
        )

    try:
        email = current_user.get("email") or f"{username}@meetingintel.local"
        user = await get_or_create_user_by_email(db, email)
        
        meeting_data = await get_meeting_detail(
            db=db,
            user_id=str(user.id),
            meeting_id=meeting_id
        )
        
        return MeetingDetail(**meeting_data)
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except DatabaseError:
        logger.exception("Database error retrieving meeting.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meeting.",
        )
    except Exception:
        logger.exception("Unexpected error retrieving meeting.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ── Audio upload ───────────────────────────────────────────────────────────────

@router.post(
    "/upload-audio",
    response_model=MeetingJobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_audio(
    audio: UploadFile = File(..., description="Audio/video file to transcribe (max 200 MB)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an audio file. The file is stored, and a background job is enqueued
    to transcribe it (via OpenAI Whisper) and then run meeting analysis.

    Returns a job_id that can be polled via GET /meetings/jobs/{job_id}.
    """
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Validate queue availability before persisting any record
    if default_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job queue unavailable — Redis is not configured.",
        )

    # Persist the file
    try:
        audio_path = await save_audio_upload(audio, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Create a stub Meeting record
    meeting = Meeting(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        audio_file_path=audio_path,
        transcription_status="pending",
    )
    try:
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)
    except (DatabaseError, SQLAlchemyError):
        await db.rollback()
        try:
            local_root = Path(os.environ.get("STORAGE_LOCAL_DIR", "/tmp/meetingintel/audio")).resolve()
            audio_file = Path(audio_path).resolve()
            if audio_file.is_file() and local_root in audio_file.parents:
                audio_file.unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to cleanup uploaded audio after DB failure")
        logger.exception("Failed to persist meeting record for uploaded audio")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist uploaded audio",
        )

    job = default_queue.enqueue(
        run_transcription_job_sync,
        str(meeting.id),
        user_id,
        job_timeout=600,  # 10 min max for large files
    )

    return MeetingJobEnqueueResponse(job_id=job.id, status="queued")
