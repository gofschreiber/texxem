"""Cross-cutting UI consistency: uniform actions, forms, trees, layout and the single central stylesheet (spec 10-17)."""

import io
import re
from pathlib import Path

import pytest

from app.ui.crud import REGISTRY
from tests.helpers import (
    create_cost,
    create_meter,
    create_reading,
    create_statement,
    setup_house,
)
from tests.ui import UI

ROOT = Path(__file__).resolve().parent.parent
ACTION_ORDER = ["Anzeigen", "Bearbeiten", "Löschen"]
TREE_PAGES = ["/objekte/", "/zaehler/", "/verteilung/", "/kosten/", "/abrechnungen/"]
LIST_PAGES = [
    "/eigentuemer/",
    "/mieter/",
    "/zaehlertypen/",
    "/zaehlerstaende/",
    "/benutzer/",
    "/kostenarten/",
    "/mietverhaeltnisse/",
    "/wohneinheiten/",
]


@pytest.fixture
def data(admin, query):
    """One row of every kind, created through the UI."""
    house = setup_house(admin, query)
    meter = create_meter(admin, query, unit_id=house["unit"])
    reading = create_reading(admin, query, meter)
    cost = create_cost(admin, query, house["property"])
    admin.post(
        "/belege/neu",
        {"kosten_id": cost, "next": "/kosten/", "file": (io.BytesIO(b"x"), "beleg.pdf", "application/pdf")},
        form_url=f"/belege/neu?kosten_id={cost}",
        content_type="multipart/form-data",
    )
    admin.submit(
        "/verteilung/neu",
        {"objekt_id": house["property"], "kostenart_id": 1, "verteilerschluessel_id": 1, "gueltig_ab": "2024-01-01"},
    )
    statement = create_statement(admin, query, house["property"])
    return {**house, "meter": meter, "reading": reading, "cost": cost, "statement": statement}


def pages(admin, urls):
    for url in urls:
        response = admin.get(f"{url}?expand=all" if url in TREE_PAGES else url)
        assert response.status_code == 200, url
        yield url, admin.soup(response)


def action_labels(actions_el):
    return [a["aria-label"] for a in actions_el.select("a[aria-label]")]


def all_pages(admin, data):
    urls = [*TREE_PAGES, *LIST_PAGES, "/", "/passwort"]
    urls += [
        f"/{slug}/{data_id}"
        for slug, data_id in [
            ("eigentuemer", data["owner"]),
            ("objekte", data["property"]),
            ("wohneinheiten", data["unit"]),
            ("mieter", data["tenant"]),
            ("mietverhaeltnisse", data["tenancy"]),
            ("zaehler", data["meter"]),
            ("zaehlerstaende", data["reading"]),
            ("kosten", data["cost"]),
            ("abrechnungen", data["statement"]),
        ]
    ]
    urls += [f"/{s}/neu" for s, r in REGISTRY.items() if r.creatable]
    return urls


# ------------------------------------------------------------------ uniform CRUD pattern (spec 12)
def test_every_creatable_resource_offers_the_same_form_layout(admin):
    checked = []
    for slug, res in REGISTRY.items():
        if not res.creatable:
            continue
        soup = admin.soup(admin.get(f"/{slug}/neu"))
        buttons = soup.select("form .form__actions > *")
        assert [b.get_text(strip=True) for b in buttons] == ["Speichern", "Abbrechen"], slug
        assert (
            "btn--primary" in buttons[0]["class"] and buttons[0].name == "button" and buttons[0]["type"] == "submit"
        ), slug
        assert "btn--secondary" in buttons[1]["class"] and buttons[1].name == "a", slug
        assert soup.select_one("form input[name=csrf_token]") and soup.select_one("form input[name=next]"), slug
        assert soup.select_one("h1").get_text(strip=True) == res.new_label, slug
        form = soup.select_one("main form")
        assert form["method"] == "post" and form.has_attr("novalidate"), slug
        assert not soup.select("form .btn--danger"), f"{slug}: no delete button inside the form"
        checked.append(slug)
    assert len(checked) == 13, checked


def test_edit_forms_use_the_same_layout_and_title(admin, data):
    for slug, key in [
        ("eigentuemer", "owner"),
        ("objekte", "property"),
        ("wohneinheiten", "unit"),
        ("mieter", "tenant"),
        ("mietverhaeltnisse", "tenancy"),
        ("zaehler", "meter"),
        ("zaehlerstaende", "reading"),
        ("kosten", "cost"),
    ]:
        res = REGISTRY[slug]
        soup = admin.soup(admin.get(f"/{slug}/{data[key]}/bearbeiten"))
        assert soup.select_one("h1").get_text(strip=True) == f"{res.singular} bearbeiten", slug
        assert [b.get_text(strip=True) for b in soup.select("form .form__actions > *")] == ["Speichern", "Abbrechen"], (
            slug
        )


def test_primary_action_is_top_right_on_every_list_and_tree(admin, data):
    for url, soup in pages(
        admin, [*TREE_PAGES, "/eigentuemer/", "/mieter/", "/zaehlertypen/", "/zaehlerstaende/", "/benutzer/"]
    ):
        primary = soup.select(".page-header .page-header__actions a.btn--primary")
        assert len(primary) == 1, url
        assert primary[0].get_text(strip=True).startswith("+ "), url
        assert soup.select_one(".page-header").find("h1"), url


def test_row_and_node_actions_always_in_uniform_order(admin, data):
    seen = 0
    for url, soup in pages(admin, [*TREE_PAGES, *LIST_PAGES]):
        for actions in soup.select(".actions"):
            labels = action_labels(actions)
            assert labels == sorted(labels, key=ACTION_ORDER.index), f"{url}: {labels}"
            seen += len(labels)
            for a in actions.select("a[aria-label]"):
                assert a.get("title") == a["aria-label"], url
                assert a.select_one("svg.icon"), f"{url}: icon missing"
                if a["aria-label"] == "Löschen":
                    assert "btn--danger" in a["class"], url
    assert seen > 30


def test_add_actions_precede_icon_actions_and_are_text_buttons(admin, data):
    for url, soup in pages(admin, TREE_PAGES):
        for actions in soup.select(".tree__actions .actions"):
            kinds = ["add" if "btn--secondary" in a["class"] else "icon" for a in actions.select("a")]
            assert kinds == sorted(kinds, key=["add", "icon"].index), f"{url}: {kinds}"
            for a in actions.select("a.btn--secondary"):
                assert a.get_text(strip=True), f"{url}: text button without text"


def test_delete_confirmation_pages_are_uniform_and_two_step(admin, data):
    for slug, key in [
        ("eigentuemer", "owner"),
        ("objekte", "property"),
        ("wohneinheiten", "unit"),
        ("mieter", "tenant"),
        ("mietverhaeltnisse", "tenancy"),
        ("zaehler", "meter"),
        ("zaehlerstaende", "reading"),
        ("kosten", "cost"),
        ("abrechnungen", "statement"),
    ]:
        res = REGISTRY[slug]
        response = admin.get(f"/{slug}/{data[key]}/loeschen")
        assert response.status_code == 200, slug
        soup = admin.soup(response)
        assert [b.get_text(strip=True) for b in soup.select("form .form__actions > *")] == [
            "Endgültig löschen",
            "Abbrechen",
        ], slug
        assert "btn--danger" in soup.select_one("form .form__actions button")["class"], slug
        assert res.singular in soup.select_one("form p").get_text(), slug
        assert soup.select_one("form input[name=csrf_token]"), slug


def test_flash_messages_use_uniform_wording(admin, query):
    created = admin.submit("/zaehlertypen/neu", {"bezeichnung": "Solar", "einheit": "kWh", "aktiv": "1"})
    type_id = query("SELECT id FROM zaehlertyp WHERE bezeichnung='Solar'")[0]["id"]
    saved = admin.submit(
        f"/zaehlertypen/{type_id}/bearbeiten", {"bezeichnung": "Solar", "einheit": "MWh", "aktiv": "1"}
    )
    deleted = admin.delete(f"/zaehlertypen/{type_id}")
    assert admin.flashes(admin.soup(created)) == ["Zählertyp „Solar“ wurde angelegt."]
    assert admin.flashes(admin.soup(saved)) == ["Zählertyp „Solar“ wurde gespeichert."]
    assert admin.flashes(admin.soup(deleted)) == ["Zählertyp „Solar“ wurde gelöscht."]
    assert all("flash--success" in el["class"] for el in admin.soup(deleted).select(".flash"))


def test_form_errors_are_rendered_identically_everywhere(admin):
    for slug, res in REGISTRY.items():
        if not res.creatable or slug == "belege":
            continue
        response = admin.submit(f"/{slug}/neu", {})
        assert response.status_code == 422, slug
        soup = admin.soup(response)
        banner = soup.select_one(".flash.flash--error")
        assert banner and "Bitte korrigieren Sie die markierten Felder." in banner.get_text(), slug
        assert soup.select(".form__field--error .form__error"), slug
        for field in soup.select(".form__field--error"):
            control = field.select_one(".form__input")
            assert control is not None and control.get("aria-invalid") == "true", slug


# ------------------------------------------------------------------ tree vs table (spec 13)
@pytest.mark.parametrize("url", TREE_PAGES)
def test_multi_level_data_is_a_collapsible_tree(admin, data, url):
    soup = admin.soup(admin.get(url))
    assert soup.select_one(".tree details > summary.tree__summary"), url
    assert not soup.select("table"), f"{url}: multi-level data must not be a flat table"
    assert soup.select_one(".toolbar").get_text(" ", strip=True) == "Alle aufklappen Alle zuklappen"


@pytest.mark.parametrize(
    "url", ["/eigentuemer/", "/mieter/", "/zaehlertypen/", "/zaehlerstaende/", "/benutzer/", "/kostenarten/"]
)
def test_single_level_data_is_a_table(admin, data, url):
    soup = admin.soup(admin.get(url))
    assert soup.select_one("table.table")
    assert not soup.select(".tree")
    assert soup.select_one("th.table__actions .sr-only").get_text() == "Aktionen"


def test_tree_nodes_share_the_same_row_structure(admin, data):
    for url, soup in pages(admin, TREE_PAGES):
        for node in soup.select(".tree__node"):
            summary = node.select_one(":scope > summary, :scope > .tree__summary")
            parts = [c["class"][0] for c in summary.find_all(recursive=False)]
            assert parts == [
                "tree__toggle",
                "tree__icon",
                "tree__title",
                "tree__meta",
                "tree__badges",
                "tree__actions",
            ], f"{url} {node['id']}: {parts}"
            assert summary.select_one(".tree__icon svg.icon")


# ------------------------------------------------------------------ layout and central stylesheet (spec 11, 17)
def test_every_page_has_the_same_skeleton(admin, data):
    for url in all_pages(admin, data):
        response = admin.get(url)
        assert response.status_code == 200, url
        soup = admin.soup(response)
        assert soup.select_one("header.app__header .app__brand"), url
        assert soup.select_one("nav.app__nav"), url
        assert soup.select_one("main.app__main h1.page-header__title"), url
        assert soup.html["lang"] == "de"
        if url != "/":
            assert soup.select_one("nav.breadcrumb li"), f"{url}: breadcrumb missing"
        active = soup.select(".nav__link--active")
        assert len(active) <= 1, url


def test_navigation_highlights_current_area_and_all_links_work(admin, data):
    soup = admin.soup(admin.get("/wohneinheiten/"))
    assert soup.select_one(".nav__link--active").get_text(strip=True) == "Objekte & Wohneinheiten"
    assert (
        admin.soup(admin.get("/belege/neu")).select_one(".nav__link--active").get_text(strip=True) == "Kostenpositionen"
    )
    groups = [h.get_text() for h in soup.select(".nav__heading")]
    assert groups == ["Stammdaten", "Messwesen", "Kosten", "Abrechnung", "System"]
    for link in soup.select(".nav__link"):
        assert admin.get(link["href"]).status_code == 200, link["href"]


def test_exactly_one_central_stylesheet_and_no_inline_styling(app, admin, data):
    anonymous = UI(app.test_client())
    soups = [(url, admin.soup(admin.get(url))) for url in all_pages(admin, data)]
    soups.append(("/login", anonymous.soup(anonymous.get("/login"))))
    for url, soup in soups:
        sheets = [link["href"] for link in soup.select('link[rel="stylesheet"]')]
        assert sheets == ["/static/css/app.css"], f"{url}: {sheets}"
        assert not soup.select("style"), f"{url}: <style> block"
        assert not soup.select("[style]"), f"{url}: style attribute"
        assert not soup.select("script"), f"{url}: pages work without JavaScript"


def test_templates_and_static_files_contain_no_inline_css_or_external_resources():
    offenders = []
    for path in (ROOT / "app" / "templates").rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"<style|\sstyle\s*=", text):
            offenders.append(f"{path.name}: inline style")
        if re.search(r"https?://(?!www\.w3\.org)", text):
            offenders.append(f"{path.name}: external URL")
    assert not offenders, offenders
    css_files = sorted(p.name for p in (ROOT / "app" / "static" / "css").iterdir())
    assert css_files == ["app.css"]
    css = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "@import" not in css and "url(http" not in css


def test_stylesheet_is_served_and_defines_design_tokens(admin):
    response = admin.get("/static/css/app.css")
    assert response.status_code == 200 and response.mimetype == "text/css"
    css = response.get_data(as_text=True)
    for token in ("--color-primary", "--color-danger", "--space-3", "--font-size-base", "--radius", "--tree-indent"):
        assert re.search(rf"{re.escape(token)}\s*:", css), token


def test_css_uses_tokens_instead_of_raw_colours_outside_root():
    css = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    body = css.split("}", 1)[1]  # everything after the :root block
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", body), "raw colours belong into :root tokens"


def test_every_css_class_used_in_pages_is_defined_in_the_stylesheet(app, admin, data):
    css = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
    used = set()
    anonymous = UI(app.test_client())
    soups = [admin.soup(admin.get(url)) for url in all_pages(admin, data)]
    soups.append(anonymous.soup(anonymous.get("/login")))
    for soup in soups:
        for el in soup.select("[class]"):
            used.update(el["class"])
    ignored = {c for c in used if c.startswith("icon--")}  # icon names, styled through .icon
    undefined = sorted(used - defined - ignored)
    assert not undefined, f"classes without a rule in app.css: {undefined}"


def test_dashboard_is_the_only_page_without_breadcrumb_and_login_has_no_navigation(ui):
    soup = ui.soup(ui.get("/login"))
    assert not soup.select("nav.app__nav, header.app__header")
    assert soup.select_one("main.app__main .card.auth h1")


def test_icon_sprite_covers_all_icons_used(admin, data):
    sprite = admin.get("/static/img/icons.svg").get_data(as_text=True)
    symbols = set(re.findall(r'<symbol id="([^"]+)"', sprite))
    used = set()
    for url in [*TREE_PAGES, *LIST_PAGES, "/"]:
        for use in admin.soup(admin.get(url)).select("svg use"):
            used.add(use["href"].split("#")[1])
    assert used and used <= symbols, used - symbols


# ------------------------------------------------------------------ formats (spec 10, 15)
def test_values_use_german_formats_and_labels(admin, data):
    cost_list = admin.soup(admin.get("/kosten/?expand=all")).get_text(" ", strip=True)
    assert "1.200,00 €" in cost_list and "01.05.2024" in cost_list
    units = admin.soup(admin.get("/wohneinheiten/")).get_text(" ", strip=True)
    assert "65,50 m²" in units and "Wohnung" in units and "WOHNUNG" not in units
    readings = admin.soup(admin.get("/zaehlerstaende/")).get_text(" ", strip=True)
    assert "1.234,5678" in readings and "31.12.2024" in readings and "Manuell" in readings
    assert "Periodengerecht (tagesgenau)" in admin.soup(admin.get("/kosten/neu")).get_text()
    detail = admin.soup(admin.get(f"/kosten/{data['cost']}")).get_text(" ", strip=True)
    assert "Abflussprinzip" in detail and "ABFLUSSPRINZIP" not in detail


def test_forms_prefill_decimals_with_comma_and_dates_in_iso_for_inputs(admin, data):
    soup = admin.soup(admin.get(f"/wohneinheiten/{data['unit']}/bearbeiten"))
    assert soup.select_one("input[name=wohnflaeche_m2]")["value"] == "65,50"
    assert soup.select_one("input[name=verfuegbar_ab]")["type"] == "date"
    assert soup.select_one("input[name=verfuegbar_ab]")["value"] == "2020-01-01"


# ------------------------------------------------------------------ misc
def test_active_property_selector_only_with_multiple_properties(admin, query, data):
    assert not admin.soup(admin.get("/")).select(".app__property")
    from tests.helpers import create_property

    create_property(admin, query, data["owner"], bezeichnung="Nebenstraße 3")
    soup = admin.soup(admin.get("/"))
    assert soup.select_one(".app__property select[name=property_id]")
    admin.post("/objekt-waehlen", {"property_id": data["property"], "next": "/zaehler/"}, form_url="/")
    tree = admin.soup(admin.get("/zaehler/"))
    assert [n["id"] for n in tree.select(".tree > details")] == [f"objekte-{data['property']}"], (
        "tree is filtered to the active property"
    )
    admin.post("/objekt-waehlen", {"property_id": "", "next": "/zaehler/"}, form_url="/")
    assert len(admin.soup(admin.get("/zaehler/")).select(".tree > details")) == 2
