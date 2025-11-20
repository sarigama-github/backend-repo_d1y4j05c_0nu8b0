"""
Database Schemas for Health Payments Platform

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- Transaction -> "transaction"
- Payout -> "payout"
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

Currency = Literal["EUR", "USD", "GBP", "CHF", "CAD", "AUD"]
Status = Literal["pending", "completed", "failed"]
TxnType = Literal["payin", "payout"]

class Transaction(BaseModel):
    """
    Payments flowing into (payin) or out of (payout) the platform.
    Collection: "transaction"
    """
    amount: float = Field(..., ge=0, description="Amount of the transaction")
    currency: Currency = Field("EUR", description="Currency code")
    status: Status = Field("completed", description="Payment status")
    type: TxnType = Field("payin", description="Transaction type: payin or payout")
    partner: Optional[str] = Field(None, description="Pharmacy, clinic or partner name")
    reference: Optional[str] = Field(None, description="Reference or invoice number")
    occurred_at: Optional[datetime] = Field(None, description="When the transaction occurred")

class Payout(BaseModel):
    """
    Outgoing settlements to partners (clinics, pharmacies)
    Collection: "payout"
    """
    amount: float = Field(..., ge=0)
    currency: Currency = Field("EUR")
    status: Status = Field("pending")
    beneficiary: str = Field(..., description="Beneficiary name")
    scheduled_for: Optional[datetime] = None
