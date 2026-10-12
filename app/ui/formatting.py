"""Display formatting (German number and date formats)."""

from datetime import date, datetime
from decimal import Decimal

from app.ui.labels import ENUM_LABELS


def fmt_date(value: date | datetime | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def fmt_datetime(value: datetime | None) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else ""


def fmt_decimal(value: Decimal | float | None, places: int = 2) -> str:
    if value is None:
        return ""
    text = f"{Decimal(value):,.{places}f}"
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_money(value: Decimal | float | None) -> str:
    return f"{fmt_decimal(value, 2)} €" if value is not None else ""


def fmt_enum(value: str | None) -> str:
    return ENUM_LABELS.get(value, value or "")


def input_decimal(value: Decimal | None) -> str:
    """Decimal as shown in an input field (comma, no thousands separator)."""
    if value is None:
        return ""
    return format(value, "f").replace(".", ",")
