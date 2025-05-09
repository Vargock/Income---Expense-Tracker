class Record:
    # A single budget entry.

    def __init__(
        self,
        date: str,
        record_type: str,
        amount: float,
        currency: str,
        category: str,
        description: str,
    ):
        self.date = date
        self.type = record_type  # "income" or "expense"
        self.amount = amount
        self.currency = currency
        self.category = category
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
            "category": self.category,
            "description": self.description,
        }

    def __repr__(self) -> str:
        return (
            f"Record(date={self.date!r}, type={self.type!r}, "
            f"amount={self.amount!r}, currency={self.currency!r}, "
            f"caregory={self.category!r}, description={self.description!r})"
        )
