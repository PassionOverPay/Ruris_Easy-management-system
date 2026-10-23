from datetime import date

from sqlmodel import Session, select

from app.models import ExchangeRate
from app.services.currency import get_eur_to_ron_rate


async def fetch_and_store_eur_ron_rate(
    session: Session,
    rate_date: date,
) -> ExchangeRate:
    """Fetch the published EUR/RON rate for a date and persist it idempotently."""
    rate = await get_eur_to_ron_rate(rate_date)
    stored_rate = session.exec(
        select(ExchangeRate).where(ExchangeRate.date == rate_date)
    ).first()

    if stored_rate is None:
        stored_rate = ExchangeRate(
            date=rate_date,
            currency_pair="EUR_RON",
            rate=float(rate),
        )
        session.add(stored_rate)
    else:
        stored_rate.currency_pair = "EUR_RON"
        stored_rate.rate = float(rate)

    session.commit()
    session.refresh(stored_rate)
    return stored_rate
