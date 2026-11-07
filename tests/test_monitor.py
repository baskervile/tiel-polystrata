import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from monitor import install_monitor
from monitor.sensors import lhm_rows, nvml_rows, read_lhm


class MonitorTests(unittest.TestCase):
    def test_sensor_groups_and_units_keep_a_stopped_fan_visible(self):
        sample = {"Children": [
            {"HardwareId": "/amdcpu/0", "Text": "CPU", "Children": [
                {"Children": [{"Text": "CPU Package", "Type": "Temperature", "RawValue": 61},
                              {"Text": "Unreadable CPU", "Type": "Temperature", "RawValue": 0}]}]},
            {"HardwareId": "/nvme/0", "Text": "NVMe", "Children": [
                {"Text": "Composite", "Type": "Temperature", "RawValue": 44.0}]},
            {"HardwareId": "/lpc/0", "Text": "Board", "Children": [
                {"Text": "Chassis", "Type": "Fan", "RawValue": 0}]},
            {"HardwareId": "/gpu-nvidia/0", "Text": "GPU", "Children": [
                {"Text": "Missing", "Type": "Temperature", "RawValue": None}]},
        ]}
        rows = lhm_rows(sample)
        self.assertEqual([(r["group"], r["value"], r["unit"]) for r in rows],
                         [("cpu", 61, "°C"), ("ssd", 44, "°C"), ("fans", 0, "RPM")])

    def test_nvml_fan_duty_is_a_percentage_and_missing_values_are_omitted(self):
        rows = nvml_rows([(0, {"temp": 37, "fan_pct": 30, "power": None}, "RTX")])
        self.assertEqual([(r["group"], r["value"], r["unit"]) for r in rows],
                         [("gpu", 37, "°C"), ("fans", 30, "%")])

    def test_stale_bridge_snapshot_is_not_shown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sensors.json"
            path.write_text(json.dumps({"HardwareId": "/amdcpu/0", "Text": "CPU", "Children": [
                {"Text": "Package", "Type": "Temperature", "RawValue": 67}]}))
            self.assertEqual(read_lhm(path)[0]["value"], 67)
            past = time.time() - 30
            os.utime(path, (past, past))
            self.assertEqual(read_lhm(path), [])

    def test_overlay_refuses_an_incompatible_checkout_before_writing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            (source / "serve/web").mkdir(parents=True)
            for file in ("serve/telemetry.py", "serve/web/index.html", "serve/web/app.js"):
                (source / file).write_text("unexpected upstream layout")
            with self.assertRaisesRegex(RuntimeError, "PolyStrata"):
                install_monitor(source)
            self.assertEqual((source / "serve/telemetry.py").read_text(), "unexpected upstream layout")
            self.assertFalse((source / "serve/tiel_sensors.py").exists())
