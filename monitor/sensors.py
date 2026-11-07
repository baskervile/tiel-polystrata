"""Read optional hardware sensors without blocking PolyStrata's sampler."""

import json
import math
import os
import threading
import time
from pathlib import Path


def row(group, device, name, value, unit, source):
    return dict(group=group, device=device, name=name, value=value, unit=unit, source=source)


def nvml_rows(readings):
    fields = (
        ("gpu", "temp", "Core temperature", "°C"),
        ("fans", "fan_pct", "Requested fan speed", "%"),
        ("gpu", "power", "Power", "W"),
        ("gpu", "clock_mhz", "SM clock", "MHz"),
        ("system", "mem_free", "Free VRAM", "MiB"),
    )
    return [row(group, device or f"GPU {index}", label,
                sample[key] / 2**20 if key == "mem_free" else sample[key], unit, "NVIDIA NVML")
            for index, sample, device in readings for group, key, label, unit in fields if sample.get(key) is not None]


def lhm_rows(tree):
    sensors = []
    pending = [(tree, "", "")]
    while pending:
        node, hardware_id, device = pending.pop()
        if not isinstance(node, dict):
            continue
        if node.get("HardwareId"):
            hardware_id = str(node["HardwareId"]).strip("/").split("/")[0].lower()
            device = str(node.get("Text") or hardware_id)
        children = node.get("Children")
        if isinstance(children, list):
            pending.extend((child, hardware_id, device) for child in reversed(children))
        kind = node.get("Type")
        unit = {"Temperature": "°C", "Fan": "RPM", "Power": "W", "Voltage": "V"}.get(kind)
        value = node.get("RawValue")
        if not device or not unit or type(value) not in (int, float) or not math.isfinite(value):
            continue
        # On Windows an unreadable CPU sensor can be reported as a zero reading.
        if kind == "Temperature" and value == 0:
            continue
        group = "cpu" if "cpu" in hardware_id else "gpu" if "gpu" in hardware_id else "system"
        if hardware_id.startswith(("hdd", "ssd", "nvme", "sata", "storage", "scsi", "ata")):
            group = "ssd"
        if kind == "Fan":
            group = "fans"
        name = str(node.get("Text") or kind)
        if group == "cpu" and kind != "Temperature" and name.startswith("Core #"):
            continue
        sensors.append(row(group, device, name, value, unit, "Libre Hardware Monitor"))
    return sensors


def read_lhm(path):
    if time.time() - path.stat().st_mtime > 20:
        return []
    with path.open("rb") as stream:
        body = stream.read(1024 * 1024 + 1)
    return lhm_rows(json.loads(body)) if len(body) <= 1024 * 1024 else []


class LocalSensors:
    def __init__(self):
        self._stop = threading.Event()
        self.snapshot = ([], "unavailable")
        if os.name == "nt":
            threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        default = Path(os.environ["LOCALAPPDATA"]) / "TielHardwareMonitor/sensors.json"
        path = Path(os.environ.get("TIEL_SENSOR_FILE") or default)
        while not self._stop.is_set():
            try:
                rows = read_lhm(path)
            except (OSError, ValueError, RecursionError):
                rows = []
            self.snapshot = (rows, "connected" if rows else "unavailable")
            self._stop.wait(5)

    def close(self):
        self._stop.set()
