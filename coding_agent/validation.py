from __future__ import annotations

from copy import deepcopy
from typing import Any


class SchemaValidationError(ValueError):
    pass


def _type_name(value: Any) -> str:
    return type(value).__name__


def validate_json_schema(value: Any, schema: dict[str, Any], *, path: str = "$") -> Any:
    schema_type = schema.get("type")

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: expected one of {schema['enum']!r}, got {value!r}")

    if schema_type == "object":
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path}: expected object, got {_type_name(value)}")

        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        additional = schema.get("additionalProperties", True)
        normalized: dict[str, Any] = {}

        if additional is False:
            unknown_keys = sorted(set(value) - set(properties))
            if unknown_keys:
                raise SchemaValidationError(f"{path}: unexpected properties {unknown_keys!r}")

        for key, prop_schema in properties.items():
            if key in value:
                normalized[key] = validate_json_schema(value[key], prop_schema, path=f"{path}.{key}")
            elif "default" in prop_schema:
                normalized[key] = deepcopy(prop_schema["default"])
            elif key in required:
                raise SchemaValidationError(f"{path}.{key}: missing required property")

        if additional not in (True, False):
            raise SchemaValidationError(f"{path}: unsupported additionalProperties schema")

        if additional is True:
            for key, item in value.items():
                if key not in normalized:
                    normalized[key] = item

        return normalized

    if schema_type == "array":
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path}: expected array, got {_type_name(value)}")

        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(value) < int(min_items):
            raise SchemaValidationError(f"{path}: expected at least {min_items} items")
        if max_items is not None and len(value) > int(max_items):
            raise SchemaValidationError(f"{path}: expected at most {max_items} items")

        item_schema = schema.get("items")
        if not item_schema:
            return list(value)
        return [validate_json_schema(item, item_schema, path=f"{path}[{index}]") for index, item in enumerate(value)]

    if schema_type == "string":
        if not isinstance(value, str):
            raise SchemaValidationError(f"{path}: expected string, got {_type_name(value)}")
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if min_length is not None and len(value) < int(min_length):
            raise SchemaValidationError(f"{path}: expected at least {min_length} characters")
        if max_length is not None and len(value) > int(max_length):
            raise SchemaValidationError(f"{path}: expected at most {max_length} characters")
        return value

    if schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected integer, got {_type_name(value)}")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < int(minimum):
            raise SchemaValidationError(f"{path}: expected value >= {minimum}")
        if maximum is not None and value > int(maximum):
            raise SchemaValidationError(f"{path}: expected value <= {maximum}")
        return value

    if schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected number, got {_type_name(value)}")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < float(minimum):
            raise SchemaValidationError(f"{path}: expected value >= {minimum}")
        if maximum is not None and value > float(maximum):
            raise SchemaValidationError(f"{path}: expected value <= {maximum}")
        return value

    if schema_type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"{path}: expected boolean, got {_type_name(value)}")
        return value

    if schema_type is None:
        return value

    raise SchemaValidationError(f"{path}: unsupported schema type {schema_type!r}")
