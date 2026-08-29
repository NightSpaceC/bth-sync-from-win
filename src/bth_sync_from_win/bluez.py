from configparser import ConfigParser, Error as ConfigParserError
from io import StringIO
from pathlib import Path
from typing import Dict

from . import fs, ui
from .constants import ATTRIBUTES_FILENAME, INFO_FILENAME
from .errors import BlueZError
from .models import PairRecord


def _new_config() -> ConfigParser:
    config = ConfigParser(
        delimiters=("=",),
        comment_prefixes=("#", ";"),
        interpolation=None,
        strict=False,
    )
    config.optionxform = str
    return config


def _render(config: ConfigParser) -> str:
    output = StringIO()
    config.write(output)
    return output.getvalue()


def _merge(config: ConfigParser, sections: Dict[str, Dict[str, str]]) -> bool:
    changed = False

    for section_name, options in sections.items():
        if not config.has_section(section_name):
            config.add_section(section_name)
            changed = True

        for option, value in options.items():
            if not config.has_option(section_name, option):
                config.set(section_name, option, value)
                changed = True
            elif config.get(section_name, option) != value:
                config.set(section_name, option, value)
                changed = True

    return changed


def _read_info(path: Path) -> ConfigParser:
    config = _new_config()

    try:
        config.read(path, encoding="utf-8")
    except (OSError, UnicodeDecodeError, ConfigParserError) as exc:
        raise BlueZError(f"Existing info file {path} could not be parsed: {exc}") from exc

    return config


def process_pair(
    record: PairRecord,
    bluez_root: Path,
    assume_yes: bool,
    dry_run: bool,
) -> bool:
    adapter_dir = bluez_root / record.local.bluez
    device_dir = adapter_dir / record.remote.bluez
    info_path = device_dir / INFO_FILENAME
    attributes_path = device_dir / ATTRIBUTES_FILENAME

    if not adapter_dir.is_dir():
        raise BlueZError(f"Adapter directory {adapter_dir} does not exist")

    if device_dir.is_symlink():
        raise BlueZError(f"{device_dir} is a symlink; refusing to manage it")

    if info_path.is_symlink():
        raise BlueZError(f"{info_path} is a symlink; refusing to manage it")

    if attributes_path.is_symlink():
        raise BlueZError(f"{attributes_path} is a symlink; refusing to manage it")

    if device_dir.exists() and not device_dir.is_dir():
        raise BlueZError(f"{device_dir} exists but is not a directory")

    if info_path.exists() and not info_path.is_file():
        raise BlueZError(f"{info_path} exists but is not a regular file")

    if attributes_path.exists() and not attributes_path.is_file():
        raise BlueZError(f"{attributes_path} exists but is not a regular file")

    if info_path.is_file():
        config = _read_info(info_path)
        info_changed = _merge(config, record.sections)
        attributes_missing = not attributes_path.exists()

        if not info_changed and not attributes_missing:
            ui.info(f"{record.local} -> {record.remote}: {info_path} is up to date.")
            return False

        rendered = _render(config) if info_changed else ""

        if info_changed:
            ui.info(f"Will merge exported data into {info_path}:")
            ui.block(rendered)
        else:
            ui.info(f"{info_path} already contains all exported values.")

        if attributes_missing:
            ui.info(f"Will create empty {attributes_path}.")

        if dry_run:
            ui.info("Dry run: no files will be changed.")
            return False

        if not ui.confirm(f"Apply these changes to {record.remote}?", assume_yes):
            ui.info("Skipped.")
            return False

        if info_changed:
            fs.write_text_atomic(info_path, rendered, 0o600)
            ui.success(f"Updated {info_path}.")

        if attributes_missing:
            fs.ensure_empty_file(attributes_path, 0o600)
            ui.success(f"Created {attributes_path}.")

        return True

    # info file does not exist.
    config = _new_config()
    _merge(config, record.sections)
    rendered = _render(config)
    attributes_missing = not attributes_path.exists()

    if device_dir.exists():
        ui.info(f"{info_path} is missing. Existing files under {device_dir} will be preserved.")
    else:
        ui.info(f"Will create device directory {device_dir}.")

    ui.info(f"Will write {info_path}:")
    ui.block(rendered)

    if attributes_missing:
        ui.info(f"Will create empty {attributes_path}.")

    if dry_run:
        ui.info("Dry run: no files will be created.")
        return False

    if not ui.confirm(f"Create pairing files for {record.remote}?", assume_yes):
        ui.info("Skipped.")
        return False

    fs.ensure_directory(device_dir, 0o700)
    fs.write_text_atomic(info_path, rendered, 0o600)
    ui.success(f"Created {info_path}.")

    if attributes_missing:
        fs.ensure_empty_file(attributes_path, 0o600)
        ui.success(f"Created {attributes_path}.")

    return True
