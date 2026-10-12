"""Resource description used by the generic CRUD views, tables and trees."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlsplit, urlunsplit

import sqlalchemy as sa
from flask import current_app, url_for

from app.extensions import db
from app.ui.fields import Field
from app.ui.labels import count_label


@dataclass
class Column:
    """A table column. ``getter`` is a model attribute name or a callable(obj)."""

    label: str
    getter: str | Callable
    kind: str = "text"  # text | num | date | money | decimal | bool | badge | enum
    link: bool = False

    def value(self, obj):
        return self.getter(obj) if callable(self.getter) else getattr(obj, self.getter)


@dataclass
class Action:
    kind: str  # add | view | edit | delete | status
    label: str
    url: str


@dataclass
class ChildTable:
    title: str
    res: Resource
    items: list
    add: Action | None = None
    note: str | None = None


@dataclass
class Node:
    key: str
    kind: str  # icon name
    title: str
    url: str | None = None
    meta: list[tuple[str, str]] = field(default_factory=list)
    badges: list[tuple[str, str]] = field(default_factory=list)  # (text, css modifier)
    actions: list[Action] = field(default_factory=list)
    children: list[Node] = field(default_factory=list)
    empty: str | None = None
    open: bool = False

    @property
    def is_leaf(self) -> bool:
        return not self.children and self.empty is None


def with_args(url: str, **params) -> str:
    """Add query parameters to a (relative) URL, replacing existing ones with the same name."""
    parts = urlsplit(url)
    query = dict(p.split("=", 1) if "=" in p else (p, "") for p in parts.query.split("&") if p)
    query.update({k: v for k, v in params.items() if v is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def dependencies(model, row_id: int) -> list[tuple[str, int]]:
    """Rows in other tables referencing the given row: [(table name, count)]."""
    table = model.__table__
    counts: dict[str, int] = {}
    for other in db.metadata.sorted_tables:
        for fk in other.foreign_keys:
            if fk.column.table is table and fk.parent.table is other:
                n = db.session.scalar(sa.select(sa.func.count()).select_from(other).where(fk.parent == row_id))
                if n:
                    counts[other.name] = counts.get(other.name, 0) + n
    return list(counts.items())


def dependency_message(deps: list[tuple[str, int]]) -> str:
    return "Wird noch verwendet von: " + ", ".join(count_label(t, n) for t, n in deps)


class Resource:
    slug = ""
    model = None
    singular = ""
    plural = ""
    fields: list[Field] = []
    columns: list[Column] = []
    creatable = True
    editable = True
    deletable = True
    has_detail = True
    searchable = False
    per_page = 25
    create_label: str | None = None
    # list filters: (query parameter, label, "select" | "date", choices callable or None)
    filters: list[tuple] = []
    # unique constraint (column names) -> message
    unique_messages: dict[tuple, str] = {}

    def __init__(self):
        self.bp_name: str | None = None
        self.fields = [f.bind(self.model) for f in self.fields]
        self.field_by_name = {f.name: f for f in self.fields}

    # ------------------------------------------------------------------ naming / urls
    def endpoint(self, action: str) -> str:
        return f"{self.bp_name}.{self.slug}_{action}"

    def url(self, action: str, obj=None, **params) -> str:
        if obj is not None:
            params["id"] = obj.id
        return url_for(self.endpoint(action), **{k: v for k, v in params.items() if v is not None})

    def index_url(self, **params) -> str:
        """URL of the list/tree page, or the dashboard if the resource has none."""
        if self.endpoint("index") in current_app.view_functions:
            return self.url("index", **params)
        return url_for("main.dashboard")

    def node_key(self, obj) -> str:
        return f"{self.slug}-{obj.id}"

    def title(self, obj) -> str:
        return str(getattr(obj, "name", obj.id))

    def view_url(self, obj) -> str | None:
        return self.url("detail", obj) if self.has_detail else None

    @property
    def new_label(self) -> str:
        return self.create_label or f"{self.singular} anlegen"

    # ------------------------------------------------------------------ permissions
    def can_edit(self, obj) -> bool:
        return self.editable

    def can_delete(self, obj) -> bool:
        return self.deletable

    def delete_blocker(self, obj) -> str | None:
        """Business reason why deleting is currently impossible (shown as error)."""
        return None

    # ------------------------------------------------------------------ listing
    def order(self):
        return [self.model.id]

    def search_attrs(self) -> list:
        return []

    def list_query(self, args):
        query = sa.select(self.model)
        term = (args.get("q") or "").strip()
        if self.searchable and term:
            like = f"%{term}%"
            query = query.where(sa.or_(*[a.ilike(like) for a in self.search_attrs()]))
        return query.order_by(*self.order())

    def new_params(self, args) -> dict:
        """Query parameters for the 'new' button on the list page (e.g. active filters)."""
        return {}

    def children(self, obj) -> list[ChildTable]:
        return []

    # ------------------------------------------------------------------ actions
    def add_action(self, label: str | None = None, **params) -> Action:
        return Action("add", label or f"+ {self.singular}", self.url("new", **params))

    def detail_actions(self, obj, next_url: str) -> list[Action]:
        """Extra actions in the detail header (before edit/delete)."""
        return []

    def actions(self, obj, next_url: str) -> list[Action]:
        acts = []
        view = self.view_url(obj)
        if view:
            acts.append(Action("view", "Anzeigen", view))
        if self.editable and self.can_edit(obj):
            acts.append(Action("edit", "Bearbeiten", self.url("edit", obj, next=next_url)))
        if self.deletable and self.can_delete(obj):
            acts.append(Action("delete", "Löschen", self.url("delete", obj, next=next_url)))
        return acts

    def node(self, obj, icon: str, next_url: str, *, adds=(), title: str | None = None, **kwargs) -> Node:
        return Node(
            key=self.node_key(obj),
            kind=icon,
            title=title or self.title(obj),
            url=self.view_url(obj),
            actions=[*adds, *self.actions(obj, next_url)],
            **kwargs,
        )

    # ------------------------------------------------------------------ forms
    def prefill(self, args) -> dict[str, str]:
        """Initial raw form values for 'new' (query parameters and column defaults)."""
        values = {}
        for f in self.fields:
            if f.name in args:
                values[f.name] = args[f.name]
            elif f.default is not None:
                values[f.name] = f.input_value(f.default)
        return values

    def form_values(self, obj) -> dict[str, str]:
        return {
            f.name: f.input_value(getattr(obj, f.attr)) for f in self.fields if not f.virtual and f.kind != "password"
        }

    def parse(self, form, files, obj) -> tuple[dict, dict]:
        values: dict = {}
        errors: dict = {}
        for f in self.fields:
            if obj is not None and not f.editable:
                continue
            if f.kind == "file":
                raw = files.get(f.name)
            elif f.kind == "bool":
                raw = f.name in form
            else:
                raw = form.get(f.name)
            if f.optional_on_edit and obj is not None and not (raw or "").strip():
                continue
            value, error = f.parse(raw)
            if error:
                errors[f.name] = error
            else:
                values[f.name] = value
        return values, errors

    def current(self, obj, values: dict) -> dict:
        """Parsed values merged over the persisted ones (keyed by column name)."""
        merged = {}
        if obj is not None:
            for f in self.fields:
                if not f.virtual:
                    merged[f.name] = getattr(obj, f.attr)
        merged.update(values)
        return merged

    def validate(self, values: dict, obj) -> dict[str, str]:
        """Cross-field validation on the merged values; returns {field name: message}."""
        return {}

    def check_unique(self, values: dict, obj) -> dict[str, str]:
        errors = {}
        mapper = sa.inspect(self.model)
        merged = self.current(obj, values)
        for constraint in self.model.__table__.constraints:
            if not isinstance(constraint, sa.UniqueConstraint):
                continue
            cols = [c.name for c in constraint.columns]
            if any(merged.get(c) is None for c in cols):
                continue
            conditions = [
                getattr(self.model, mapper.get_property_by_column(constraint.columns[c]).key) == merged[c] for c in cols
            ]
            query = sa.select(sa.func.count()).select_from(self.model).where(*conditions)
            if obj is not None:
                query = query.where(self.model.id != obj.id)
            if db.session.scalar(query):
                target = next((c for c in reversed(cols) if c in self.field_by_name), "_form")
                errors[target] = self.unique_messages.get(
                    tuple(cols), "Ein Eintrag mit diesen Werten existiert bereits."
                )
        return errors

    def create_defaults(self, obj) -> None:
        """Set non-form attributes on a newly created object."""

    def populate(self, obj, values: dict, creating: bool) -> None:
        for f in self.fields:
            if not f.virtual and f.name in values:
                setattr(obj, f.attr, values[f.name])

    def warnings(self, obj) -> list[str]:
        return []

    def prepare_delete(self, obj) -> Callable[[], None] | None:
        """Called before deleting; the returned callback runs after a successful commit."""
        return None
