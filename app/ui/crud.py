"""Generic CRUD views implementing the uniform create / edit / delete pattern (spec 12)."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from flask import abort, flash, redirect, render_template, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.ui.resource import Node, Resource, dependencies, dependency_message, with_args

logger = logging.getLogger(__name__)

REGISTRY: dict[str, Resource] = {}


def safe_next(value: str | None) -> str | None:
    """Only accept local absolute paths as redirect targets."""
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return None


def apply_open_state(roots: list[Node], args) -> None:
    """Set ``open`` on all nodes: level 1 open by default, plus the nodes named in ``open``."""
    mode = args.get("expand")
    wanted = {k for k in (args.get("open") or "").split(",") if k}

    def visit(node: Node, level: int) -> bool:
        contains = node.key in wanted
        for child in node.children:
            contains = visit(child, level + 1) or contains
        node.open = contains or mode == "all" or (mode != "none" and level == 1)
        return contains

    for root in roots:
        visit(root, 1)


def get_or_404(res: Resource, row_id: int):
    obj = db.session.get(res.model, row_id)
    if obj is None:
        abort(404)
    return obj


def render_form(res: Resource, obj, raw: dict, errors: dict, next_url: str, status: int = 200):
    creating = obj is None
    sections: dict[str, list] = {}
    for f in res.fields:
        sections.setdefault(f.section, []).append(f)
    title = res.new_label if creating else f"{res.singular} bearbeiten"
    return (
        render_template(
            "crud/form.html",
            res=res,
            obj=obj,
            raw=raw,
            errors=errors,
            sections=sections,
            title=title,
            next_url=next_url,
            creating=creating,
            multipart=any(f.kind == "file" for f in res.fields),
        ),
        status,
    )


def handle_form(res: Resource, obj=None):
    creating = obj is None
    default_next = res.index_url()
    next_url = safe_next(request.values.get("next")) or default_next

    if request.method == "GET":
        raw = res.prefill(request.args) if creating else res.form_values(obj)
        return render_form(res, obj, raw, {}, next_url)

    values, errors = res.parse(request.form, request.files, obj)
    if not errors:
        errors = {**res.validate(res.current(obj, values), obj), **res.check_unique(values, obj)}
    if errors:
        logger.info("%s: validation failed (%s)", res.slug, sorted(errors))
        return render_form(res, obj, request.form.to_dict(), errors, next_url, 422)

    try:
        if creating:
            obj = res.model()
            res.create_defaults(obj)
            db.session.add(obj)
        res.populate(obj, values, creating)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.exception("%s: integrity error while saving", res.slug)
        return render_form(
            res,
            None if creating else db.session.get(res.model, obj.id),
            request.form.to_dict(),
            {"_form": "Der Eintrag verletzt eine Datenbankbedingung und wurde nicht gespeichert."},
            next_url,
            422,
        )

    logger.info("%s: %s id=%s", res.slug, "created" if creating else "updated", obj.id)
    flash(f"{res.singular} „{res.title(obj)}“ wurde {'angelegt' if creating else 'gespeichert'}.", "success")
    for warning in res.warnings(obj):
        flash(warning, "warning")
    target = with_args(next_url, open=res.node_key(obj))
    return redirect(f"{target}#{res.node_key(obj)}")


def handle_delete(res: Resource, obj):
    next_url = safe_next(request.values.get("next")) or res.index_url()
    if not (res.deletable and res.can_delete(obj)):
        abort(403)

    if request.method == "GET":
        return render_template(
            "crud/confirm_delete.html",
            res=res,
            obj=obj,
            next_url=next_url,
            title=f"{res.singular} löschen",
        )

    title = res.title(obj)
    row_id = obj.id
    blocker = res.delete_blocker(obj)
    deps = dependencies(res.model, row_id)
    if blocker or deps:
        flash(blocker or f"„{title}“ kann nicht gelöscht werden. {dependency_message(deps)}.", "error")
        return redirect(next_url)

    cleanup = res.prepare_delete(obj)
    try:
        db.session.execute(sa.delete(res.model.__table__).where(res.model.__table__.c.id == row_id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.exception("%s: integrity error while deleting id=%s", res.slug, row_id)
        flash(f"„{title}“ kann nicht gelöscht werden, da der Eintrag noch verwendet wird.", "error")
        return redirect(next_url)
    if cleanup:
        cleanup()
    logger.info("%s: deleted id=%s", res.slug, row_id)
    flash(f"{res.singular} „{title}“ wurde gelöscht.", "success")
    return redirect(next_url)


def handle_index(res: Resource):
    page = max(request.args.get("page", 1, type=int), 1)
    query = res.list_query(request.args)
    total = db.session.scalar(sa.select(sa.func.count()).select_from(query.order_by(None).subquery()))
    items = db.session.scalars(query.limit(res.per_page).offset((page - 1) * res.per_page)).all()
    pages = max((total + res.per_page - 1) // res.per_page, 1)
    next_url = request.full_path.rstrip("?")
    return render_template(
        "crud/list.html",
        res=res,
        items=items,
        total=total,
        page=page,
        pages=pages,
        next_url=next_url,
        new_url=res.url("new", next=next_url, **res.new_params(request.args)) if res.creatable else None,
        args=request.args,
        title=res.plural,
    )


def handle_detail(res: Resource, obj):
    detail_url = res.url("detail", obj)
    list_url = res.index_url()
    head_actions = [
        *res.detail_actions(obj, detail_url),
        *[a for a in res.actions(obj, detail_url) if a.kind == "edit"],
        *[a for a in res.actions(obj, list_url) if a.kind == "delete"],
    ]
    return render_template(
        "crud/detail.html",
        res=res,
        obj=obj,
        children=res.children(obj),
        next_url=detail_url,
        list_url=list_url,
        head_actions=head_actions,
        title=f"{res.singular}: {res.title(obj)}",
    )


def register_crud(bp, res: Resource, *, index: bool = True) -> Resource:
    """Register the uniform routes of a resource on an area blueprint."""
    res.bp_name = bp.name
    REGISTRY[res.slug] = res
    s = res.slug

    def rule(path: str, action: str, view, methods=("GET",)):
        bp.add_url_rule(f"/{s}/{path}", f"{s}_{action}", view, methods=list(methods))

    if index:
        rule("", "index", lambda: handle_index(res))
    if res.has_detail:
        rule("<int:id>", "detail", lambda id: handle_detail(res, get_or_404(res, id)))
    if res.creatable:
        rule("neu", "new", lambda: handle_form(res), ("GET", "POST"))
    if res.editable:

        def edit(id):
            obj = get_or_404(res, id)
            if not res.can_edit(obj):
                abort(403)
            return handle_form(res, obj)

        rule("<int:id>/bearbeiten", "edit", edit, ("GET", "POST"))
    if res.deletable:
        rule("<int:id>/loeschen", "delete", lambda id: handle_delete(res, get_or_404(res, id)), ("GET", "POST"))
    return res
