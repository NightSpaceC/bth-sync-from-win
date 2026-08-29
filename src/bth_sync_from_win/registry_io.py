from pathlib import Path
from typing import Any

from .errors import RegistryError
from .models import RegistryNode, RegistryValue

try:
    from Registry.Registry import Registry
except Exception as exc:
    Registry = None
    _REGISTRY_IMPORT_ERROR = exc
else:
    _REGISTRY_IMPORT_ERROR = None


def load_system_hive(path: Path) -> Any:
    if Registry is None:
        raise RegistryError(
            "python-registry (Registry.Registry) is required but could not be imported"
        ) from _REGISTRY_IMPORT_ERROR

    try:
        return Registry(str(path))
    except Exception as exc:
        raise RegistryError(f"Failed to open Windows SYSTEM hive {path}: {exc}") from exc


def _coerce_int(value: Any) -> int:
    if isinstance(value, int):
        return value

    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return int.from_bytes(raw, "little") if raw else 0

    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise RegistryError(f"Cannot interpret {value!r} as integer") from exc

    raise RegistryError(f"Cannot interpret {type(value).__name__} as integer")


def get_current_control_set(registry: Any) -> Any:
    try:
        select_key = registry.open("Select")
        current_value = select_key.value("Current").value()
        current = _coerce_int(current_value)
        return registry.open(f"ControlSet{current:03d}")
    except RegistryError:
        raise
    except Exception as exc:
        raise RegistryError("Could not determine current control set from Select\\Current") from exc


def _subkey(key: Any, name: str) -> Any:
    try:
        return key.subkey(name)
    except Exception as exc:
        raise RegistryError(f"Missing required registry key: {name}") from exc


def get_bluetooth_parameters(registry: Any) -> Any:
    try:
        control_set = get_current_control_set(registry)
        services = _subkey(control_set, "Services")
        bthport = _subkey(services, "BTHPORT")
        return _subkey(bthport, "Parameters")
    except RegistryError:
        raise
    except Exception as exc:
        raise RegistryError("Could not open Services\\BTHPORT\\Parameters in current control set") from exc


def read_node(key: Any) -> RegistryNode:
    node = RegistryNode()

    try:
        for subkey in key.subkeys():
            raw_name = subkey.name()
            name = "" if raw_name is None else str(raw_name)
            node.subkeys[name] = read_node(subkey)

        for value in key.values():
            raw_name = value.name()
            name = "" if raw_name is None else str(raw_name)
            data = value.value()

            try:
                value_type = int(value.value_type())
            except Exception:
                value_type = -1

            node.values[name] = RegistryValue(value=data, value_type=value_type)
    except RegistryError:
        raise
    except Exception as exc:
        raise RegistryError(f"Failed to read registry key: {exc}") from exc

    return node


def get_devices_node(parameters: Any) -> RegistryNode:
    try:
        return read_node(_subkey(parameters, "Devices"))
    except RegistryError:
        raise
    except Exception as exc:
        raise RegistryError("Failed to read Bluetooth Devices key") from exc


def get_keys_node(parameters: Any) -> RegistryNode:
    try:
        return read_node(_subkey(parameters, "Keys"))
    except RegistryError:
        raise
    except Exception as exc:
        raise RegistryError("Failed to read Bluetooth Keys key") from exc
