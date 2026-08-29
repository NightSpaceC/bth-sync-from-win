from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def _decode_text(data: bytes) -> str:
    """
    Decode Windows registry text-like binary data.

    Bluetooth device names may be stored as UTF-8 or UTF-16LE with NUL
    terminators. This helper tries to do something sensible for both.
    """
    if data.endswith(b"\x00\x00"):
        candidate = data[:-2]
    elif data.endswith(b"\x00"):
        candidate = data[:-1]
    else:
        candidate = data

    if not candidate:
        return ""

    # If the payload contains NUL bytes and has even length, UTF-16LE is likely.
    if len(candidate) % 2 == 0 and b"\x00" in candidate:
        try:
            text = candidate.decode("utf-16-le")
            if "\x00" not in text:
                return text
        except UnicodeDecodeError:
            pass

    try:
        return candidate.decode("utf-8").replace("\x00", "")
    except UnicodeDecodeError:
        pass

    try:
        return candidate.decode("utf-16-le").replace("\x00", "")
    except UnicodeDecodeError:
        pass

    return candidate.decode("utf-8", errors="replace").replace("\x00", "")


def _to_int(value: Any) -> int:
    if isinstance(value, int):
        return value

    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return int.from_bytes(raw, "little") if raw else 0

    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"cannot convert string {value!r} to int") from exc

    raise ValueError(f"cannot convert {type(value).__name__} to int")


def _to_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value

    if isinstance(value, bytearray):
        return bytes(value)

    if isinstance(value, str):
        try:
            return bytes.fromhex(value.strip())
        except ValueError:
            return value.encode("utf-8")

    if isinstance(value, int):
        if value == 0:
            return b"\x00"
        length = (value.bit_length() + 7) // 8
        return value.to_bytes(length, "little", signed=value < 0)

    raise ValueError(f"cannot convert {type(value).__name__} to bytes")


@dataclass
class RegistryValue:
    value: Any
    value_type: int

    def as_int(self) -> int:
        return _to_int(self.value)

    def as_bytes(self) -> bytes:
        return _to_bytes(self.value)

    def as_text(self) -> str:
        if isinstance(self.value, str):
            return self.value.rstrip("\x00").strip()

        if isinstance(self.value, (bytes, bytearray)):
            return _decode_text(bytes(self.value)).strip()

        return str(self.value)


@dataclass(frozen=True)
class BluetoothAddress:
    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != 6:
            raise ValueError("Bluetooth address must be 6 bytes")

    @classmethod
    def parse(cls, text: str) -> "BluetoothAddress":
        cleaned = (
            text.strip()
            .replace("{", "")
            .replace("}", "")
            .replace(":", "")
            .replace("-", "")
        )
        try:
            raw = bytes.fromhex(cleaned)
        except ValueError as exc:
            raise ValueError(f"invalid Bluetooth address {text!r}") from exc
        return cls(raw)

    @property
    def hex(self) -> str:
        return self.raw.hex()

    @property
    def bluez(self) -> str:
        return ":".join(f"{byte:02X}" for byte in self.raw)

    @property
    def is_static_random(self) -> bool:
        return (self.raw[0] >> 6) == 0b11

    def __str__(self) -> str:
        return self.bluez


@dataclass
class RegistryNode:
    subkeys: Dict[str, "RegistryNode"] = field(default_factory=dict)
    values: Dict[str, RegistryValue] = field(default_factory=dict)

    def child(self, name: str) -> Optional["RegistryNode"]:
        if name in self.subkeys:
            return self.subkeys[name]

        lowered = name.lower()
        for key, node in self.subkeys.items():
            if key.lower() == lowered:
                return node
        return None

    def value(self, name: str) -> Optional[RegistryValue]:
        if name in self.values:
            return self.values[name]

        lowered = name.lower()
        for key, value in self.values.items():
            if key.lower() == lowered:
                return value
        return None


@dataclass(frozen=True)
class PairRecord:
    local: BluetoothAddress
    remote: BluetoothAddress
    sections: Dict[str, Dict[str, str]]
