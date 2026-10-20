import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO

import httpx

ECB_RATES_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.RON.EUR.SP00.A"
FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v1"


class ExchangeRateUnavailable(Exception):
    """Raised when no trusted source provides a rate for or before the date."""


def _ecb_eur_rate(csv_content: str, requested_date: date) -> Decimal:
    latest_observation: tuple[date, Decimal] | None = None
    for row in csv.DictReader(StringIO(csv_content)):
        observation_date = date.fromisoformat(row["TIME_PERIOD"])
        if observation_date > requested_date:
            continue
        if row.get("CURRENCY") != "RON" or row.get("CURRENCY_DENOM") != "EUR":
            raise ValueError("ECB returned an unexpected currency pair")

        rate = Decimal(row["OBS_VALUE"])
        if not rate.is_finite() or rate <= 0:
            raise ValueError("ECB returned a non-positive EUR/RON rate")
        if latest_observation is None or observation_date > latest_observation[0]:
            latest_observation = (observation_date, rate)

    if latest_observation is None:
        raise ValueError(f"ECB has no EUR/RON rate on or before {requested_date}")
    return latest_observation[1]


async def _frankfurter_eur_rate(
    client: httpx.AsyncClient,
    requested_date: date,
) -> Decimal:
    response = await client.get(
        f"{FRANKFURTER_RATES_URL}/{requested_date.isoformat()}",
        params={"base": "EUR", "symbols": "RON"},
    )
    response.raise_for_status()
    data = response.json()

    try:
        returned_date = date.fromisoformat(data["date"])
        if returned_date > requested_date:
            raise ValueError(
                f"Frankfurter returned a rate later than {requested_date}"
            )
        if data["base"] != "EUR":
            raise ValueError("Frankfurter returned an unexpected base currency")
        rate = Decimal(str(data["rates"]["RON"]))
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise ValueError("Frankfurter returned an invalid EUR/RON rate") from exc

    if not rate.is_finite() or rate <= 0:
        raise ValueError("Frankfurter returned a non-positive EUR/RON rate")
    return rate


async def get_eur_to_ron_rate(rate_date: date) -> Decimal:
    """Return the latest published EUR/RON rate on or before the requested date."""
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                ECB_RATES_URL,
                params={
                    "startPeriod": (rate_date - timedelta(days=7)).isoformat(),
                    "endPeriod": rate_date.isoformat(),
                    "format": "csvdata",
                },
            )
            response.raise_for_status()
            return _ecb_eur_rate(response.text, rate_date)
        except (httpx.HTTPError, KeyError, InvalidOperation, ValueError) as exc:
            failures.append(f"ECB lookup failed: {exc}")

        try:
            return await _frankfurter_eur_rate(client, rate_date)
        except (httpx.HTTPError, ValueError) as exc:
            failures.append(f"Frankfurter lookup failed: {exc}")

    raise ExchangeRateUnavailable(
        f"No EUR/RON rate is available for {rate_date}. "
        + "; ".join(failures)
        + ". No invoice was saved."
    )
