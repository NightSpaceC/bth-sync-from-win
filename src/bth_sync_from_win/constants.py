from pathlib import Path

DEFAULT_BLUEZ_ROOT = Path("/var/lib/bluetooth")
WINDOWS_SYSTEM_HIVE_RELATIVE_PATH = Path("Windows") / "System32" / "config" / "SYSTEM"

INFO_FILENAME = "info"
ATTRIBUTES_FILENAME = "attributes"

CENTRAL_IRK = "CentralIRK"

TRUSTED = "true"
LINK_KEY_TYPE = "4"
PIN_LENGTH = "0"
LTK_AUTHENTICATED = "2"

SUPPORTED_TECHNOLOGIES_DUAL = "BR/EDR;LE"
