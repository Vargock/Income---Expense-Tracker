import csv, json, requests
import logging

from .config import EXCHANGE_API_KEY, EXCHANGE_API_URL, DATA_FILE, SETTINGS_FILE
from .classes import Record


def fetch_exchange_rates(base: str = "USD") -> dict[str, float]:
    # Retrieve conversion rates from the external API.
    # Returns a mapping currency_code -> rate.
    url = f"{EXCHANGE_API_URL}/{EXCHANGE_API_KEY}/latest/{base}"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("result") == "success":
            return data["conversion_rates"]
        logging.error("Exchange API error: %s", data.get("error-type"))
    except requests.RequestException as exception:
        logging.error("Request to Exchange API failed: %s", exception)
    return {}


def load_data() -> list[Record]:
    """
    Read all records from DATA_FILE, return as list of Record.
    """

    records: list[Record] = []
    try:
        with open(DATA_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rec = Record(
                        date=row["date"],
                        record_type=row["type"],
                        amount=float(row["amount"]),
                        currency=row["currency"],
                        category=row["category"],
                        description=row["description"],
                    )
                    records.append(rec)
                except (ValueError, KeyError) as e:
                    logging.warning("Skipping invalid row %s: %s", row, e)
    except FileNotFoundError:
        pass
    return records


def save_data(record: Record) -> None:
    # Append one Record to DATA_FILE, writing header if necessary.

    write_header = False
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            first_char = f.read(1)
            if (
                not first_char
            ):  # Try reading the first character, if empty  -> write_header == True
                write_header = True
    except FileNotFoundError:
        write_header = True

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "type",
                "amount",
                "currency",
                "category",
                "description",
            ],
        )

        if write_header:  # Checks if CSV needs headers, writes it in if so
            writer.writeheader()

        writer.writerow(record.to_dict())


def load_main_currency() -> str:
    # Read main_currency from SETTINGS_FILE, defaulting to 'RUB' if missing.
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("main_currency", "RUB")
    except:
        return "RUB"


def save_main_currency(currency: str) -> None:
    # Persist main_currency to SETTINGS_FILE.
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"main_currency": currency}, f)
