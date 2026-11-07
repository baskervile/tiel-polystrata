(() => {
  "use strict";
  const groups = {cpu: "CPU", gpu: "GPU", ssd: "Storage", fans: "Fans", system: "System"};
  const thermal = new Set(["cpu", "gpu", "ssd"]);
  const inputs = {};
  const prefs = store.get("tiel.sensorPrefs", {}) || {};
  const options = document.getElementById("tiel-sensor-options");
  const card = document.getElementById("tiel-sensor-card");
  const values = document.getElementById("tiel-sensor-values");
  const status = document.getElementById("tiel-sensor-status");
  let latest = null;

  function warnAt(group) {
    const limit = inputs[group].limit;
    return limit?.value && limit.checkValidity() ? limit.valueAsNumber : null;
  }

  function save() {
    store.set("tiel.sensorPrefs", Object.fromEntries(Object.entries(inputs).map(
      ([group, {show}]) => [group, {show: show.checked, limit: warnAt(group)}]
    )));
    if (latest) window.tielRenderSensors(latest);
  }

  for (const [group, label] of Object.entries(groups)) {
    const line = document.createElement("div");
    line.className = "toggle-row";
    const showLabel = document.createElement("label");
    const show = document.createElement("input");
    show.type = "checkbox";
    show.checked = prefs[group]?.show !== false;
    show.addEventListener("change", save);
    showLabel.append(show, " " + label);
    line.append(showLabel);
    let limit = null;
    if (thermal.has(group)) {
      limit = document.createElement("input");
      limit.className = "st-input";
      limit.type = "number";
      limit.min = "1";
      limit.max = "150";
      limit.placeholder = "Warn at °C";
      limit.setAttribute("aria-label", label + " warning temperature in Celsius");
      limit.value = prefs[group]?.limit ?? "";
      limit.addEventListener("change", save);
      line.append(limit);
    }
    inputs[group] = {show, limit};
    options.append(line);
  }

  window.tielRenderSensors = (hw) => {
    latest = hw;
    const rows = Array.isArray(hw.tiel_sensors) ? hw.tiel_sensors.slice() : [];
    if (Number.isFinite(hw.ram_total) && Number.isFinite(hw.ram_used)) {
      rows.push({group: "system", name: "Available RAM", value: (hw.ram_total - hw.ram_used) / 2**30, unit: "GiB"});
    }
    card.hidden = !Object.values(inputs).some(({show}) => show.checked);
    status.textContent = hw.tiel_sensor_provider === "connected"
      ? "Libre Hardware Monitor connected. Warnings use your browser settings."
      : "Additional sensors unavailable. For CPU, drive and chassis readings, connect Libre Hardware Monitor on the host.";
    const rendered = document.createDocumentFragment();
    for (const [group, label] of Object.entries(groups)) {
      if (!inputs[group].show.checked) continue;
      const readings = rows.filter((r) => r.group === group && Number.isFinite(r.value));
      if (thermal.has(group) && !readings.some((r) => r.unit === "°C")) {
        readings.unshift({name: "Temperature unavailable"});
      } else if (!readings.length) {
        readings.push({name: "Unavailable"});
      }
      for (const r of readings) {
        const title = document.createElement("dt");
        title.textContent = [label, r.device, r.name].filter(Boolean).join(" · ");
        if (r.source) title.title = r.source;
        const value = document.createElement("dd");
        const limit = warnAt(group);
        const hot = r.unit === "°C" && limit !== null && r.value >= limit;
        value.textContent = r.value == null ? "—" : `${fmt(r.value, Number.isInteger(r.value) ? 0 : 1)} ${r.unit}${hot ? " ⚠ Above warning threshold" : ""}`;
        if (hot) value.classList.add("st-badge", "st-badge--error");
        rendered.append(title, value);
      }
    }
    values.replaceChildren(rendered);
  };
})();
