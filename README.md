# bth-sync-from-win

Import Bluetooth pairing keys from a Windows `SYSTEM` registry hive into the
local BlueZ state directory.

For dual-boot machines: pair a mouse, keyboard or headset once, then share the
same pairing keys between Windows and Linux instead of re-pairing every time
you switch operating system.

---

## Requirements

- Linux with BlueZ
- Python 3.11+
- root access — `/var/lib/bluetooth` is `0700 root:root`
- `python-registry` (installed automatically)

## Installation

```bash
uv sync
```

or, without `uv`:

```bash
pip install -e .
```

## Usage

### 1. Point the tool at the hive

Pass the Windows mount point and the tool will locate
`Windows/System32/config/SYSTEM` inside it; the hive file can also be given
directly. Add `--dry-run` to print every file that would be written without
touching anything — the hive itself is only ever read, never modified.

```bash
# mount point
sudo .venv/bin/python -m bth_sync_from_win /mnt/windows --dry-run

# hive file
sudo .venv/bin/python -m bth_sync_from_win \
    /mnt/windows/Windows/System32/config/SYSTEM --dry-run
```

If your NTFS volume is FUSE-mounted, it may be reachable only by the user who
mounted it, root included. In that case copy the hive out with your own
account — note the absence of `sudo` — and pass the copy:

```bash
cp /mnt/windows/Windows/System32/config/SYSTEM /tmp/SYSTEM
sudo .venv/bin/python -m bth_sync_from_win /tmp/SYSTEM --dry-run
```

### 2. Apply

```bash
sudo systemctl stop bluetooth
sudo .venv/bin/python -m bth_sync_from_win /mnt/windows
sudo systemctl start bluetooth
```

`bluetoothctl devices` should now list the devices as paired.

> Use `.venv/bin/python` rather than plain `python`: the dependencies live in
> the virtualenv, and `sudo` resets `PATH`.

### Options

| Argument | Description |
| --- | --- |
| `WINDOWS_ROOT` | Windows mount point, or a direct path to a `SYSTEM` hive file |
| `--bluez-root PATH` | BlueZ state directory (default: `/var/lib/bluetooth`) |
| `-n`, `--dry-run` | Show what would change; write nothing |
| `-y`, `--yes` | Assume "yes" for all confirmation prompts |
| `--version` | Print the version and exit |

### Before you start

- The adapter address under `Keys\` must match your Linux adapter's address.
  If the two machines use different Bluetooth hardware, nothing will match.
- The device does not have to be paired on Linux first — the tool creates the
  device directory and `info` file when they are missing — but pairing first
  is the safer path, since BlueZ then supplies its own baseline entry.
- Make sure Windows is fully shut down rather than hibernated, so the hive on
  disk is current.

---

## How it works

### 1. Read the registry hive

The hive is opened with `python-registry`. The tool reads `Select\Current` to
find the active control set, then walks:

```
ControlSet00N\Services\BTHPORT\Parameters
├── Devices\<device-mac>            Name, COD, LEAppearance
└── Keys\<adapter-mac>
    ├── <device-mac>                REG_BINARY — 16-byte BR/EDR link key
    └── <device-mac>\               BLE key material
        ├── LTK          16 bytes
        ├── IRK          16 bytes
        ├── KeyLength    DWORD
        ├── EDIV         DWORD
        └── ERand        8 bytes
```

Every entry under an adapter key whose name looks like a Bluetooth address
becomes one pairing record. The `Devices` node supplies the human-readable
name and class of device.

### 2. Convert to BlueZ format

| Windows registry | BlueZ `info` | Conversion |
| --- | --- | --- |
| link key value | `[LinkKey] Key` | 16 bytes → uppercase hex, no byte reversal |
| `IRK` | `[IdentityResolvingKey] Key` | 16 bytes → uppercase hex |
| `LTK` | `[LongTermKey]` / `[PeripheralLongTermKey]` / `[SlaveLongTermKey]` | 16 bytes → uppercase hex |
| `KeyLength` | `EncSize` | decimal |
| `EDIV` | `EDiv` | decimal |
| `ERand` | `Rand` | little-endian 64-bit → decimal |
| `COD` | `[General] Class` | `0x%06x` |
| `LEAppearance` | `[General] Appearance` | `0x%04x` |
| `Name` | `[General] Name` | UTF-8 or UTF-16LE text |

Two details worth noting:

- The LTK is written under all three section names. BlueZ renamed this section
  over time — `LongTermKey` for the central role, `PeripheralLongTermKey` and
  `SlaveLongTermKey` for the peripheral role — and reads whichever one it
  knows about, so writing all three keeps every BlueZ version happy.
- `AddressType` is derived from the address itself: when the two most
  significant bits of the first octet are `11`, the address is a static random
  address, otherwise it is public.

### 3. Merge into the BlueZ state directory

Each record targets:

```
<bluez-root>/<adapter-mac>/<device-mac>/info
<bluez-root>/<adapter-mac>/<device-mac>/attributes
```

If `info` already exists it is parsed and only the exported keys are merged
in, so sections written by BlueZ itself (`Services`, `Alias`, …) are left
untouched. An empty `attributes` file is created when it is missing.

Writes are atomic (temporary file plus rename), files are created `0600` and
directories `0700`, and existing symlinks are refused rather than followed.
BlueZ has to be restarted to pick up the new files.

---

## Example output

```ini
[General]
Class = 0x5a020c
Appearance = 0x00c0
Name = Pixel 7
Trusted = true
SupportedTechnologies = BR/EDR;LE
AddressType = public

[LinkKey]
Key = 0123456789ABCDEF0123456789ABCDEF
Type = 4
PINLength = 0

[IdentityResolvingKey]
Key = AABBCCDDEEFF00112233445566778899

[PeripheralLongTermKey]
Key = FFEEDDCCBBAA99887766554433221100
Authenticated = 2
EncSize = 16
EDiv = 4321
Rand = 987654321
```

## License

MIT
