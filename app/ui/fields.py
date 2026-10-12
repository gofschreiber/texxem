"""Form field definitions with parsing and validation derived from the model columns."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa

from app.ui.formatting import fmt_date, fmt_decimal, fmt_enum, input_decimal

INT_MAX = 2**31 - 1
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Field:
    """One form field. ``attr`` is the model attribute (or a free name if ``virtual``)."""

    def __init__(
        self,
        attr: str,
        label: str,
        *,
        kind: str | None = None,
        choices: Callable[[], list[tuple]] | None = None,
        required: bool | None = None,
        section: str = "Allgemein",
        help: str | None = None,
        editable: bool = True,
        virtual: bool = False,
        min_length: int | None = None,
        optional_on_edit: bool = False,
    ):
        self.attr = attr
        self.label = label
        self.kind = kind
        self.choices_fn = choices
        self.required = required
        self.section = section
        self.help = help
        self.editable = editable
        self.virtual = virtual
        self.min_length = min_length
        self.optional_on_edit = optional_on_edit
        self.name = attr
        self.column: sa.Column | None = None
        self.max_length: int | None = None
        self.precision: int | None = None
        self.scale: int | None = None
        self.enum_values: list[str] | None = None
        self.default = None

    def bind(self, model) -> Field:
        if self.virtual:
            self.required = bool(self.required)
            return self
        column = getattr(model, self.attr).property.columns[0]
        self.column = column
        self.name = column.name
        col_type = column.type
        if self.required is None:
            self.required = not column.nullable and not isinstance(col_type, sa.Boolean)
        if column.default is not None and not callable(column.default.arg):
            self.default = column.default.arg
        if self.kind is None:
            if isinstance(col_type, sa.Enum) or self.choices_fn is not None:
                self.kind = "select"
            elif isinstance(col_type, sa.Boolean):
                self.kind = "bool"
            elif isinstance(col_type, sa.Integer):
                self.kind = "int"
            elif isinstance(col_type, sa.Numeric):
                self.kind = "decimal"
            elif isinstance(col_type, sa.Date):
                self.kind = "date"
            elif isinstance(col_type, sa.Text):
                self.kind = "textarea"
            else:
                self.kind = "text"
        if isinstance(col_type, sa.Enum):
            self.enum_values = list(col_type.enums)
        if isinstance(col_type, sa.String) and not isinstance(col_type, sa.Enum):
            self.max_length = col_type.length
        if isinstance(col_type, sa.Numeric):
            self.precision, self.scale = col_type.precision, col_type.scale
        return self

    @property
    def is_integer_column(self) -> bool:
        return self.column is not None and isinstance(self.column.type, sa.Integer)

    def choices(self) -> list[tuple]:
        if self.choices_fn is not None:
            return list(self.choices_fn())
        if self.enum_values is not None:
            return [(v, fmt_enum(v)) for v in self.enum_values]
        return []

    # ------------------------------------------------------------------ parsing
    def parse(self, raw) -> tuple[object, str | None]:
        """Return (python value, error message)."""
        if self.kind == "bool":
            return bool(raw), None
        if self.kind == "file":
            if raw is None or not getattr(raw, "filename", ""):
                return None, "Bitte eine Datei auswählen." if self.required else None
            return raw, None

        text = (raw or "").strip()
        if text == "":
            return None, "Bitte ausfüllen." if self.required else None

        if self.kind in ("text", "textarea", "email", "password"):
            if self.max_length and len(text) > self.max_length:
                return None, f"Maximal {self.max_length} Zeichen erlaubt."
            if self.min_length and len(text) < self.min_length:
                return None, f"Mindestens {self.min_length} Zeichen erforderlich."
            if self.kind == "email" and not EMAIL_RE.match(text):
                return None, "Bitte eine gültige E-Mail-Adresse eingeben."
            return (raw if self.kind == "password" else text), None
        if self.kind in ("int", "select", "hidden"):
            return self._parse_choice_or_int(text)
        if self.kind == "decimal":
            return self._parse_decimal(text)
        if self.kind == "date":
            return self._parse_date(text)
        return text, None

    def _parse_choice_or_int(self, text: str) -> tuple[object, str | None]:
        if self.kind == "int" or self.is_integer_column:
            try:
                value = int(text)
            except ValueError:
                return None, "Bitte eine ganze Zahl eingeben."
            if abs(value) > INT_MAX:
                return None, "Wert ist zu groß."
        else:
            value = text
        if self.kind == "select":
            valid = {c[0] for c in self.choices()}
            if value not in valid:
                return None, "Bitte einen gültigen Eintrag auswählen."
        return value, None

    def _parse_decimal(self, text: str) -> tuple[object, str | None]:
        normalized = text.replace(" ", "")
        if "," in normalized:
            normalized = normalized.replace(".", "").replace(",", ".")
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            return None, "Bitte eine Zahl eingeben."
        if not value.is_finite():
            return None, "Bitte eine Zahl eingeben."
        if self.scale is not None:
            if -value.as_tuple().exponent > self.scale:
                return None, f"Maximal {self.scale} Nachkommastellen erlaubt."
            limit = Decimal(10) ** (self.precision - self.scale)
            if abs(value) >= limit:
                return (
                    None,
                    f"Wert ist zu groß (maximal {fmt_decimal(limit - Decimal(1) / 10**self.scale, self.scale)}).",
                )
        return value, None

    @staticmethod
    def _parse_date(text: str) -> tuple[object, str | None]:
        for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(text, pattern).date(), None
            except ValueError:
                continue
        return None, "Bitte ein gültiges Datum eingeben."

    # ------------------------------------------------------------------ rendering
    def input_value(self, value) -> str:
        """Model value -> string for an HTML input."""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "1" if value else ""
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return input_decimal(value)
        return str(value)

    def static_text(self, raw: str) -> str:
        """Raw form value -> read-only text (non-editable field on the edit form)."""
        if raw in (None, ""):
            return ""
        if self.kind == "select":
            return {str(v): label for v, label in self.choices()}.get(str(raw), str(raw))
        if self.kind == "bool":
            return "Ja"
        if self.kind == "date":
            parsed, error = self._parse_date(raw)
            return fmt_date(parsed) if not error else str(raw)
        return str(raw)

    def display(self, value) -> str:
        """Model value -> human readable text (detail pages)."""
        if value is None or value == "":
            return ""
        if self.kind == "bool":
            return "Ja" if value else "Nein"
        if self.kind == "select":
            return dict(self.choices()).get(value, str(value))
        if isinstance(value, date):
            return fmt_date(value)
        if isinstance(value, Decimal):
            return fmt_decimal(value, self.scale if self.scale is not None else 2)
        return str(value)
