"""Core types and exceptions for pairtrading-data."""

from ptdata.core.constants import (
    DEFAULT_CACHE_EXPIRY_DAYS,
    DEFAULT_EXTREME_MOVE_THRESHOLD,
    DEFAULT_MAX_CONSECUTIVE_MISSING,
)
from ptdata.core.exceptions import (
    DataQualityError,
    InsufficientDataError,
    LookAheadBiasError,
    PTDataError,
    SurvivorshipBiasError,
)
from ptdata.core.types import CorporateAction, CorporateActionType, PriceBar

__all__ = [
    # Types
    "PriceBar",
    "CorporateAction",
    "CorporateActionType",
    # Exceptions
    "PTDataError",
    "LookAheadBiasError",
    "SurvivorshipBiasError",
    "InsufficientDataError",
    "DataQualityError",
    # Constants
    "DEFAULT_CACHE_EXPIRY_DAYS",
    "DEFAULT_MAX_CONSECUTIVE_MISSING",
    "DEFAULT_EXTREME_MOVE_THRESHOLD",
]
