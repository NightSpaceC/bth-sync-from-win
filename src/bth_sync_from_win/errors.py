class BluetoothSyncError(Exception):
    """Base exception for this project."""


class RegistryError(BluetoothSyncError):
    """Failed to read or interpret the Windows registry hive."""


class ExportError(BluetoothSyncError):
    """Failed to export registry data into BlueZ-oriented records."""


class BlueZError(BluetoothSyncError):
    """Failed to process BlueZ state files."""


class FileSystemError(BlueZError):
    """Failed to create, read, write, or chmod files or directories."""
