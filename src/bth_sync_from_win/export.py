from dataclasses import dataclass, field
from itertools import chain
from typing import Dict, List, Set, Tuple

from .constants import (
    CENTRAL_IRK,
    LINK_KEY_TYPE,
    LTK_AUTHENTICATED,
    PIN_LENGTH,
    SUPPORTED_TECHNOLOGIES_DUAL,
    TRUSTED,
)
from .models import BluetoothAddress, PairRecord, RegistryNode


class _SkipPair(Exception):
    """Internal exception used to skip one pair without aborting everything."""


@dataclass
class ExportReport:
    records: List[PairRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _looks_like_address(text: str) -> bool:
    cleaned = text.strip().replace(":", "").replace("-", "")
    if len(cleaned) != 12:
        return False
    return all(ch in "0123456789abcdefABCDEF" for ch in cleaned)


def export_pairs(devices: RegistryNode, keys: RegistryNode) -> ExportReport:
    report = ExportReport()
    pairs: Set[Tuple[BluetoothAddress, BluetoothAddress]] = set()

    for src_text, src_node in keys.subkeys.items():
        if not _looks_like_address(src_text):
            report.warning(
                f"Ignoring unexpected subkey {src_text!r} under Keys; "
                "expected a local Bluetooth adapter address."
            )
            continue

        try:
            local = BluetoothAddress.parse(src_text)
        except ValueError as exc:
            report.warning(f"Ignoring invalid local adapter address {src_text!r}: {exc}")
            continue

        for dst_text in chain(src_node.subkeys.keys(), src_node.values.keys()):
            if dst_text == CENTRAL_IRK:
                continue

            if not _looks_like_address(dst_text):
                continue

            try:
                remote = BluetoothAddress.parse(dst_text)
            except ValueError as exc:
                report.warning(
                    f"Ignoring invalid remote address {dst_text!r} under {local}: {exc}"
                )
                continue

            if remote == local:
                report.warning(f"Ignoring self-pairing {local}.")
                continue

            pairs.add((local, remote))

    for local, remote in sorted(pairs, key=lambda item: (item[0].hex, item[1].hex)):
        try:
            record = _build_record(devices, keys, local, remote, report)
        except _SkipPair as exc:
            report.warning(f"Skipping pair {local} -> {remote}: {exc}")
            continue

        report.records.append(record)

    return report


def _build_record(
    devices: RegistryNode,
    keys: RegistryNode,
    local: BluetoothAddress,
    remote: BluetoothAddress,
    report: ExportReport,
) -> PairRecord:
    local_node = keys.child(local.hex)
    if local_node is None:
        raise _SkipPair("local adapter key is missing")

    remote_node = devices.child(remote.hex)
    general: Dict[str, str] = {}

    if remote_node is None:
        report.warning(f"No Devices entry for {remote}; using address as Name.")
        name = remote.bluez
    else:
        name_value = remote_node.value("Name")
        if name_value is None:
            report.warning(f"Missing Name for {remote}; using address as Name.")
            name = remote.bluez
        else:
            try:
                name = name_value.as_text().strip()
            except ValueError as exc:
                report.warning(f"Could not decode Name for {remote}: {exc}")
                name = remote.bluez

            if not name:
                report.warning(f"Empty Name for {remote}; using address as Name.")
                name = remote.bluez

        # Keep the value single-line and tidy.
        name = " ".join(name.split())

        cod_value = remote_node.value("COD")
        if cod_value is not None:
            try:
                general["Class"] = f"0x{cod_value.as_int():06x}"
            except ValueError as exc:
                report.warning(f"Invalid COD for {remote}: {exc}")

        appearance_value = remote_node.value("LEAppearance")
        if appearance_value is not None:
            try:
                general["Appearance"] = f"0x{appearance_value.as_int():04x}"
            except ValueError as exc:
                report.warning(f"Invalid LEAppearance for {remote}: {exc}")

    general["Name"] = name
    general["Trusted"] = TRUSTED
    general["SupportedTechnologies"] = SUPPORTED_TECHNOLOGIES_DUAL
    general["AddressType"] = "static" if remote.is_static_random else "public"

    sections: Dict[str, Dict[str, str]] = {
        "General": general,
    }

    # BR/EDR link key, if present.
    link_value = local_node.value(remote.hex)
    if link_value is not None:
        try:
            link_key = link_value.as_bytes()
            if len(link_key) != 16:
                raise ValueError("expected 16-byte link key")

            sections["LinkKey"] = {
                "Key": link_key.hex().upper(),
                "Type": LINK_KEY_TYPE,
                "PINLength": PIN_LENGTH,
            }
        except ValueError as exc:
            report.warning(f"Invalid BR/EDR link key for {local} -> {remote}: {exc}")

    # LE keys, if present.
    le_node = local_node.child(remote.hex)
    if le_node is not None:
        irk_value = le_node.value("IRK")
        if irk_value is not None:
            try:
                irk = irk_value.as_bytes()
                if len(irk) != 16:
                    raise ValueError("expected 16-byte IRK")

                sections["IdentityResolvingKey"] = {
                    "Key": irk.hex().upper(),
                }
            except ValueError as exc:
                report.warning(f"Invalid IRK for {local} -> {remote}: {exc}")

        ltk_value = le_node.value("LTK")
        key_length_value = le_node.value("KeyLength")
        ediv_value = le_node.value("EDIV")
        erand_value = le_node.value("ERand")

        present = (
            ltk_value is not None,
            key_length_value is not None,
            ediv_value is not None,
            erand_value is not None,
        )

        if all(present):
            try:
                ltk = ltk_value.as_bytes()
                if len(ltk) != 16:
                    raise ValueError("expected 16-byte LTK")

                ltk_section = {
                    "Key": ltk.hex().upper(),
                    "Authenticated": LTK_AUTHENTICATED,
                    "EncSize": str(key_length_value.as_int()),
                    "EDiv": str(ediv_value.as_int()),
                    "Rand": str(erand_value.as_int()),
                }

                # Preserve the original implementation's compatibility behavior.
                sections["SlaveLongTermKey"] = dict(ltk_section)
                sections["PeripheralLongTermKey"] = dict(ltk_section)
                sections["LongTermKey"] = dict(ltk_section)
            except ValueError as exc:
                report.warning(f"Invalid LTK data for {local} -> {remote}: {exc}")
        elif any(present):
            report.warning(
                f"Incomplete LTK information for {local} -> {remote}; omitted LTK sections."
            )

    if len(sections) == 1:
        raise _SkipPair("no usable link key or LE key material was found")

    return PairRecord(local=local, remote=remote, sections=sections)
