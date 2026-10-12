"""Importing this package registers every table on ``db.metadata``."""

from app.models.allocation_key import AllocationKey
from app.models.cost import Cost
from app.models.cost_receipt import CostReceipt
from app.models.cost_type import CostType
from app.models.cost_year_share import CostYearShare
from app.models.meter import Meter
from app.models.meter_reading import MeterReading
from app.models.meter_type import MeterType
from app.models.owner import Owner
from app.models.property import Property
from app.models.property_cost_type_config import PropertyCostTypeConfig
from app.models.statement import Statement
from app.models.statement_item import StatementItem
from app.models.statement_item_cost_type import StatementItemCostType
from app.models.tenancy_agreement import TenancyAgreement
from app.models.tenant import Tenant
from app.models.unit import Unit
from app.models.user import User

__all__ = [
    "AllocationKey",
    "Cost",
    "CostReceipt",
    "CostType",
    "CostYearShare",
    "Meter",
    "MeterReading",
    "MeterType",
    "Owner",
    "Property",
    "PropertyCostTypeConfig",
    "Statement",
    "StatementItem",
    "StatementItemCostType",
    "TenancyAgreement",
    "Tenant",
    "Unit",
    "User",
]
