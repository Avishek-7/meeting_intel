"""
Billing service — Stripe checkout, customer management, webhook handling.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.user import User
from core.exceptions import DatabaseError

logger = logging.getLogger(__name__)

try:
    import stripe  # type: ignore
    _stripe_available = True
except ImportError:
    _stripe_available = False
    logger.warning("stripe package not installed. Billing endpoints will return 503.")


def _get_stripe():
    if not _stripe_available:
        raise RuntimeError("stripe is not installed. Run: pip install stripe")
    from core.config import settings
    stripe.api_key = settings.STRIPE_SECRET_KEY  # type: ignore[attr-defined]
    return stripe


# Plan configuration
PLANS = {
    "free": {"display": "Free", "meetings_per_month": 10, "audio_uploads": False},
    "pro": {"display": "Pro", "meetings_per_month": 200, "audio_uploads": True},
    "enterprise": {"display": "Enterprise", "meetings_per_month": -1, "audio_uploads": True},
}


async def get_or_create_stripe_customer(db: AsyncSession, user: User) -> str:
    """Return existing Stripe customer ID or create one."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    s = _get_stripe()
    customer = s.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    customer_id: str = customer["id"]

    user.stripe_customer_id = customer_id
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("Failed to persist stripe_customer_id", exc_info=True)
        raise DatabaseError("Failed to save Stripe customer") from exc

    return customer_id


async def create_checkout_session(
    db: AsyncSession,
    user: User,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return its URL."""
    s = _get_stripe()
    customer_id = await get_or_create_stripe_customer(db, user)

    session = s.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user.id)},
    )
    return session["url"]


async def create_portal_session(db: AsyncSession, user: User, return_url: str) -> str:
    """Create a Stripe Customer Portal session URL."""
    s = _get_stripe()
    customer_id = await get_or_create_stripe_customer(db, user)
    session = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session["url"]


async def handle_webhook(payload: bytes, sig_header: str, webhook_secret: str) -> None:
    """Process an incoming Stripe webhook event."""
    s = _get_stripe()
    try:
        event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    except s.error.SignatureVerificationError:  # type: ignore[attr-defined]
        raise ValueError("Invalid Stripe webhook signature")

    event_type: str = event["type"]
    logger.info("stripe_webhook_received", extra={"event_type": event_type})

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        sub = event["data"]["object"]
        await _sync_subscription(sub)
    elif event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        await _handle_subscription_cancelled(sub)


async def _sync_subscription(subscription: dict) -> None:
    """Map Stripe subscription status to a local plan name."""
    from core.database import get_async_session
    from datetime import datetime

    customer_id: str = subscription["customer"]
    status: str = subscription["status"]
    current_period_end: int = subscription.get("current_period_end", 0)

    # Determine plan from first line item price
    plan = "free"
    items = subscription.get("items", {}).get("data", [])
    if items:
        price_id = items[0]["price"]["id"]
        from core.config import settings
        if hasattr(settings, "STRIPE_PRO_PRICE_ID") and price_id == settings.STRIPE_PRO_PRICE_ID:
            plan = "pro"
        elif hasattr(settings, "STRIPE_ENTERPRISE_PRICE_ID") and price_id == settings.STRIPE_ENTERPRISE_PRICE_ID:
            plan = "enterprise"

    if status not in ("active", "trialing"):
        plan = "free"

    async with get_async_session() as db:
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.plan = plan
            user.plan_expires_at = datetime.utcfromtimestamp(current_period_end) if current_period_end else None
            await db.commit()
            logger.info("Plan synced from Stripe", extra={"plan": plan})


async def _handle_subscription_cancelled(subscription: dict) -> None:
    customer_id: str = subscription["customer"]
    from core.database import get_async_session
    async with get_async_session() as db:
        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.plan = "free"
            user.plan_expires_at = None
            await db.commit()
