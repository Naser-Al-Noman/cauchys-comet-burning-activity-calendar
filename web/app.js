const DATA_URL = "./data/demo_calendar.json";

function $(id) {
  return document.getElementById(id);
}

function formatNumber(n) {
  return Math.round(Number(n)).toLocaleString("en-US");
}

function renderBaseline(baseline) {
  const chart = $("baseline-chart");
  chart.innerHTML = "";
  const max = Math.max(...baseline.map((d) => Number(d.p50)), 1);

  for (const row of baseline.filter((d) => d.enough_years !== false || d.years_used > 1)) {
    const fill = document.createElement("div");
    fill.className = "bar-fill";

    const track = document.createElement("div");
    track.className = "bar-track";
    track.appendChild(fill);

    const label = document.createElement("span");
    label.textContent = `Week ${row.iso_week}`;

    const value = document.createElement("span");
    value.textContent = formatNumber(row.p50);

    const wrap = document.createElement("div");
    wrap.className = "bar-row";
    wrap.append(label, track, value);
    chart.appendChild(wrap);

    requestAnimationFrame(() => {
      fill.style.width = `${(100 * Number(row.p50)) / max}%`;
    });
  }
}

function renderYearControls(years, selected, onSelect) {
  const host = $("year-controls");
  host.innerHTML = "";
  for (const year of years) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = String(year);
    btn.setAttribute("aria-pressed", year === selected ? "true" : "false");
    btn.addEventListener("click", () => onSelect(year));
    host.appendChild(btn);
  }
}

function renderAnomalies(weeks, year) {
  const chart = $("anomaly-chart");
  chart.innerHTML = "";
  const rows = weeks
    .filter((w) => Number(w.iso_year) === Number(year))
    .sort((a, b) => Number(a.iso_week) - Number(b.iso_week));

  const maxAbs = Math.max(...rows.map((r) => Math.abs(Number(r.anomaly_score))), 1);

  for (const row of rows) {
    const score = Number(row.anomaly_score);
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    if (score > 0.5) fill.classList.add("is-anomaly-high");
    if (score < -0.5) fill.classList.add("is-anomaly-low");

    const track = document.createElement("div");
    track.className = "bar-track";
    track.appendChild(fill);

    const label = document.createElement("span");
    label.textContent = `Week ${row.iso_week}`;

    const value = document.createElement("span");
    value.textContent = score.toFixed(2);

    const wrap = document.createElement("div");
    wrap.className = "bar-row";
    wrap.append(label, track, value);
    chart.appendChild(wrap);

    requestAnimationFrame(() => {
      fill.style.width = `${(100 * Math.abs(score)) / maxAbs}%`;
    });
  }
}

function renderCritical(critical) {
  const list = $("critical-list");
  list.innerHTML = "";
  for (const row of critical) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>#${row.critical_rank} · ISO week ${row.iso_week}</strong><span>median ${formatNumber(row.p50)}</span>`;
    list.appendChild(li);
  }
}

function renderPeaks(peaks) {
  const list = $("peak-list");
  list.innerHTML = "";
  for (const row of peaks) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${row.iso_year}</strong><span>peak week ${row.peak_iso_week} · ${formatNumber(row.peak_regional_active_cell_days)}</span>`;
    list.appendChild(li);
  }
  const slope = peaks[0]?.peak_week_slope_per_year;
  const slopeEl = $("peak-slope");
  if (slope == null || Number.isNaN(Number(slope))) {
    slopeEl.textContent = "Peak-timing slope not available for this extract.";
  } else {
    const direction =
      Number(slope) < -0.05 ? "earlier" : Number(slope) > 0.05 ? "later" : "little net change";
    slopeEl.textContent = `Descriptive peak ISO-week slope: ${Number(slope).toFixed(2)} weeks/year (${direction} over this March-only window). Not a climate attribution.`;
  }
}

async function main() {
  const status = $("status-line");
  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error(`Could not load ${DATA_URL}`);
    const data = await res.json();

    status.textContent = data.meta?.status || "Demo data loaded.";
    if (data.meta?.data_credit) {
      $("credit").textContent = data.meta.data_credit;
    }

    const years = (data.meta?.years || []).map(Number).sort((a, b) => a - b);
    let selected = years[years.length - 1];

    renderBaseline(data.baseline || []);
    renderCritical(data.critical_periods || []);
    renderPeaks(data.peak_timing || []);

    const refresh = (year) => {
      selected = year;
      renderYearControls(years, selected, refresh);
      renderAnomalies(data.weeks || [], selected);
    };
    refresh(selected);
  } catch (err) {
    status.classList.add("error");
    status.textContent =
      "Could not load demo data. Serve the web/ folder over HTTP (file:// blocks fetch).";
    console.error(err);
  }
}

main();
