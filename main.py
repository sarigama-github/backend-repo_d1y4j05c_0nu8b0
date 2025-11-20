import os
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents

app = FastAPI(title="Health Payments Backoffice API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TransactionOut(BaseModel):
    id: Optional[str] = None
    amount: float
    currency: str
    status: str
    type: str
    partner: Optional[str] = None
    reference: Optional[str] = None
    occurred_at: Optional[datetime] = None


@app.get("/")
def read_root():
    return {"message": "Health Payments Backoffice API"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response


# --- Seed helpers -----------------------------------------------------------
PARTNERS = [
    "Pharmacie Centrale", "Clinique St. Michel", "PharmaPlus Lyon",
    "Hôpital Sainte-Anne", "Centre Dentaire Azur"
]


def seed_transactions_if_empty():
    try:
        if db is None:
            return
        count = db["transaction"].count_documents({})
        if count > 0:
            return
        now = datetime.utcnow()
        # generate 30 days of sample data
        for i in range(30):
            day = now - timedelta(days=29 - i)
            # 6-15 payins per day
            for j in range(6, 12):
                amt = round(20 + (j * 7.3) + (i % 5) * 3.7, 2)
                doc = {
                    "amount": amt,
                    "currency": "EUR",
                    "status": "completed" if (j % 9 != 0) else "failed",
                    "type": "payin",
                    "partner": PARTNERS[(i + j) % len(PARTNERS)],
                    "reference": f"INV-{day.strftime('%Y%m%d')}-{j}",
                    "occurred_at": day.replace(hour=j % 24, minute=(j * 7) % 60)
                }
                db["transaction"].insert_one({
                    **doc,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                })
            # 0-3 payouts per day
            for k in range(i % 3):
                amt = round(100 + i * 8.5 + k * 25.7, 2)
                db["transaction"].insert_one({
                    "amount": amt,
                    "currency": "EUR",
                    "status": "pending" if (k == 2) else "completed",
                    "type": "payout",
                    "partner": PARTNERS[(i + k) % len(PARTNERS)],
                    "reference": f"PO-{day.strftime('%Y%m%d')}-{k}",
                    "occurred_at": day.replace(hour=(k * 5) % 24, minute=(k * 11) % 60),
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                })
    except Exception:
        # Silently ignore seeding problems
        pass


seed_transactions_if_empty()


# --- API Endpoints ----------------------------------------------------------
@app.get("/api/transactions", response_model=List[TransactionOut])
def list_transactions(limit: int = 5):
    """Return latest transactions (default 5)."""
    try:
        if db is None:
            # Return mock data if db not available
            now = datetime.utcnow()
            items = []
            for i in range(limit):
                items.append(TransactionOut(
                    id=str(i),
                    amount=123.45 + i,
                    currency="EUR",
                    status=["completed", "pending", "failed"][i % 3],
                    type=["payin", "payout"][i % 2],
                    partner=PARTNERS[i % len(PARTNERS)],
                    reference=f"INV-{now.strftime('%Y%m%d')}-{i}",
                    occurred_at=now - timedelta(hours=i)
                ))
            return items
        docs = db["transaction"].find({}).sort("occurred_at", -1).limit(limit)
        result = []
        for d in docs:
            result.append(TransactionOut(
                id=str(d.get("_id")),
                amount=float(d.get("amount", 0)),
                currency=d.get("currency", "EUR"),
                status=d.get("status", "completed"),
                type=d.get("type", "payin"),
                partner=d.get("partner"),
                reference=d.get("reference"),
                occurred_at=d.get("occurred_at")
            ))
        return result
    except Exception:
        return []


@app.get("/api/metrics")
def metrics():
    """Return top-line metrics for the dashboard."""
    now = datetime.utcnow()
    start_day = datetime(now.year, now.month, now.day)

    def sum_amount(filter_query):
        total = 0.0
        for d in db["transaction"].find(filter_query):
            total += float(d.get("amount", 0))
        return round(total, 2)

    try:
        if db is None:
            return {
                "available_balance": 12845.23,
                "today": {"count": 42, "amount": 2456.7},
                "payouts_pending": {"count": 3, "amount": 1240.5},
                "success_rate": 0.94,
            }
        available_balance = sum_amount({"type": "payin", "status": "completed"}) - sum_amount({"type": "payout"})
        today_count = db["transaction"].count_documents({"occurred_at": {"$gte": start_day}})
        today_amount = sum_amount({"occurred_at": {"$gte": start_day}})
        pending_payouts_count = db["transaction"].count_documents({"type": "payout", "status": "pending"})
        pending_payouts_amount = sum_amount({"type": "payout", "status": "pending"})
        total_count = db["transaction"].count_documents({}) or 1
        success_count = db["transaction"].count_documents({"status": "completed"})
        success_rate = success_count / total_count
        return {
            "available_balance": round(float(available_balance), 2),
            "today": {"count": int(today_count), "amount": round(float(today_amount), 2)},
            "payouts_pending": {"count": int(pending_payouts_count), "amount": round(float(pending_payouts_amount), 2)},
            "success_rate": round(float(success_rate), 4),
        }
    except Exception:
        return {
            "available_balance": 10000.0,
            "today": {"count": 20, "amount": 1500.0},
            "payouts_pending": {"count": 2, "amount": 800.0},
            "success_rate": 0.92,
        }


@app.get("/api/transactions/weekly")
def transactions_weekly():
    """Return aggregated amounts for the last 7 days."""
    now = datetime.utcnow()
    start = now - timedelta(days=6)
    buckets = {}
    for i in range(7):
        day = (start + timedelta(days=i)).strftime('%Y-%m-%d')
        buckets[day] = 0.0

    try:
        if db is None:
            return [{"date": k, "amount": (i + 1) * 300.0} for i, k in enumerate(buckets.keys())]
        cursor = db["transaction"].find({"occurred_at": {"$gte": start}})
        for d in cursor:
            day = d.get("occurred_at", now).strftime('%Y-%m-%d')
            buckets[day] = buckets.get(day, 0.0) + float(d.get("amount", 0))
        return [{"date": k, "amount": round(v, 2)} for k, v in buckets.items()]
    except Exception:
        return [{"date": k, "amount": (i + 1) * 250.0} for i, k in enumerate(buckets.keys())]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
