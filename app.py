# app.py

from __future__ import annotations
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
import csv

from modules.utilities import (
    load_data,
    load_main_currency,
    save_data,
    save_main_currency,
    fetch_exchange_rates,
)
from modules.classes import Record
from modules.config import DATA_FILE

# ─── 1. CONFIG & CONSTANTS ────────────────────────────────────────


app = Flask(__name__)


# ─── 2. FLASK FILTERS ────────────────────────────────────────────


@app.template_filter("format_currency")
def format_currency(value: float, currency: str) -> str:
    # Jinja filter: format 2 decimals, add thousand separators, localization.
    formatted = f"{value:,.2f}"
    if currency == "RUB":
        # swap commas/spaces and dot/comma
        formatted = formatted.replace(",", " ").replace(".", ",")
    return f"{formatted} {currency}"


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

    entry_types = sorted(
        set(r.type.upper() for r in records if r.type in ("income", "expense"))
    )
    print(entry_types)

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
    serialized_records = [record.to_dict() for record in records]

    return render_template(
        "index.html",
        records=records,
        serialized_records=serialized_records,
        income=round(income, 2),
        expense=round(expense, 2),
        balance=round(balance, 2),
        entry_types=entry_types,
        main_currency=main_currency,
        rates=rates,
        balance_status=balance_status,
        has_description=any(entry.description for entry in records),
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
        category=request.form.get("category").strip(),
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
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_dict())
        app.logger.info("Deleted record: %s", removed)
    return redirect(url_for("index"))


# ─── 6. APP ENTRY POINT ────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
