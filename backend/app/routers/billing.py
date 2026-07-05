"""Billing routes — credit purchases, subscriptions, and transaction history."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..auth_deps import get_current_user
from ..models.user import User
from ..models.credit_transaction import CreditTransaction

router = APIRouter(tags=["billing"])

# Available plans with their pricing and features
AVAILABLE_PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "credits": 100,
        "api_rate_limit": 60,
        "features": ["100 credits/month", "60 requests/hour"],
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "credits": 1000,
        "api_rate_limit": 300,
        "features": ["1000 credits/month", "300 requests/hour", "Priority queue"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 199,
        "credits": 10000,
        "api_rate_limit": 1000,
        "features": [
            "10000 credits/month",
            "1000 requests/hour",
            "Priority queue",
            "Dedicated support",
        ],
    },
}

# Credit pack prices (USD)
CREDIT_PACKS = {
    100: {"price": 5, "label": "100 credits"},
    500: {"price": 20, "label": "500 credits"},
    1000: {"price": 35, "label": "1000 credits"},
    5000: {"price": 150, "label": "5000 credits"},
}


class PurchaseCreditsRequest(BaseModel):
    amount: int


class SubscribeRequest(BaseModel):
    plan: str


@router.post("/credits")
async def purchase_credits(
    req: PurchaseCreditsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Purchase additional credits."""
    if req.amount not in CREDIT_PACKS:
        valid_options = ", ".join(str(k) for k in CREDIT_PACKS)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credit amount. Available packs: {valid_options}",
        )

    pack = CREDIT_PACKS[req.amount]

    # TODO: Integrate with real payment processor (Stripe, etc.)
    # For now, we just add the credits directly

    current_user.credits += req.amount

    transaction = CreditTransaction(
        user_id=current_user.id,
        amount=req.amount,
        balance_after=current_user.credits,
        description=f"Purchased {pack['label']} (${pack['price']})",
        reference_type="purchase",
    )
    db.add(transaction)

    return {
        "credits_purchased": req.amount,
        "price_usd": pack["price"],
        "credits_remaining": current_user.credits,
        "transaction_id": transaction.id,
    }


@router.get("/transactions")
async def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get transaction history for the current user."""
    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == current_user.id)
        .order_by(desc(CreditTransaction.created_at))
        .offset(skip)
        .limit(limit)
    )
    transactions = result.scalars().all()

    return {
        "total": len(transactions),
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "balance_after": t.balance_after,
                "description": t.description,
                "reference_type": t.reference_type,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transactions
        ],
    }




@router.get("/balance")
async def get_balance(
    user_id: int = Query(1, description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get current user billing balance (credits, plan, usage)."""
    from sqlalchemy import select as sel
    from ..models.user import User
    result = await db.execute(sel(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"plan": "free", "credits": 100, "credits_used": 0}
    return {
        "plan": user.plan or "free",
        "credits": user.credits or 100,
        "credits_used": user.credits_used or 0,
        "api_rate_limit": user.api_rate_limit or 60,
        "subscription_end": user.subscription_end.isoformat() if user.subscription_end else None,
    }

@router.post("/subscribe")
async def subscribe_to_plan(
    req: SubscribeRequest,
    user_id: int = Query(1, description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Subscribe to a plan (no auth required for demo)."""
    plan_name = req.plan.lower()
    if plan_name not in AVAILABLE_PLANS:
        valid = ", ".join(AVAILABLE_PLANS)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{plan_name}'. Available: {valid}",
        )

    plan_info = AVAILABLE_PLANS[plan_name]

    # Look up user
    from sqlalchemy import select as sel
    from ..models.user import User
    result = await db.execute(sel(User).where(User.id == user_id))
    current_user = result.scalar_one_or_none()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_user.plan = plan_name
    current_user.credits = plan_info["credits"]
    current_user.api_rate_limit = plan_info["api_rate_limit"]
    current_user.subscription_end = datetime.utcnow() + timedelta(days=30)

    return {
        "plan": plan_name,
        "credits": plan_info["credits"],
        "api_rate_limit": plan_info["api_rate_limit"],
        "features": plan_info["features"],
        "subscription_end": current_user.subscription_end.isoformat(),
    }


@router.get("/plans")
async def get_plans():
    """Get available plans and pricing."""
    return {"plans": AVAILABLE_PLANS, "credit_packs": CREDIT_PACKS}
