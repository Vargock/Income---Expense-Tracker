# app.py

from __future__ import annotations
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for

import csv
import json
import requests

# ─── 1. CONFIG & CONSTANTS ────────────────────────────────────────

DATA_FILE = "data.csv"
SETTINGS_FILE = "settings.json"
EXCHANGE_API_KEY = "3f7daa467d1bc05c774e7af9"  # Personal API Key
EXCHANGE_API_URL = "https://v6.exchangerate-api.com/v6"  # Basic API url

app = Flask(__name__)


# ─── 2. DATA CLASSES ─────────────────────────────────────────────


class Record:
    # A single budget entry.

    def __init__(
        self,
        date: str,
        record_type: str,
        amount: float,
        currency: str,
        description: str,
    ):
        self.date = date
        self.type = record_type  # "income" or "expense"
        self.amount = amount
        self.currency = currency
        self.description = description

    def convert_amount(self, rate: float) -> float:
        # Convert self.amount to main currency by dividing by rate.
        return self.amount / rate

    def to_dict(self) -> dict[str, str]:
        # Serialize for CSV writing.
        return {
            "date": self.date,
            "type": self.type,
            "amount": f"{self.amount}",
            "currency": self.currency,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"Record(date={self.date!r}, type={self.type!r}, "
            f"amount={self.amount!r}, currency={self.currency!r}, "
            f"description={self.description!r})"
        )


# ─── 3. FLASK FILTERS ────────────────────────────────────────────


@app.template_filter("format_currency")
def format_currency(value: float, currency: str) -> str:
    # Jinja filter: format 2 decimals, add thousand separators, localization.
    formatted = f"{value:,.2f}"
    if currency == "RUB":
        # swap commas/spaces and dot/comma
        formatted = formatted.replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}"


# ─── 4. UTILITY FUNCTIONS ────────────────────────────────────────


def fetch_exchange_rates(base: str = "USD") -> dict[str, float]:
    # Retrieve conversion rates from the external API.
    # Returns a mapping currency_code -> rate.
    url = f"{EXCHANGE_API_URL}/{EXCHANGE_API_KEY}/latest/{base}"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("result") == "success":
            return data["conversion_rates"]
        app.logger.error("Exchange API error: %s", data.get("error-type"))
    except requests.RequestException as exception:
        app.logger.error("Request to Exchange API failed: %s", exception)
    return {}


def load_data() -> list[Record]:
    # Read all records from DATA_FILE, return as list of Record.

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
                        description=row["description"],
                    )
                    records.append(rec)
                except (ValueError, KeyError) as e:
                    app.logger.warning("Skipping invalid row %s: %s", row, e)
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
            fieldnames=["date", "type", "amount", "currency", "description"],
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
    except (FileNotFoundError, json.JSONDecodeError):
        return "RUB"


def save_main_currency(currency: str) -> None:
    # Persist main_currency to SETTINGS_FILE.
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"main_currency": currency}, f)


# ─── 5. ROUTES ────────────────────────────────────────────────────


@app.route("/")
def index():
    # Render the main dashboard:
    #   - Load records
    #   - Load user’s main currency
    #   - Fetch rates
    #   - Compute income, expense, balance

    records = load_data()
    main_currency = load_main_currency()
    rates = fetch_exchange_rates(main_currency) or {main_currency: 1.0}

    income = sum(
        r.convert_amount(rates.get(r.currency, 1.0))
        for r in records
        if r.type == "income"
    )
    expense = sum(
        r.convert_amount(rates.get(r.currency, 1.0))
        for r in records
        if r.type == "expense"
    )
    balance = income - expense
    balance_status = "debt" if balance < 0 else "normal"

    return render_template(
        "index.html",
        records=records,
        income=round(income, 2),
        expense=round(expense, 2),
        balance=round(balance, 2),
        main_currency=main_currency,
        rates=rates,
        balance_status=balance_status,
    )


@app.route("/add", methods=["POST"])
def add_entry():
    # Handle form submission to add a new record.
    # Infers type from sign of amount (>=0 → income, <0 → expense).

    raw_amount = float(request.form["amount"])

    record = Record(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        record_type=request.form["type"],
        amount=abs(raw_amount),
        currency=request.form.get("currency", load_main_currency()),
        description=request.form.get("description", "").strip(),
    )

    save_data(record)
    return redirect(url_for("index"))


@app.route("/set_currency", methods=["POST"])
def change_currency():
    # Save the user’s preferred main currency and redirect home.
    currency = request.form.get("main_currency")
    if currency:
        save_main_currency(currency)
    return redirect(url_for("index"))


@app.route("/delete/<int:idx>", methods=["POST"])
def delete_entry(idx: int):
    # Delete the record at position index in the CSV.
    # Then rewrite the file without it.
    records = load_data()
    if 0 <= idx < len(records):
        removed = records.pop(idx)
        # rewrite CSV
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["date", "type", "amount", "currency", "description"]
            )
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_dict())
        app.logger.info("Deleted record: %s", removed)
    return redirect(url_for("index"))


# ─── 6. APP ENTRY POINT ────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
