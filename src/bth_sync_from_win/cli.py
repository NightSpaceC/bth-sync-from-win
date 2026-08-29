import argparse
from pathlib import Path
from typing import List, Optional

from . import __version__, bluez, export, registry_io, ui
from .constants import DEFAULT_BLUEZ_ROOT, WINDOWS_SYSTEM_HIVE_RELATIVE_PATH
from .errors import BluetoothSyncError, RegistryError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bluetooth-registry-sync",
        description=(
            "Synchronize Bluetooth pairing records from a mounted Windows SYSTEM "
            "registry hive into the local BlueZ state directory."
        ),
    )

    parser.add_argument(
        "windows_root",
        metavar="WINDOWS_ROOT",
        help="Mounted Windows directory, or direct path to a SYSTEM hive file.",
    )
    parser.add_argument(
        "--bluez-root",
        type=Path,
        default=DEFAULT_BLUEZ_ROOT,
        help=f"BlueZ state directory (default: {DEFAULT_BLUEZ_ROOT})",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help='Assume "yes" for all confirmation prompts.',
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying any files.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def _resolve_system_hive(windows_root: Path) -> Path:
    candidate = windows_root / WINDOWS_SYSTEM_HIVE_RELATIVE_PATH

    if candidate.is_file():
        return candidate

    if windows_root.is_file():
        return windows_root

    raise RegistryError(
        f"Could not find a SYSTEM hive at {candidate}, "
        f"and {windows_root} is not a hive file"
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    windows_root = Path(args.windows_root).expanduser().resolve()
    bluez_root = Path(args.bluez_root).expanduser().resolve()

    try:
        system_hive = _resolve_system_hive(windows_root)
    except RegistryError as exc:
        ui.error(str(exc))
        return 1

    ui.info(f"Reading SYSTEM hive: {system_hive}")

    try:
        registry = registry_io.load_system_hive(system_hive)
        parameters = registry_io.get_bluetooth_parameters(registry)
        devices = registry_io.get_devices_node(parameters)
        keys = registry_io.get_keys_node(parameters)
    except RegistryError as exc:
        ui.error(str(exc))
        return 1

    report = export.export_pairs(devices, keys)

    for message in report.warnings:
        ui.warning(message)

    if not report.records:
        ui.warning("No usable Bluetooth pairing records were found in the registry.")
        return 0

    if not bluez_root.is_dir():
        ui.error(f"BlueZ state directory {bluez_root} does not exist.")
        return 1

    ui.info(f"Found {len(report.records)} pairing record(s).")

    if args.dry_run:
        ui.info("Dry-run mode enabled; no files will be modified.")

    updated = 0
    unchanged = 0
    skipped = 0
    failed = 0

    for record in report.records:
        label = f"{record.local} -> {record.remote}"
        adapter_dir = bluez_root / record.local.bluez

        if not adapter_dir.is_dir():
            ui.warning(
                f"Skipping {label}: adapter directory {adapter_dir} does not exist."
            )
            skipped += 1
            continue

        try:
            changed = bluez.process_pair(
                record,
                bluez_root,
                assume_yes=args.yes,
                dry_run=args.dry_run,
            )

            if args.dry_run:
                skipped += 1
            elif changed:
                updated += 1
            else:
                unchanged += 1

        except BluetoothSyncError as exc:
            ui.error(f"Failed to process {label}: {exc}")
            failed += 1
        except Exception as exc:
            ui.error(f"Unexpected error while processing {label}: {exc}")
            failed += 1

    if args.dry_run:
        ui.success(
            f"Dry run finished. {len(report.records)} record(s) inspected; "
            "no files were modified."
        )
    else:
        ui.success(
            f"Finished. updated={updated}, unchanged={unchanged}, "
            f"skipped={skipped}, failed={failed}"
        )

    return 1 if failed else 0
