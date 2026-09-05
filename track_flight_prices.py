"""Record direct TPE-NRT fares for the preferred December travel windows.

Two trip combinations are tracked. For each one the outbound leg is taken from a
round-trip search (so its price is the round-trip total), while the return leg
needs its own one-way search -- Google Flights only lists outbound options for a
round-trip query, so return times are otherwise unavailable. That means a return
row's price is a ONE-WAY price and is there to confirm the schedule, not to be
added to the outbound total.
"""

from __future__ import annotations

import csv
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fast_flights import FlightData, Passengers, TFSData, get_flights_from_filter


FROM_AIRPORT = "TPE"
TO_AIRPORT = "NRT"
SEAT = "economy"
PASSENGERS = 1
FETCH_MODE = "local"
CURRENCY = "TWD"
MAX_STOPS = 0
# Pause between queries to look less like bot traffic. Each date combination
# costs two queries (round-trip for the outbound leg, one-way for the return),
# so a run makes four in total.
QUERY_DELAY_SECONDS = 10

# (outbound date, return date) pairs to track.
DATE_COMBOS = (
    ("2026-12-17", "2026-12-23"),
    ("2026-12-16", "2026-12-22"),
)

# Preferred arrival windows in local time at the arriving airport, as
# [start, end) minutes from midnight.
OUTBOUND_ARRIVAL_WINDOW = (12 * 60, 18 * 60)  # arrive NRT 12:00-18:00
RETURN_ARRIVAL_WINDOW = (23 * 60, 24 * 60)  # arrive TPE 23:00-24:00

# Full-service carriers only; low-cost carriers are deliberately excluded.
AIRLINE_WHITELIST = (
    "China Airlines",
    "EVA Air",
    "Japan Airlines",
    "JAL",
    "ANA",
    "All Nippon Airways",
    "STARLUX",
    "Cathay Pacific",
)

HISTORY_FILE = Path("data/price_history.csv")
GOOGLE_FLIGHTS_URL = "https://www.google.com/travel/flights?tfs="
FIELDNAMES = [
    "query_date",
    "outbound_date",
    "return_date",
    "leg",
    "airline",
    "departure",
    "arrival",
    "duration",
    "stops",
    "price",
    "price_type",
    "in_time_window",
    "is_best",
    "current_price_level",
    "booking_url",
]
# Columns that identify a distinct flight observation. booking_url is derived
# from the trip combination and leg, so it adds nothing to a row's identity.
DEDUP_FIELDS = [field for field in FIELDNAMES if field != "booking_url"]

# Matches the leading clock time of "8:20 PM on Wed, Dec 23".
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})\s*([AP]M)", re.IGNORECASE)


def query_date() -> str:
    taipei_time = datetime.now(timezone.utc) + timedelta(hours=8)
    return taipei_time.date().isoformat()


def csv_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"


def arrival_minutes(arrival: str) -> int | None:
    """Minutes from midnight for an arrival string, or None if unparseable."""
    match = TIME_PATTERN.search(arrival)
    if not match:
        return None
    hour = int(match.group(1)) % 12
    minute = int(match.group(2))
    if match.group(3).upper() == "PM":
        hour += 12
    return hour * 60 + minute


def in_window(arrival: str, window: tuple[int, int]) -> bool:
    """Whether an arrival falls inside a window.

    A next-day arrival such as "1:30 AM on Thu, Dec 24" lands at 90 minutes and
    so falls outside a late-evening window, which is the intended behaviour.
    """
    minutes = arrival_minutes(arrival)
    if minutes is None:
        return False
    start, end = window
    return start <= minutes < end


def is_selected_airline(name: str) -> bool:
    return any(airline in name for airline in AIRLINE_WHITELIST)


def is_direct(flight: object) -> bool:
    # stops is "Unknown" when the parser cannot read it; treat that as not direct
    # rather than letting int() raise.
    return str(flight.stops) == "0"


def booking_link(flight_filter: TFSData) -> str:
    """Deep link that reopens this exact search on Google Flights."""
    return GOOGLE_FLIGHTS_URL + flight_filter.as_b64().decode("utf-8")


def build_filter(flight_data: list[FlightData], trip: str) -> TFSData:
    return TFSData.from_interface(
        flight_data=flight_data,
        trip=trip,
        seat=SEAT,
        passengers=Passengers(adults=PASSENGERS),
        max_stops=MAX_STOPS,
    )


def fetch_result(flight_filter: TFSData, *, throttle: bool) -> object:
    """Run one query, pausing first so a run does not fire them back to back."""
    if throttle:
        time.sleep(QUERY_DELAY_SECONDS)
    return get_flights_from_filter(flight_filter, currency=CURRENCY, mode=FETCH_MODE)


def read_history() -> list[dict[str, str]]:
    if not HISTORY_FILE.exists():
        return []

    with HISTORY_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    if not rows:
        return []
    if rows[0] == FIELDNAMES:
        rows = rows[1:]
    return [
        {**{field: "" for field in FIELDNAMES}, **dict(zip(FIELDNAMES, row))}
        for row in rows
    ]


def rows_from_result(
    result: object,
    *,
    outbound_date: str,
    return_date: str,
    leg: str,
    price_type: str,
    window: tuple[int, int],
    booking_url: str,
) -> list[dict[str, str]]:
    price_level = str(result.current_price)
    today = query_date()
    # Google Flights renders a curated "best flights" block above the full list,
    # so the parser yields each flight twice -- once flagged best, once not.
    # Collapse those into a single row that keeps the best flag.
    collapsed: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for flight in result.flights:
        if not is_selected_airline(str(flight.name)) or not is_direct(flight):
            continue
        arrival = str(flight.arrival)
        row = {
            "query_date": today,
            "outbound_date": outbound_date,
            "return_date": return_date,
            "leg": leg,
            "airline": str(flight.name),
            "departure": str(flight.departure),
            "arrival": arrival,
            "duration": str(flight.duration),
            "stops": str(flight.stops),
            "price": str(flight.price or "Price unavailable"),
            "price_type": price_type,
            "in_time_window": csv_bool(in_window(arrival, window)),
            "is_best": csv_bool(bool(flight.is_best)),
            "current_price_level": price_level,
            "booking_url": booking_url,
        }
        key = (row["airline"], row["departure"], row["arrival"], row["price"])
        if key in collapsed:
            if row["is_best"] == "TRUE":
                collapsed[key]["is_best"] = "TRUE"
            continue
        collapsed[key] = row
    return list(collapsed.values())


def collect_rows() -> list[dict[str, str]]:
    """Query every combination and return this run's rows."""
    rows = []
    completed_queries = 0
    for outbound_date, return_date in DATE_COMBOS:
        round_trip_filter = build_filter(
            [
                FlightData(
                    date=outbound_date,
                    from_airport=FROM_AIRPORT,
                    to_airport=TO_AIRPORT,
                    max_stops=MAX_STOPS,
                ),
                FlightData(
                    date=return_date,
                    from_airport=TO_AIRPORT,
                    to_airport=FROM_AIRPORT,
                    max_stops=MAX_STOPS,
                ),
            ],
            "round-trip",
        )
        rows += rows_from_result(
            fetch_result(round_trip_filter, throttle=completed_queries > 0),
            outbound_date=outbound_date,
            return_date=return_date,
            leg="outbound",
            price_type="round_trip",
            window=OUTBOUND_ARRIVAL_WINDOW,
            booking_url=booking_link(round_trip_filter),
        )
        completed_queries += 1

        return_filter = build_filter(
            [
                FlightData(
                    date=return_date,
                    from_airport=TO_AIRPORT,
                    to_airport=FROM_AIRPORT,
                    max_stops=MAX_STOPS,
                )
            ],
            "one-way",
        )
        rows += rows_from_result(
            fetch_result(return_filter, throttle=completed_queries > 0),
            outbound_date=outbound_date,
            return_date=return_date,
            leg="return",
            price_type="one_way",
            window=RETURN_ARRIVAL_WINDOW,
            booking_url=booking_link(return_filter),
        )
        completed_queries += 1
    return rows


def deduplication_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in DEDUP_FIELDS)


def write_history(rows: list[dict[str, str]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def report(rows: list[dict[str, str]]) -> None:
    """Print the flights that match the preferred arrival windows."""
    legs = (
        ("outbound", "outbound, arrive NRT 12:00-18:00", "round-trip total"),
        ("return", "return, arrive TPE 23:00-24:00", "one-way only"),
    )
    for outbound_date, return_date in DATE_COMBOS:
        print(f"\n=== {outbound_date} -> {return_date} ===")
        for leg, label, price_note in legs:
            hits = [
                row
                for row in rows
                if row["outbound_date"] == outbound_date
                and row["leg"] == leg
                and row["in_time_window"] == "TRUE"
            ]
            print(f"  {label} -- {len(hits)} match(es), price is {price_note}")
            for row in hits:
                print(
                    f"    {row['airline']:<20} {row['departure']} -> "
                    f"{row['arrival']}  {row['price']}"
                )
            if hits:
                print(f"    link: {hits[0]['booking_url']}")


def main() -> None:
    new_rows = collect_rows()
    history = read_history()
    known_rows = {deduplication_key(row) for row in history}
    added = 0
    for row in new_rows:
        key = deduplication_key(row)
        if key not in known_rows:
            history.append(row)
            known_rows.add(key)
            added += 1
    write_history(history)
    report(new_rows)
    print(
        f"\nScanned {len(new_rows)} matching fares, added {added} new rows; "
        f"{len(history)} total history rows."
    )


if __name__ == "__main__":
    main()
