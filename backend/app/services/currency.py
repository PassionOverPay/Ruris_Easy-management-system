import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

BNR_RATES_URL = "https://www.bnr.ro/nbrfxrates.xml"
FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v1"


class ExchangeRateUnavailable(Exception):
    """Raised when no trusted source provides the exact requested rate."""


def _bnr_eur_rate(xml_content: bytes) -> tuple[date, Decimal]:
    root = ET.fromstring(xml_content)
    for cube in root.iter("Cube"):
        published_date = cube.get("date")
        if published_date is None:
            continue

        for rate in cube.findall(".//Rate"):
            if rate.get("currency") != "EUR":
                continue
            value = Decimal(rate.text or "")
            unit = Decimal(rate.get("unit", "1"))
            if (
                not value.is_finite()
                or not unit.is_finite()
                or value <= 0
                or unit <= 0
            ):
                raise ValueError("BNR returned an invalid EUR rate")
            return date.fromisoformat(published_date), value / unit

    raise ValueError("BNR response did not contain a dated EUR rate")


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
        if returned_date != requested_date:
            raise ValueError(
                f"Frankfurter has no EUR/RON rate published for {requested_date}"
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
    """Return the EUR/RON rate published for this exact date, or fail clearly."""
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(BNR_RATES_URL)
            response.raise_for_status()
            bnr_date, bnr_rate = _bnr_eur_rate(response.content)
            if bnr_date == rate_date:
                return bnr_rate
            failures.append(f"BNR has a rate for {bnr_date}, not {rate_date}")
        except (httpx.HTTPError, ET.ParseError, InvalidOperation, ValueError) as exc:
            failures.append(f"BNR lookup failed: {exc}")

        try:
            return await _frankfurter_eur_rate(client, rate_date)
        except (httpx.HTTPError, ValueError) as exc:
            failures.append(f"Frankfurter lookup failed: {exc}")

    raise ExchangeRateUnavailable(
        f"No EUR/RON rate is available for {rate_date}. "
        + "; ".join(failures)
        + ". No invoice was saved."
    )
