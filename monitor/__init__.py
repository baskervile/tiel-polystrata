"""Install the sensor overlay on a compatible PolyStrata checkout."""

from pathlib import Path

HERE = Path(__file__).resolve().parent

TELEMETRY = (
    ("import time\n", "import time\n\nfrom serve.tiel_sensors import LocalSensors, nvml_rows\n"),
    ('                out["mem_used"], out["mem_total"] = m.used, m.total',
     '                out["mem_used"], out["mem_total"] = m.used, m.total\n                out["mem_free"] = m.free'),
    ('        mw = self._uint("nvmlDeviceGetPowerUsage")',
     '        out["fan_pct"] = self._uint("nvmlDeviceGetFanSpeed")\n'
     '        out["clock_mhz"] = self._uint("nvmlDeviceGetClockInfo", ctypes.c_uint(1))  # NVML_CLOCK_SM\n'
     '        mw = self._uint("nvmlDeviceGetPowerUsage")'),
    ('        self.gpu = self.gpus[0][1]',
     '        self.gpu = self.gpus[0][1]\n'
     '        self.tiel_sensors = LocalSensors()\n'
     '        self.tiel_gpu_names = {i: g.name() for i, g in self.gpus if g.ok()}'),
    ('        s = {}\n        if self.gpu.ok():',
     '        s = {}\n        extra_sensors, provider = self.tiel_sensors.snapshot\n'
     '        s["tiel_sensor_provider"] = provider\n'
     '        s["tiel_sensors"] = extra_sensors\n'
     '        if self.gpu.ok():'),
    ('            reads = [(i, g.read()) for i, g in self.gpus]',
     '            reads = [(i, g.read()) for i, g in self.gpus]\n'
     '            s["tiel_sensors"] = nvml_rows((i, r, self.tiel_gpu_names.get(i)) for i, r in reads) + extra_sensors'),
    ('        self._stop.set()\n\n    def _loop(self):',
     '        self._stop.set()\n        self.tiel_sensors.close()\n\n    def _loop(self):'),
)

HTML = (
    ('      <div class="monitor-row">',
     '''      <div class="st-card" id="tiel-sensor-card">
        <span class="card-title">Hardware sensors</span>
        <p class="muted small" id="tiel-sensor-status">Waiting for readings</p>
        <dl class="facts" id="tiel-sensor-values"></dl>
      </div>
      <div class="monitor-row">'''),
    ('        <p class="muted small">Chats, settings and the key are kept in this browser only.',
     '''        <fieldset id="tiel-sensor-settings">
          <legend>Hardware sensors</legend>
          <div id="tiel-sensor-options"></div>
          <p class="muted small">Choose what to show in Monitor. Optional temperature warnings use °C.</p>
        </fieldset>
        <p class="muted small">Chats, settings and the key are kept in this browser only.'''),
    ('<script src="web/app.js"></script>',
     '<script src="web/app.js"></script>\n<script src="web/tiel-monitor.js"></script>'),
)

APP = (
    ('  if (tab === "monitor") renderConvCache(m.conversation_cache);',
     '  if (tab === "monitor") renderConvCache(m.conversation_cache);\n'
     '  if (tab === "monitor") window.tielRenderSensors?.(hw);'),
)


def install_monitor(source):
    changes = {}
    for relative, edits in (("serve/telemetry.py", TELEMETRY), ("serve/web/index.html", HTML), ("serve/web/app.js", APP)):
        path = source / relative
        if not path.is_file():
            raise RuntimeError(f"Incompatible PolyStrata monitor layout: {path}")
        original = text = path.read_text(encoding="utf-8")
        for old, new in edits:
            if new in text:
                continue
            if text.count(old) != 1:
                raise RuntimeError(f"Incompatible PolyStrata monitor hook in {path}: {old.strip()}")
            text = text.replace(old, new, 1)
        if text != original:
            changes[path] = text
    for relative, asset in (("serve/tiel_sensors.py", "sensors.py"), ("serve/web/tiel-monitor.js", "sensors.js")):
        path = source / relative
        content = (HERE / asset).read_text(encoding="utf-8")
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            changes[path] = content
    for path, content in changes.items():
        staging = path.with_name(path.name + ".tiel-next")
        staging.write_text(content, encoding="utf-8")
        staging.replace(path)
