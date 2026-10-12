from datetime import date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import (
    AllocationKey,
    Cost,
    CostReceipt,
    CostType,
    CostYearShare,
    Meter,
    MeterReading,
    MeterType,
    Owner,
    Property,
    PropertyCostTypeConfig,
    Statement,
    StatementItem,
    StatementItemCostType,
    TenancyAgreement,
    Tenant,
    Unit,
    User,
)


@pytest.fixture
def unit(session):
    owner = Owner(name="Muster KG", legal_form="KG", street="Weg 1", postal_code="12345", city="Stadt")
    prop = Property(
        owner=owner,
        name="Hauptstraße 12",
        street="Hauptstraße",
        house_number="12",
        postal_code="12345",
        city="Stadt",
    )
    unit = Unit(
        property=prop,
        name="EG links",
        unit_type="WOHNUNG",
        living_area_m2=65.5,
        available_from=date(2020, 1, 1),
    )
    session.add(unit)
    session.commit()
    return unit


@pytest.fixture
def tenant(session):
    tenant = Tenant(first_name="Erika", last_name="Mustermann")
    session.add(tenant)
    session.commit()
    return tenant


def test_all_specified_tables_exist(app):
    expected = {
        "eigentuemer",
        "objekt",
        "wohneinheit",
        "mieter",
        "mietverhaeltnis",
        "kostenart",
        "verteilerschluessel",
        "zaehlertyp",
        "objekt_kostenart_konfiguration",
        "zaehler",
        "zaehlerstand",
        "kosten",
        "kosten_jahresanteil",
        "kosten_beleg",
        "abrechnung",
        "abrechnungsposition",
        "abrechnungsposition_kostenart",
        "benutzer",
    }
    actual = set(sa.inspect(app.test_engine).get_table_names())
    assert expected <= actual


def test_cost_type_seed(session):
    types = session.query(CostType).order_by(CostType.id).all()
    assert len(types) == 17
    assert types[3].name == "Kosten der Heizungsanlage"
    assert types[3].betrkv_number == "2 Nr. 4"
    consumption = {t.id for t in types if t.consumption_based_possible}
    assert consumption == {2, 4, 5, 6, 11}


def test_allocation_key_seed(session):
    keys = {k.id: k.code for k in session.query(AllocationKey)}
    assert keys == {
        1: "WOHNFLAECHE",
        2: "PERSONENANZAHL",
        3: "ANZAHL_EINHEITEN",
        4: "MITEIGENTUMSANTEILE",
        5: "VERBRAUCH",
    }


def test_meter_type_seed(session):
    names = {m.name for m in session.query(MeterType) if m.active}
    assert {"Heizung", "Warmwasser", "Kaltwasser", "Allgemeinstrom"} <= names


def test_unit_name_unique_per_property(session, unit):
    session.add(
        Unit(
            property_id=unit.property_id,
            name=unit.name,
            unit_type="GEWERBE",
            living_area_m2=20,
            available_from=date(2020, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_unit_type_enum_rejects_invalid(session, unit):
    session.add(
        Unit(
            property_id=unit.property_id,
            name="X",
            unit_type="GARAGE",
            living_area_m2=20,
            available_from=date(2020, 1, 1),
        )
    )
    with pytest.raises(Exception):  # noqa: B017
        session.commit()


def test_tenancy_defaults_and_timestamps(session, unit, tenant):
    tenancy = TenancyAgreement(unit=unit, tenant=tenant, move_in_date=date(2024, 3, 15))
    session.add(tenancy)
    session.commit()
    session.refresh(tenancy)
    assert tenancy.occupants == 1
    assert tenancy.move_out_date is None
    assert isinstance(tenancy.created_at, datetime)
    assert isinstance(tenancy.updated_at, datetime)


def test_tenancy_move_out_before_move_in_rejected(session, unit, tenant):
    session.add(
        TenancyAgreement(
            unit=unit,
            tenant=tenant,
            move_in_date=date(2024, 3, 15),
            move_out_date=date(2024, 3, 14),
        )
    )
    with pytest.raises(DBAPIError):  # MariaDB reports CHECK violations as OperationalError 4025
        session.commit()


def test_cost_service_period_check(session, unit):
    session.add(
        Cost(
            property_id=unit.property_id,
            cost_type_id=1,
            total_amount=Decimal("100.00"),
            invoice_date=date(2024, 5, 1),
            service_period_from=date(2024, 1, 31),
            service_period_to=date(2024, 1, 1),
            accrual_method="ABFLUSSPRINZIP",
        )
    )
    with pytest.raises(DBAPIError):  # MariaDB reports CHECK violations as OperationalError 4025
        session.commit()


def test_meter_requires_unit_or_property(session):
    session.add(Meter(meter_type_id=1, external_device_id="DEV-1", installed_on=date(2020, 1, 1)))
    with pytest.raises(DBAPIError):  # MariaDB reports CHECK violations as OperationalError 4025
        session.commit()


def test_meter_reading_unique_per_day(session, unit):
    meter = Meter(
        meter_type_id=1,
        unit_id=unit.id,
        external_device_id="DEV-2",
        installed_on=date(2020, 1, 1),
    )
    session.add(meter)
    session.commit()
    session.add(
        MeterReading(
            meter_id=meter.id,
            reading_date=date(2024, 12, 31),
            value=Decimal("1234.5678"),
            source="SCHNITTSTELLE",
        )
    )
    session.commit()
    session.add(
        MeterReading(
            meter_id=meter.id,
            reading_date=date(2024, 12, 31),
            value=Decimal("1300.0000"),
            source="MANUELL",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_property_cost_type_config_unique(session, unit):
    kwargs = {
        "property_id": unit.property_id,
        "cost_type_id": 4,
        "allocation_key_id": 1,
        "consumption_based": True,
        "base_cost_percent": Decimal("30.00"),
        "meter_type_id": 1,
        "valid_from": date(2024, 1, 1),
    }
    session.add(PropertyCostTypeConfig(**kwargs))
    session.commit()
    session.add(PropertyCostTypeConfig(**kwargs))
    with pytest.raises(IntegrityError):
        session.commit()


def test_statement_unique_per_property_year_and_default_status(session, unit):
    statement = Statement(property_id=unit.property_id, billing_year=2024)
    session.add(statement)
    session.commit()
    session.refresh(statement)
    assert statement.status == "ENTWURF"
    session.add(Statement(property_id=unit.property_id, billing_year=2024))
    with pytest.raises(IntegrityError):
        session.commit()


def test_full_statement_chain(session, unit, tenant):
    tenancy = TenancyAgreement(unit=unit, tenant=tenant, move_in_date=date(2024, 3, 15), occupants=2)
    session.add(tenancy)
    cost = Cost(
        property_id=unit.property_id,
        cost_type_id=1,
        total_amount=Decimal("1200.00"),
        invoice_date=date(2024, 5, 1),
        service_period_from=date(2024, 1, 1),
        service_period_to=date(2024, 12, 31),
        accrual_method="ABFLUSSPRINZIP",
    )
    cost.year_shares.append(
        CostYearShare(
            billing_year=2024,
            share_amount=Decimal("1200.00"),
            calculation_basis="100 % im Jahr des Rechnungsdatums",
        )
    )
    cost.receipts.append(
        CostReceipt(
            file_name="rechnung.pdf",
            storage_reference="2024/rechnung.pdf",
            mime_type="application/pdf",
        )
    )
    statement = Statement(property_id=unit.property_id, billing_year=2024)
    item = StatementItem(
        statement=statement,
        tenancy=tenancy,
        period_from=date(2024, 3, 15),
        period_to=date(2024, 12, 31),
        usage_days=292,
        total_cost_share=Decimal("500.00"),
        balance=Decimal("100.00"),
        delivery_street="Weg 2",
        delivery_postal_code="54321",
        delivery_city="Anderswo",
    )
    item.cost_type_lines.append(
        StatementItemCostType(
            cost_type_id=1,
            allocation_key_id=1,
            amount=Decimal("500.00"),
            share_percent=Decimal("12.3456"),
        )
    )
    session.add_all([cost, statement, item])
    session.commit()
    session.refresh(item)
    assert item.prepayment_received == 0
    assert item.cost_type_lines[0].base_cost_amount is None
    assert session.get(Cost, cost.id).receipts[0].uploaded_at is not None
    assert session.query(Property).count() == 1


def test_statement_item_unique_per_tenancy(session, unit, tenant):
    tenancy = TenancyAgreement(unit=unit, tenant=tenant, move_in_date=date(2024, 1, 1))
    session.add(tenancy)
    statement = Statement(property_id=unit.property_id, billing_year=2024)
    session.add(statement)
    session.commit()
    kwargs = {
        "statement_id": statement.id,
        "tenancy_id": tenancy.id,
        "period_from": date(2024, 1, 1),
        "period_to": date(2024, 12, 31),
        "usage_days": 366,
        "total_cost_share": 1,
        "balance": 1,
        "delivery_street": "a",
        "delivery_postal_code": "1",
        "delivery_city": "c",
    }
    session.add(StatementItem(**kwargs))
    session.commit()
    session.add(StatementItem(**kwargs))
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_password_hashing_and_unique_username(session):
    user = User(username="admin", email="admin@example.com")
    user.set_password("geheim")
    session.add(user)
    session.commit()
    assert user.password_hash != "geheim"
    assert user.check_password("geheim")
    assert not user.check_password("falsch")
    assert user.is_active
    other = User(username="admin", email="other@example.com", password_hash="x")
    session.add(other)
    with pytest.raises(IntegrityError):
        session.commit()


def test_foreign_key_restrict(session, unit):
    with pytest.raises(IntegrityError):
        session.execute(Property.__table__.delete())
        session.commit()
