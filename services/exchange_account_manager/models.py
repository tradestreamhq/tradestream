"""Pydantic models for exchange account management."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExchangeAccountCreate(BaseModel):
    exchange: str = Field(..., description="Exchange name, e.g. binance, coinbase")
    label: str = Field(..., description="User-friendly label for this account")
    api_key: str = Field(..., min_length=1, description="Exchange API key")
    api_secret: str = Field(..., min_length=1, description="Exchange API secret")
    permissions: List[str] = Field(
        default_factory=lambda: ["read"],
        description="API key permissions, e.g. read, trade, withdraw",
    )


class ExchangeAccountUpdate(BaseModel):
    label: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    permissions: Optional[List[str]] = None


class ExchangeAccountResponse(BaseModel):
    id: str
    exchange: str
    label: str
    permissions: List[str]
    is_active: bool
    created_at: str
    updated_at: str


class AccountBalance(BaseModel):
    account_id: str
    exchange: str
    label: str
    balances: Dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of asset symbol to available balance",
    )
    total_usd: float = Field(0.0, description="Estimated total balance in USD")


class UnifiedPortfolio(BaseModel):
    accounts: List[AccountBalance]
    total_usd: float = 0.0
    asset_totals: Dict[str, float] = Field(
        default_factory=dict,
        description="Aggregate balance per asset across all accounts",
    )
