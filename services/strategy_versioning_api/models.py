"""Pydantic models for strategy versioning."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class VersionCreate(BaseModel):
    """Captured automatically when a strategy spec is updated."""

    strategy_id: str = Field(..., description="Strategy spec UUID")
    parameters: Dict[str, Any] = Field(..., description="Full parameter snapshot")
    indicators: Dict[str, Any] = Field(..., description="Full indicator snapshot")
    entry_conditions: Dict[str, Any] = Field(..., description="Full entry conditions snapshot")
    exit_conditions: Dict[str, Any] = Field(..., description="Full exit conditions snapshot")
    changed_by: str = Field(..., description="Who made the change")
    change_reason: Optional[str] = Field(None, description="Why the change was made")


class RollbackRequest(BaseModel):
    changed_by: str = Field(..., description="Who is requesting the rollback")
    change_reason: Optional[str] = Field(None, description="Reason for rollback")
