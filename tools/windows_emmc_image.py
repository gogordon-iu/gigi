#!/usr/bin/env python3
"""Windows USB-eMMC imaging utility.

Install the compression dependency:
    python -m pip install zstandard

Run from an elevated terminal:
    python tools/windows_emmc_image.py list
    python tools/windows_emmc_image.py dump --disk 2 --output emmc.img.zst
    python tools/windows_emmc_image.py flash --disk 2 --input emmc.img.zst

Flash overwrites the selected disk. Images may expand to less than the target
disk's byte size if they contain at least 50 decimal GB; excess image bytes are
not written beyond the target capacity. Dump --max-steps performs a bounded
probe and discards its temporary compressed output; it never publishes an
incomplete image. Dump and flash accept --log-file to tee output to a UTF-8 log.

Disk sizes and displayed GB/MB use decimal units. Transfer chunks are 16 MiB.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, BinaryIO, Iterator, Sequence


CHUNK_SIZE = 16 * 1024 * 1024
MIN_DISK_SIZE = 50_000_000_000
MAX_DISK_SIZE = 70_000_000_000
PROGRESS_INTERVAL = 2.0

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FSCTL_LOCK_VOLUME = 0x00090018
FSCTL_DISMOUNT_VOLUME = 0x00090020
FSCTL_UNLOCK_VOLUME = 0x0009001C
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

VOLUME_PATH_PATTERN = re.compile(
    r"^\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\$"
)
DRIVE_PATH_PATTERN = re.compile(r"^[a-zA-Z]:\\$")


class ImagingError(RuntimeError):
    """An actionable imaging or safety-check failure."""


class Tee:
    """Mirror text output while preserving the original stream's interface."""

    def __init__(self, stream: Any, log: Any) -> None:
        self.stream = stream
        self.log = log

    def write(self, text: str) -> int:
        self.log.write(text)
        self.stream.write(text)
        return len(text)

    def flush(self) -> None:
        self.log.flush()
        self.stream.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.stream, name)


@dataclass(frozen=True)
class Disk:
    number: int
    friendly_name: str
    bus_type: str
    size: int
    partition_style: str
    sector_size: int
    unique_id: str
    serial_number: str
    is_boot: bool
    is_system: bool
    access_paths: tuple[str, ...]

    @property
    def device_path(self) -> str:
        return rf"\\.\PhysicalDrive{self.number}"


class WindowsAPI:
    """Small, explicitly typed Win32 interface for volume safety operations."""

    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)

        self.kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        self.kernel.CreateFileW.restype = wintypes.HANDLE

        self.kernel.DeviceIoControl.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        ]
        self.kernel.DeviceIoControl.restype = wintypes.BOOL

        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

        self.kernel.GetVolumePathNameW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.kernel.GetVolumePathNameW.restype = wintypes.BOOL

        self.kernel.GetVolumeNameForVolumeMountPointW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPWSTR,
            wintypes.DWORD,
        ]
        self.kernel.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL

    @staticmethod
    def error(operation: str) -> ImagingError:
        error_code = ctypes.get_last_error()
        return ImagingError(
            f"{operation}: {ctypes.FormatError(error_code).strip()} "
            f"(Windows error {error_code})"
        )

    def volume_for_path(self, path: Path) -> str | None:
        # A UNC path resides on a remote server, not this local physical disk.
        resolved = str(path.resolve(strict=True))
        if resolved.startswith("\\\\") and not resolved.startswith("\\\\?\\"):
            return None

        mount_point = ctypes.create_unicode_buffer(32768)
        if not self.kernel.GetVolumePathNameW(
            resolved, mount_point, len(mount_point)
        ):
            raise self.error(f"Cannot identify the volume containing {path}")

        volume_name = ctypes.create_unicode_buffer(32768)
        if not self.kernel.GetVolumeNameForVolumeMountPointW(
            mount_point.value, volume_name, len(volume_name)
        ):
            raise self.error(f"Cannot identify the local volume containing {path}")
        return volume_name.value

    def open_volume(self, device_path: str) -> int:
        handle = self.kernel.CreateFileW(
            device_path,
            GENERIC_READ | GENERIC_WRITE,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle is None or handle == INVALID_HANDLE_VALUE:
            raise self.error(f"Cannot open volume {device_path}")
        return int(handle)

    def control(self, handle: int, code: int, operation: str) -> None:
        returned = wintypes.DWORD()
        if not self.kernel.DeviceIoControl(
            handle, code, None, 0, None, 0, ctypes.byref(returned), None
        ):
            raise self.error(operation)

    def close(self, handle: int) -> None:
        if not self.kernel.CloseHandle(handle):
            print(
                f"Warning: {self.error('Cannot close volume handle')}",
                file=sys.stderr,
            )


def positive_int(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return result


def disk_number(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if result < 0 or result > 2_147_483_647:
        raise argparse.ArgumentTypeError("must be a nonnegative 32-bit integer")
    return result


def powershell(script: str, timeout: float = 120.0) -> Any:
    executable = shutil.which("powershell.exe")
    if executable is None:
        raise ImagingError("Windows PowerShell (powershell.exe) was not found.")

    prefix = """
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
"""
    try:
        result = subprocess.run(
            [
                executable,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                prefix + script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise ImagingError(
            f"PowerShell did not finish within {timeout:g} seconds. "
            "Verify the disk's state before retrying."
        ) from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ImagingError(f"PowerShell failed: {detail or result.returncode}")

    output = result.stdout.strip().lstrip("\ufeff")
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise ImagingError(f"PowerShell returned invalid JSON: {output[:500]}") from exc


def integer_field(data: dict[str, Any], name: str) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ImagingError(f"Get-Disk returned an invalid {name}: {value!r}")
    return value


def query_disks(number: int | None = None) -> list[Disk]:
    selection = "Get-Disk" if number is None else f"Get-Disk -Number {number}"
    # Get-Partition access paths include drive letters, mounted folders, and
    # volume GUID paths. Get-Volume supplies GUID paths for letterless volumes.
    partition_query = """
    $paths = @()
    if ([string]$d.PartitionStyle -ne 'RAW') {
        $parts = @(Get-Partition -DiskNumber $d.Number)
        foreach ($p in $parts) {
            $paths += @($p.AccessPaths)
            $volumes = @(Get-Volume -Partition $p)
            foreach ($v in $volumes) {
                if ($v.Path) { $paths += [string]$v.Path }
            }
        }
    }
""" if number is not None else "$paths = @()"

    data = powershell(
        f"""
$items = @(
    {selection} | Sort-Object Number | ForEach-Object {{
        $d = $_
        {partition_query}
        [pscustomobject]@{{
            Number = [int]$d.Number
            FriendlyName = [string]$d.FriendlyName
            BusType = [string]$d.BusType
            Size = [long]$d.Size
            PartitionStyle = [string]$d.PartitionStyle
            LogicalSectorSize = [int]$d.LogicalSectorSize
            UniqueId = [string]$d.UniqueId
            SerialNumber = [string]$d.SerialNumber
            IsBoot = [bool]$d.IsBoot
            IsSystem = [bool]$d.IsSystem
            AccessPaths = @($paths | Where-Object {{ $_ }} | Select-Object -Unique)
        }}
    }}
)
ConvertTo-Json -InputObject $items -Depth 5 -Compress
"""
    )
    if not isinstance(data, list):
        raise ImagingError("Get-Disk returned an unexpected result.")

    disks: list[Disk] = []
    for item in data:
        if not isinstance(item, dict):
            raise ImagingError("Get-Disk returned an invalid disk entry.")
        paths = item.get("AccessPaths", [])
        if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
            raise ImagingError("Get-Disk returned invalid partition access paths.")
        for name in ("IsBoot", "IsSystem"):
            if not isinstance(item.get(name), bool):
                raise ImagingError(f"Get-Disk returned an invalid {name}.")
        disks.append(
            Disk(
                number=integer_field(item, "Number"),
                friendly_name=str(item.get("FriendlyName", "")),
                bus_type=str(item.get("BusType", "")),
                size=integer_field(item, "Size"),
                partition_style=str(item.get("PartitionStyle", "")),
                sector_size=integer_field(item, "LogicalSectorSize"),
                unique_id=str(item.get("UniqueId", "")).strip(),
                serial_number=str(item.get("SerialNumber", "")).strip(),
                is_boot=item["IsBoot"],
                is_system=item["IsSystem"],
                access_paths=tuple(paths),
            )
        )
    return disks


def validate_disk(number: int) -> Disk:
    if number == 0:
        raise ImagingError("Disk 0 is explicitly forbidden.")
    disks = query_disks(number)
    if len(disks) != 1 or disks[0].number != number:
        raise ImagingError(f"Could not uniquely identify Disk {number}.")
    disk = disks[0]
    if disk.bus_type.casefold() != "usb":
        raise ImagingError(
            f"Disk {number} has BusType {disk.bus_type!r}; only USB is allowed."
        )
    if not MIN_DISK_SIZE <= disk.size <= MAX_DISK_SIZE:
        raise ImagingError(
            f"Disk {number} is {disk.size / 1e9:.3f} GB; "
            "only disks between 50 and 70 decimal GB are allowed."
        )
    if disk.is_boot or disk.is_system:
        raise ImagingError("Refusing a boot or system disk.")
    if (
        disk.sector_size <= 0
        or disk.size % disk.sector_size != 0
        or CHUNK_SIZE % disk.sector_size != 0
    ):
        raise ImagingError("Disk size or sector size is incompatible with aligned I/O.")
    return disk


def revalidate_disk(original: Disk) -> Disk:
    current = validate_disk(original.number)
    identity_before = (
        original.size,
        original.sector_size,
        original.friendly_name,
        original.unique_id,
        original.serial_number,
    )
    identity_after = (
        current.size,
        current.sector_size,
        current.friendly_name,
        current.unique_id,
        current.serial_number,
    )
    if identity_before != identity_after:
        raise ImagingError("Disk identity changed; refusing to continue.")
    return current


def require_administrator() -> None:
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.IsUserAnAdmin.argtypes = []
    shell.IsUserAnAdmin.restype = wintypes.BOOL
    if not shell.IsUserAnAdmin():
        raise ImagingError("Run this command from an Administrator terminal.")


def ensure_external_storage(api: WindowsAPI, disk: Disk, path: Path) -> None:
    volume = api.volume_for_path(path)
    if volume is None:
        return
    target_paths = {p.rstrip("\\").casefold() for p in disk.access_paths}
    if volume.rstrip("\\").casefold() in target_paths:
        raise ImagingError(
            f"{path} is on the selected eMMC disk. Use a different storage device."
        )


@contextlib.contextmanager
def locked_volumes(api: WindowsAPI, disk: Disk) -> Iterator[None]:
    guid_paths = {
        p.rstrip("\\")
        for p in disk.access_paths
        if VOLUME_PATH_PATTERN.fullmatch(p)
    }
    # Normally GUID paths cover every volume. A letter fallback is required
    # when an adapter exposes only drive-letter access paths.
    paths = sorted(guid_paths)
    if not paths:
        paths = sorted(
            {
                rf"\\.\{p[:2]}"
                for p in disk.access_paths
                if DRIVE_PATH_PATTERN.fullmatch(p)
            }
        )
    handles: list[tuple[int, str]] = []
    try:
        for path in paths:
            handle = api.open_volume(path)
            try:
                api.control(handle, FSCTL_LOCK_VOLUME, f"Cannot lock {path}")
            except BaseException:
                api.close(handle)
                raise
            handles.append((handle, path))
            api.control(handle, FSCTL_DISMOUNT_VOLUME, f"Cannot dismount {path}")
        yield
    finally:
        for handle, path in reversed(handles):
            try:
                api.control(handle, FSCTL_UNLOCK_VOLUME, f"Cannot unlock {path}")
            except ImagingError as exc:
                print(f"Warning: {exc}", file=sys.stderr)
            finally:
                api.close(handle)


class Progress:
    def __init__(self, operation: str, total: int) -> None:
        if total <= 0:
            raise ImagingError("Progress requires a positive total size.")
        self.operation = operation
        self.total = total
        self.started = time.monotonic()
        self.last_print = self.started

    def update(
        self, completed: int, compressed_size: int | None = None, *, final: bool = False
    ) -> None:
        now = time.monotonic()
        if not final and now - self.last_print < PROGRESS_INTERVAL:
            return
        elapsed = max(now - self.started, 1e-9)
        speed = completed / elapsed
        eta = (self.total - completed) / speed if speed > 0 else math.inf
        eta_text = f"{max(eta, 0.0):.0f}s" if math.isfinite(eta) else "unknown"
        compressed = (
            f", compressed {compressed_size / 1e9:.3f} GB"
            if compressed_size is not None
            else ""
        )
        print(
            f"{self.operation}: {completed / 1e9:.3f} / {self.total / 1e9:.3f} GB "
            f"({100.0 * completed / self.total:.2f}%){compressed}, "
            f"{speed / 1e6:.1f} MB/s, ETA {eta_text}",
            flush=True,
        )
        self.last_print = now


def import_zstandard() -> Any:
    try:
        import zstandard
    except ImportError as exc:
        raise ImagingError(
            "Missing dependency: install it with 'python -m pip install zstandard'."
        ) from exc
    return zstandard


def list_command() -> None:
    disks = query_disks()
    if not disks:
        print("No disks found.")
        return
    headers = ("DiskNumber", "FriendlyName", "BusType", "SizeGB", "PartitionStyle")
    rows = [
        (
            str(d.number),
            " ".join(d.friendly_name.split()),
            d.bus_type,
            f"{d.size / 1e9:.3f}",
            d.partition_style,
        )
        for d in disks
    ]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    print("  ".join(text.ljust(width) for text, width in zip(headers, widths)))
    for row in rows:
        print("  ".join(text.ljust(width) for text, width in zip(row, widths)))


def dump_command(args: argparse.Namespace) -> None:
    require_administrator()
    zstd = import_zstandard()
    disk = validate_disk(args.disk)
    api = WindowsAPI()

    output = Path(args.output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ImagingError(f"Output already exists; refusing to overwrite: {output}")
    if not output.parent.is_dir():
        raise ImagingError(f"Output directory does not exist: {output.parent}")
    ensure_external_storage(api, disk, output.parent)

    try:
        compressor = zstd.ZstdCompressor(level=args.level, threads=-1)
    except (ValueError, zstd.ZstdError) as exc:
        raise ImagingError(f"Invalid compression level: {exc}") from exc

    disk = revalidate_disk(disk)
    transferred = 0
    steps = 0
    progress = Progress("Read", disk.size)
    temporary: Path | None = None

    print(
        f"Dumping Disk {disk.number}: {disk.friendly_name}, "
        f"{disk.size / 1e9:.3f} GB",
        flush=True,
    )
    print(
        "Keep the source idle and close applications using its files. "
        "A live, changing filesystem is not a consistent snapshot.",
        flush=True,
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            buffering=0,
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as destination:
            temporary = Path(destination.name)
            with open(disk.device_path, "rb", buffering=0) as source:
                with compressor.stream_writer(
                    destination, closefd=False, size=disk.size
                    if args.max_steps is None
                    else -1,
                ) as writer:
                    while transferred < disk.size:
                        if args.max_steps is not None and steps >= args.max_steps:
                            break
                        requested = min(CHUNK_SIZE, disk.size - transferred)
                        data = source.read(requested)
                        if len(data) != requested:
                            raise ImagingError(
                                f"Short raw read at byte {transferred}: "
                                f"expected {requested}, received {len(data)}."
                            )
                        writer.write(data)
                        transferred += len(data)
                        steps += 1
                        progress.update(transferred, os.fstat(destination.fileno()).st_size)
            destination.flush()
            os.fsync(destination.fileno())
            compressed_size = os.fstat(destination.fileno()).st_size

        progress.update(transferred, compressed_size, final=True)
        if args.max_steps is not None:
            print(
                f"Probe completed after {steps} chunk(s). "
                "Temporary output discarded; no image created."
            )
            return
        if transferred != disk.size:
            raise ImagingError("Incomplete dump; refusing to publish the image.")

        # On Windows os.rename fails if the destination already exists.
        os.rename(temporary, output)
        temporary = None
        print(f"Image saved: {output}")
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                print(f"Warning: cannot remove temporary file {temporary}: {exc}",
                      file=sys.stderr)


def read_chunk(reader: Any, limit: int) -> bytes:
    data = bytearray()
    while len(data) < limit:
        piece = reader.read(limit - len(data))
        if not isinstance(piece, bytes):
            raise ImagingError("Decompressor returned non-byte data.")
        if not piece:
            break
        data.extend(piece)
    return bytes(data)


def write_aligned(destination: BinaryIO, data: bytes, sector_size: int) -> None:
    if not data or len(data) % sector_size:
        raise ImagingError("Refusing an empty or non-sector-aligned raw write.")
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = destination.write(view[offset:])
        if (
            written is None
            or written <= 0
            or written > len(view) - offset
            or written % sector_size
        ):
            raise ImagingError("Raw write failed or returned an unaligned byte count.")
        offset += written


def flash_command(args: argparse.Namespace) -> None:
    require_administrator()
    zstd = import_zstandard()
    disk = validate_disk(args.disk)
    api = WindowsAPI()

    image = Path(args.input).expanduser().resolve(strict=True)
    if not image.is_file() or image.stat().st_size == 0:
        raise ImagingError("Input must be a nonempty, regular compressed image file.")
    ensure_external_storage(api, disk, image)

    print(
        f"WARNING: ALL DATA on Disk {disk.number} will be overwritten.\n"
        f"Target: {disk.friendly_name}, USB, {disk.size / 1e9:.3f} GB\n"
        f"Image:  {image}",
        flush=True,
    )
    if not args.yes:
        if not sys.stdin.isatty():
            raise ImagingError("Interactive confirmation required; use --yes to confirm.")
        expected = f"FLASH {disk.number}"
        try:
            confirmation = input(f"Type '{expected}' to continue: ")
        except EOFError as exc:
            raise ImagingError("Confirmation was not provided.") from exc
        if confirmation != expected:
            raise ImagingError("Confirmation did not match; nothing was written.")

    disk = revalidate_disk(disk)
    powershell(
        f"""
Set-Disk -Number {disk.number} -IsReadOnly $false
Set-Disk -Number {disk.number} -IsOffline $false
"""
    )
    disk = revalidate_disk(disk)
    ensure_external_storage(api, disk, image)

    transferred = 0
    progress = Progress("Written", disk.size)
    write_started = False

    try:
        with open(image, "rb") as source:
            with zstd.ZstdDecompressor().stream_reader(
                source, read_across_frames=True, closefd=False
            ) as reader:
                # Decode the first block before locking or writing the disk.
                pending = read_chunk(reader, min(CHUNK_SIZE, disk.size))
                if not pending:
                    raise ImagingError("Compressed input expands to an empty image.")
                with locked_volumes(api, disk):
                    revalidate_disk(disk)
                    with open(disk.device_path, "r+b", buffering=0) as destination:
                        try:
                            while transferred < disk.size:
                                expected = min(CHUNK_SIZE, disk.size - transferred)
                                reached_eof = len(pending) != expected
                                if (
                                    reached_eof
                                    and transferred + len(pending) < MIN_DISK_SIZE
                                ):
                                    raise ImagingError(
                                        "Image is smaller than the minimum allowed size: "
                                        f"decompressed {transferred + len(pending)} "
                                        f"bytes, expected at least {MIN_DISK_SIZE}."
                                    )
                                if pending:
                                    write_started = True
                                    write_aligned(destination, pending, disk.sector_size)
                                    transferred += len(pending)
                                    progress.update(transferred)

                                if reached_eof:
                                    print(
                                        f"Note: Image ended after {transferred} bytes "
                                        f"({transferred / 1e9:.3f} GB). "
                                        "The remaining target disk bytes were left unchanged.",
                                        flush=True,
                                    )
                                    break

                                if transferred < disk.size:
                                    pending = read_chunk(
                                        reader, min(CHUNK_SIZE, disk.size - transferred)
                                    )

                            # At capacity, check for excess data without writing it.
                            # For an exact-size image this also processes checksums.
                            if transferred == disk.size and read_chunk(reader, 1):
                                print(
                                    "Note: Image is larger than the target disk. "
                                    f"Stopped after {transferred} bytes "
                                    f"({transferred / 1e9:.3f} GB); "
                                    "trailing image bytes were not written.",
                                    flush=True,
                                )
                        finally:
                            destination.flush()
                            # Some USB bridges do not support FlushFileBuffers
                            # on raw PhysicalDrive handles.
                            with contextlib.suppress(OSError):
                                os.fsync(destination.fileno())

        progress.update(transferred, final=True)
        print(
            "Flash complete. Safely disconnect/reconnect the adapter "
            "before using the restored partition table."
        )
    except BaseException:
        if write_started:
            print(
                "WARNING: Flash did not complete successfully. The target may "
                "contain an incomplete or invalid image; do not boot from it.",
                file=sys.stderr,
                flush=True,
            )
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Dump or flash 50–70 GB USB Orange Pi eMMC disks on Windows. "
            "Disk 0, non-USB disks, and boot/system disks are forbidden."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List disks reported by PowerShell Get-Disk.")

    dump = commands.add_parser("dump", help="Stream a complete disk into a .img.zst image.")
    dump.add_argument("--disk", required=True, type=disk_number)
    dump.add_argument("--output", required=True, type=Path)
    dump.add_argument("--level", type=int, default=3, help="Zstandard level (default: 3).")
    dump.add_argument(
        "--max-steps",
        type=positive_int,
        default=None,
        help="Probe at most this many 16 MiB chunks; discard output instead of saving an image.",
    )
    dump.add_argument(
        "--log-file",
        type=Path,
        help="Tee progress and error output to a UTF-8 log file.",
    )

    flash = commands.add_parser("flash", help="Destructively restore a .img.zst image.")
    flash.add_argument("--disk", required=True, type=disk_number)
    flash.add_argument("--input", required=True, type=Path)
    flash.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive flashing without an interactive prompt.",
    )
    flash.add_argument(
        "--log-file",
        type=Path,
        help="Tee progress and error output to a UTF-8 log file.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        with contextlib.ExitStack() as stack:
            log_file = getattr(args, "log_file", None)
            if log_file is not None:
                log = stack.enter_context(
                    open(log_file.expanduser(), "a", encoding="utf-8", buffering=1)
                )
                stack.enter_context(contextlib.redirect_stdout(Tee(sys.stdout, log)))
                stack.enter_context(contextlib.redirect_stderr(Tee(sys.stderr, log)))

            try:
                if os.name != "nt":
                    print("Error: this utility runs only on Windows.", file=sys.stderr)
                    return 1

                if args.command == "list":
                    list_command()
                elif args.command == "dump":
                    dump_command(args)
                elif args.command == "flash":
                    flash_command(args)
                else:
                    raise ImagingError(f"Unsupported command: {args.command}")
                return 0
            except KeyboardInterrupt:
                print("\nInterrupted.", file=sys.stderr)
                return 130
            except Exception as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
