"""Record selected round-trip TPE-NRT fares from Google Flights."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fast_flights import FlightData, Passengers, TFSData, get_flights_from_filter


OUTBOUND_DATE = "2026-12-17"
RETURN_DATE = "2026-12-22"
FROM_AIRPORT = "TPE"
TO_AIRPORT = "NRT"
SEAT = "economy"
PASSENGERS = 1
FETCH_MODE = "local"
CURRENCY = "TWD"
MAX_STOPS = 0
TRADITIONAL_AIRLINES = (
    "China Airlines",
    "EVA Air",
    "Japan Airlines",
    "JAL",
    "ANA",
    "All Nippon Airways",
    "STARLUX",
)

HISTORY_FILE = Path("data/price_history.csv")
FIELDNAMES = [
    "query_date",
    "airline",
    "outbound_departure",
    "outbound_arrival",
    "outbound_duration",
    "outbound_stops",
    "round_trip_price",
    "is_best",
    "current_price_level",
]


def query_date() -> str:
    taipei_time = datetime.now(timezone.utc) + timedelta(hours=8)
    return taipei_time.date().isoformat()


def is_selected_airline(name: str) -> bool:
    return any(airline in name for airline in TRADITIONAL_AIRLINES)


def read_history() -> list[dict[str, str]]:
    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    if not rows:
        return []
    if rows[0] == FIELDNAMES:
        return [dict(zip(FIELDNAMES, row)) for row in rows[1:]]
    return [dict(zip(FIELDNAMES, row)) for row in rows]


def flight_row(flight: object, current_price_level: str) -> dict[str, str]:
    return {
        "query_date": query_date(),
        "airline": str(flight.name),
        "outbound_departure": str(flight.departure),
        "outbound_arrival": str(flight.arrival),
        "outbound_duration": str(flight.duration),
        "outbound_stops": str(flight.stops),
        "round_trip_price": str(flight.price or "Price unavailable"),
        "is_best": str(bool(flight.is_best)),
        "current_price_level": current_price_level,
    }


def deduplication_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in FIELDNAMES)


def write_history(rows: list[dict[str, str]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    flights = [
        FlightData(
            date=OUTBOUND_DATE,
            from_airport=FROM_AIRPORT,
            to_airport=TO_AIRPORT,
            max_stops=MAX_STOPS,
        ),
        FlightData(
            date=RETURN_DATE,
            from_airport=TO_AIRPORT,
            to_airport=FROM_AIRPORT,
            max_stops=MAX_STOPS,
        ),
    ]
    flight_filter = TFSData.from_interface(
        flight_data=flights,
        trip="round-trip",
        seat=SEAT,
        passengers=Passengers(adults=PASSENGERS),
        max_stops=MAX_STOPS,
    )
    result = get_flights_from_filter(
        flight_filter,
        currency=CURRENCY,
        mode=FETCH_MODE,
    )

    price_level = str(result.current_price)
    new_rows = [
        flight_row(flight, price_level)
        for flight in result.flights
        if is_selected_airline(str(flight.name)) and int(flight.stops) == MAX_STOPS
    ]
    history = read_history()
    known_rows = {deduplication_key(row) for row in history}
    for row in new_rows:
        key = deduplication_key(row)
        if key not in known_rows:
            history.append(row)
            known_rows.add(key)
    write_history(history)
    print(f"Recorded {len(new_rows)} matching fares; {len(history)} total history rows.")


if __name__ == "__main__":
    main()
