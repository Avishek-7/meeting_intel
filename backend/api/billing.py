"""
Billing API — Stripe checkout, portal, and webhook endpoints.
"""

import logging
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, HttpUrl

from core.database import get_db
from core.dependencies import get_current_user
from core.config import settings
from services.billing_service import (
    create_checkout_session,
    create_portal_session,
    handle_webhook,
    PLANS,
)
from services.user_service import get_user_by_id
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


class CheckoutRequest(BaseModel):
    price_id: str
    success_url: HttpUrl
    cancel_url: HttpUrl


class PortalRequest(BaseModel):
    return_url: HttpUrl


def _allowed_redirect_hosts() -> set[str]:
    configured = getattr(settings, "BILLING_ALLOWED_REDIRECT_HOSTS", None)
    if configured:
        return {h.strip().lower() for h in configured.split(",") if h.strip()}
    # Safe local defaults for development
    return {"localhost", "127.0.0.1"}


def _validate_redirect_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in _allowed_redirect_hosts():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Redirect URL host is not allowed",
        )
    return url


@router.get("/plans")
def list_plans():
    """Return available subscription plans."""
    return PLANS


@router.post("/checkout")
async def start_checkout(
    body: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session and return the redirect URL."""
    try:
        user_id = uuid.UUID(current_user["id"])
    except (KeyError, ValueError, TypeError):
        logger.warning("Invalid current_user id for checkout", extra={"current_user": current_user})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user identity")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    success_url = _validate_redirect_url(str(body.success_url))
    cancel_url = _validate_redirect_url(str(body.cancel_url))

    try:
        url = await create_checkout_session(
            db=db,
            user=user,
            price_id=body.price_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        logger.exception("Stripe checkout error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Billing error")

    return {"url": url}


@router.post("/portal")
async def customer_portal(
    body: PortalRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session URL."""
    try:
        user_id = uuid.UUID(current_user["id"])
    except (KeyError, ValueError, TypeError):
        logger.warning("Invalid current_user id for portal", extra={"current_user": current_user})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user identity")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return_url = _validate_redirect_url(str(body.return_url))

    try:
        url = await create_portal_session(db=db, user=user, return_url=return_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        logger.exception("Stripe portal error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Billing error")

    return {"url": url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    """
    Stripe sends events here. Must be registered in the Stripe dashboard as:
    https://your-domain.com/billing/webhook
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not hasattr(settings, "STRIPE_WEBHOOK_SECRET") or not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook not configured")

    try:
        await handle_webhook(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError as exc:
        # Invalid signature
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception:
        logger.exception("Webhook processing error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook error")

    return {"received": True}
