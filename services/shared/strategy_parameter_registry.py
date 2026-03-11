"""Shared strategy parameter registry for decoupled protobuf type resolution.

Instead of each service maintaining its own hardcoded mapping of protobuf
type URLs to parameter classes, this registry auto-discovers all parameter
message types from strategies_pb2 using protobuf reflection.

This fixes audit finding C3: cross-repo model invariant coupling. Adding a
new strategy parameter type to strategies.proto automatically makes it
available to all services—no manual mapping updates required.
"""

import hashlib
import logging
from typing import Dict, Optional, Type

from google.protobuf import descriptor_pool, symbol_database
from google.protobuf.message import Message

from protos import strategies_pb2

logger = logging.getLogger(__name__)

# Schema fingerprint computed from the strategies proto descriptor.
# Services can compare this at startup to detect mismatched proto versions.
_PROTO_PACKAGE = "strategies"
_TYPE_URL_PREFIX = "type.googleapis.com"


def _build_parameter_registry() -> Dict[str, Type[Message]]:
    """Auto-discover all parameter message types from strategies_pb2.

    Scans the strategies_pb2 module for any class whose name ends with
    'Parameters' and is a protobuf Message subclass. Returns a mapping
    from fully-qualified type URL to the message class.
    """
    registry: Dict[str, Type[Message]] = {}

    for name in dir(strategies_pb2):
        if not name.endswith("Parameters"):
            continue
        cls = getattr(strategies_pb2, name)
        if not isinstance(cls, type) or not issubclass(cls, Message):
            continue
        type_url = f"{_TYPE_URL_PREFIX}/{_PROTO_PACKAGE}.{name}"
        registry[type_url] = cls

    return registry


# Module-level singleton—built once on import.
PARAMETER_REGISTRY: Dict[str, Type[Message]] = _build_parameter_registry()


def get_parameter_class(type_url: str) -> Optional[Type[Message]]:
    """Look up the parameter message class for a given protobuf type URL.

    Returns None if the type URL is not recognized.
    """
    return PARAMETER_REGISTRY.get(type_url)


def unpack_strategy_parameters(strategy: strategies_pb2.Strategy) -> dict:
    """Unpack a Strategy's google.protobuf.Any parameters into a plain dict.

    Returns an empty dict if the strategy has no parameters or the
    parameter type is unrecognized.
    """
    if not strategy.HasField("parameters"):
        return {}

    any_params = strategy.parameters
    type_url = any_params.type_url
    param_cls = get_parameter_class(type_url)

    if param_cls is None:
        logger.warning("Unknown strategy parameter type: %s", type_url)
        return {}

    param_msg = param_cls()
    any_params.Unpack(param_msg)

    result = {}
    for field in param_msg.DESCRIPTOR.fields:
        value = getattr(param_msg, field.name)
        if field.type == field.TYPE_ENUM:
            result[field.name] = field.enum_type.values_by_number[value].name
        else:
            result[field.name] = value
    return result


def compute_schema_fingerprint() -> str:
    """Compute a fingerprint of the current strategies proto schema.

    Services can log or exchange this fingerprint to detect when they are
    running against different proto versions.
    """
    descriptor = strategies_pb2.Strategy.DESCRIPTOR.file
    fields_repr = []
    for msg in descriptor.message_types_by_name.values():
        parts = [msg.full_name]
        for field in msg.fields:
            parts.append(f"{field.name}:{field.number}:{field.type}")
        fields_repr.append("|".join(parts))
    fields_repr.sort()
    content = "\n".join(fields_repr)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


SCHEMA_FINGERPRINT = compute_schema_fingerprint()
