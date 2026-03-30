"""Serves a local web dashboard to visualize experiment results."""
from __future__ import annotations

import http.server
import json
import os
import webbrowser
from pathlib import Path

RESULTS_DIR = Path("results")
PORT = 8050


def load_results() -> list[dict]:
    records = []
    for path in sorted(RESULTS_DIR.glob("*.jsonl")):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def build_dashboard() -> str:
    records = load_results()
    data_json = json.dumps(records)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-Agent Experiment Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #e0e0e0; padding: 24px; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 8px; color: #fff; }}
  .subtitle {{ color: #888; margin-bottom: 24px; font-size: 0.9rem; }}
  .kpi-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
  .kpi {{ background: #1a1d27; border-radius: 10px; padding: 20px; text-align: center; border: 1px solid #2a2d37; }}
  .kpi .value {{ font-size: 2rem; font-weight: 700; color: #60a5fa; }}
  .kpi .label {{ font-size: 0.8rem; color: #888; margin-top: 4px; }}
  .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; margin-bottom: 24px; }}
  .chart-card {{ background: #1a1d27; border-radius: 10px; padding: 20px; border: 1px solid #2a2d37; }}
  .chart-card h3 {{ font-size: 0.95rem; margin-bottom: 12px; color: #ccc; }}
  canvas {{ max-height: 320px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #2a2d37; }}
  th {{ color: #888; font-weight: 600; background: #1a1d27; position: sticky; top: 0; }}
  td {{ color: #ccc; }}
  tr.clickable {{ cursor: pointer; }}
  tr.clickable:hover {{ background: #1e2230; }}
  tr.selected {{ background: #1e2230; }}
  .pass {{ color: #34d399; font-weight: 600; }}
  .fail {{ color: #f87171; font-weight: 600; }}
  .table-card {{ background: #1a1d27; border-radius: 10px; padding: 20px; border: 1px solid #2a2d37; overflow-x: auto; }}
  .table-card h3 {{ font-size: 0.95rem; margin-bottom: 12px; color: #ccc; }}
  .filters {{ display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }}
  .filters select {{ background: #1a1d27; color: #ccc; border: 1px solid #2a2d37; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; }}
  #detailPanel {{ background: #1a1d27; border-radius: 10px; padding: 20px; border: 1px solid #2a2d37; margin-top: 20px; display: none; }}
  #detailPanel.visible {{ display: block; }}
  #detailPanel h3 {{ font-size: 0.95rem; margin-bottom: 16px; color: #ccc; }}
  .detail-close {{ background: none; border: 1px solid #444; color: #888; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }}
  .detail-close:hover {{ color: #fff; border-color: #666; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-bottom: 16px; }}
  .meta-item {{ background: #0f1117; border-radius: 6px; padding: 8px 12px; }}
  .meta-label {{ font-size: 0.7rem; color: #666; }}
  .meta-value {{ font-size: 0.9rem; color: #ccc; font-weight: 600; }}
  .section-title {{ font-size: 0.85rem; color: #60a5fa; margin: 16px 0 8px 0; }}
  .code-block {{ background: #0f1117; border: 1px solid #2a2d37; border-radius: 6px; padding: 12px; font-size: 0.78rem; font-family: 'SF Mono', Monaco, Consolas, monospace; line-height: 1.5; overflow-x: auto; max-height: 400px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; }}
  .error-text {{ color: #f87171; }}
  .trace-flow {{ display: flex; flex-direction: column; gap: 12px; }}
  .trace-msg {{ background: #0f1117; border: 1px solid #2a2d37; border-radius: 8px; padding: 12px 16px; position: relative; }}
  .trace-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
  .trace-agents {{ font-size: 0.8rem; font-weight: 600; }}
  .trace-from {{ color: #60a5fa; }}
  .trace-arrow {{ color: #555; margin: 0 6px; }}
  .trace-to {{ color: #f59e0b; }}
  .trace-tokens {{ font-size: 0.7rem; color: #555; }}
  .trace-content {{ font-size: 0.78rem; font-family: 'SF Mono', Monaco, Consolas, monospace; line-height: 1.5; color: #aaa; white-space: pre-wrap; word-break: break-word; max-height: 200px; overflow-y: auto; }}
  .trace-toggle {{ background: none; border: 1px solid #333; color: #888; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 0.7rem; margin-left: 8px; }}
  .trace-toggle:hover {{ color: #ccc; border-color: #555; }}
  .trace-connector {{ width: 2px; height: 12px; background: #2a2d37; margin-left: 24px; }}
</style>
</head>
<body>

<h1>Multi-Agent Architecture Experiment</h1>
<p class="subtitle">TestEval Benchmark Results Dashboard</p>

<div class="filters">
  <select id="modelFilter" onchange="refresh()"><option value="all">All Models</option></select>
  <select id="archFilter" onchange="refresh()"><option value="all">All Architectures</option></select>
  <select id="runFilter" onchange="refresh()"><option value="all">All Runs</option></select>
</div>

<div class="kpi-row" id="kpis"></div>
<div class="chart-grid" id="charts"></div>
<div class="table-card" id="tableSection"></div>
<div id="detailPanel"></div>

<script>
const RAW_DATA = {data_json};

const ARCH_COLORS = {{
  single_agent: '#60a5fa',
  sequential: '#f59e0b',
  hierarchical: '#34d399',
}};
const ARCH_LABELS = {{
  single_agent: 'Single Agent',
  sequential: 'Sequential',
  hierarchical: 'Hierarchical',
}};

let charts = {{}};
let selectedRow = null;

function populateFilters() {{
  const models = [...new Set(RAW_DATA.map(r => r.model_display_name))];
  const archs = [...new Set(RAW_DATA.map(r => r.architecture))].sort();
  const runs = [...new Set(RAW_DATA.map(r => r.run_number))].sort();
  const mSel = document.getElementById('modelFilter');
  models.forEach(m => {{ const o = document.createElement('option'); o.value = m; o.textContent = m; mSel.appendChild(o); }});
  const aSel = document.getElementById('archFilter');
  archs.forEach(a => {{ const o = document.createElement('option'); o.value = a; o.textContent = ARCH_LABELS[a] || a; aSel.appendChild(o); }});
  const rSel = document.getElementById('runFilter');
  runs.forEach(r => {{ const o = document.createElement('option'); o.value = r; o.textContent = 'Run ' + r; rSel.appendChild(o); }});
}}

function getFiltered() {{
  const model = document.getElementById('modelFilter').value;
  const arch = document.getElementById('archFilter').value;
  const run = document.getElementById('runFilter').value;
  return RAW_DATA.filter(r =>
    (model === 'all' || r.model_display_name === model) &&
    (arch === 'all' || r.architecture === arch) &&
    (run === 'all' || r.run_number === parseInt(run))
  );
}}

function groupBy(data, key) {{
  const groups = {{}};
  data.forEach(r => {{
    const k = r[key];
    if (!groups[k]) groups[k] = [];
    groups[k].push(r);
  }});
  return groups;
}}

function avg(arr) {{ return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0; }}
function total(arr) {{ return arr.reduce((a, b) => a + b, 0); }}

function renderKPIs(data) {{
  const el = document.getElementById('kpis');
  el.textContent = '';
  const totalCount = data.length;
  const passed = data.filter(r => r.coverage && r.coverage.passed).length;
  const totalTokens = total(data.map(r => (r.metrics ? r.metrics.total_input_tokens + r.metrics.total_output_tokens : 0)));
  const totalCost = total(data.map(r => r.metrics ? r.metrics.estimated_cost_usd : 0));
  const avgLatency = avg(data.map(r => r.metrics ? r.metrics.end_to_end_latency_s : 0));
  const passedRecs = data.filter(r => r.coverage && r.coverage.passed);
  const avgCov = avg(passedRecs.map(r => r.coverage.line_coverage));

  const items = [
    [totalCount, 'Total Tasks'],
    [passed + '/' + totalCount, 'Pass Rate (' + (totalCount ? Math.round(passed/totalCount*100) : 0) + '%)'],
    [totalTokens.toLocaleString(), 'Total Tokens'],
    ['$' + totalCost.toFixed(2), 'Total Cost'],
    [avgLatency.toFixed(1) + 's', 'Avg Latency'],
    [(avgCov * 100).toFixed(1) + '%', 'Avg Line Coverage (passed)'],
  ];
  items.forEach(([val, label]) => {{
    const card = document.createElement('div');
    card.className = 'kpi';
    const vDiv = document.createElement('div');
    vDiv.className = 'value';
    vDiv.textContent = val;
    const lDiv = document.createElement('div');
    lDiv.className = 'label';
    lDiv.textContent = label;
    card.appendChild(vDiv);
    card.appendChild(lDiv);
    el.appendChild(card);
  }});
}}

function destroyCharts() {{
  Object.values(charts).forEach(c => c.destroy());
  charts = {{}};
}}

function makeChart(id, config) {{
  const canvas = document.getElementById(id);
  charts[id] = new Chart(canvas.getContext('2d'), config);
}}

function buildChartCards() {{
  const container = document.getElementById('charts');
  container.textContent = '';
  const chartDefs = [
    ['c1', 'Pass Rate by Architecture'],
    ['c2', 'Avg Token Usage by Architecture'],
    ['c3', 'Avg Latency by Architecture (seconds)'],
    ['c4', 'Avg Line Coverage by Architecture'],
    ['c5', 'Avg Cost per Task by Architecture'],
    ['c6', 'Avg Agent Turns by Architecture'],
    ['c7', 'Pass Rate by Difficulty'],
    ['c8', 'Cost vs Coverage Scatter'],
  ];
  chartDefs.forEach(([id, title]) => {{
    const card = document.createElement('div');
    card.className = 'chart-card';
    const h3 = document.createElement('h3');
    h3.textContent = title;
    const canvas = document.createElement('canvas');
    canvas.id = id;
    card.appendChild(h3);
    card.appendChild(canvas);
    container.appendChild(card);
  }});
}}

function renderCharts(data) {{
  destroyCharts();
  const byArch = groupBy(data, 'architecture');
  const archs = Object.keys(byArch).sort();
  buildChartCards();

  const labels = archs.map(a => ARCH_LABELS[a] || a);
  const colors = archs.map(a => ARCH_COLORS[a] || '#888');

  makeChart('c1', {{
    type: 'bar',
    data: {{ labels, datasets: [{{ label: 'Pass Rate %', data: archs.map(a => {{
      const recs = byArch[a]; return Math.round(recs.filter(r => r.coverage && r.coverage.passed).length / recs.length * 100);
    }}), backgroundColor: colors }}] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, max: 100, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
  }});

  makeChart('c2', {{
    type: 'bar',
    data: {{ labels, datasets: [
      {{ label: 'Input Tokens', data: archs.map(a => Math.round(avg(byArch[a].map(r => r.metrics ? r.metrics.total_input_tokens : 0)))), backgroundColor: colors.map(c => c + '99') }},
      {{ label: 'Output Tokens', data: archs.map(a => Math.round(avg(byArch[a].map(r => r.metrics ? r.metrics.total_output_tokens : 0)))), backgroundColor: colors }},
    ] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, stacked: true, ticks: {{ color: '#888' }} }}, x: {{ stacked: true, ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#888' }} }} }} }}
  }});

  makeChart('c3', {{
    type: 'bar',
    data: {{ labels, datasets: [{{ label: 'Avg Latency (s)', data: archs.map(a => parseFloat(avg(byArch[a].map(r => r.metrics ? r.metrics.end_to_end_latency_s : 0)).toFixed(1))), backgroundColor: colors }}] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
  }});

  makeChart('c4', {{
    type: 'bar',
    data: {{ labels, datasets: [{{ label: 'Avg Line Coverage %', data: archs.map(a => {{
      const passed = byArch[a].filter(r => r.coverage && r.coverage.passed);
      return passed.length ? parseFloat((avg(passed.map(r => r.coverage.line_coverage)) * 100).toFixed(1)) : 0;
    }}), backgroundColor: colors }}] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, max: 100, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
  }});

  makeChart('c5', {{
    type: 'bar',
    data: {{ labels, datasets: [{{ label: 'Avg Cost ($)', data: archs.map(a => parseFloat(avg(byArch[a].map(r => r.metrics ? r.metrics.estimated_cost_usd : 0)).toFixed(4))), backgroundColor: colors }}] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
  }});

  makeChart('c6', {{
    type: 'bar',
    data: {{ labels, datasets: [{{ label: 'Avg Agent Turns', data: archs.map(a => parseFloat(avg(byArch[a].map(r => r.metrics ? r.metrics.agent_turns : 0)).toFixed(1))), backgroundColor: colors }}] }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ display: false }} }} }}
  }});

  const difficulties = [...new Set(data.map(r => r.difficulty))].sort();
  makeChart('c7', {{
    type: 'bar',
    data: {{
      labels: difficulties.map(d => 'Difficulty ' + d),
      datasets: archs.map((a, i) => ({{
        label: ARCH_LABELS[a] || a,
        data: difficulties.map(d => {{
          const recs = byArch[a] ? byArch[a].filter(r => r.difficulty === d) : [];
          return recs.length ? Math.round(recs.filter(r => r.coverage && r.coverage.passed).length / recs.length * 100) : 0;
        }}),
        backgroundColor: colors[i],
      }})),
    }},
    options: {{ responsive: true, scales: {{ y: {{ beginAtZero: true, max: 100, ticks: {{ color: '#888' }} }}, x: {{ ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#888' }} }} }} }}
  }});

  const scatterData = archs.map((a, i) => ({{
    label: ARCH_LABELS[a] || a,
    data: byArch[a].filter(r => r.coverage && r.coverage.passed).map(r => ({{
      x: r.metrics ? r.metrics.estimated_cost_usd : 0,
      y: (r.coverage.line_coverage || 0) * 100,
    }})),
    backgroundColor: colors[i],
    pointRadius: 4,
  }}));
  makeChart('c8', {{
    type: 'scatter',
    data: {{ datasets: scatterData }},
    options: {{ responsive: true, scales: {{ x: {{ title: {{ display: true, text: 'Cost ($)', color: '#888' }}, ticks: {{ color: '#888' }} }}, y: {{ title: {{ display: true, text: 'Line Coverage %', color: '#888' }}, beginAtZero: true, max: 100, ticks: {{ color: '#888' }} }} }}, plugins: {{ legend: {{ labels: {{ color: '#888' }} }} }} }}
  }});
}}

function showDetail(record) {{
  const panel = document.getElementById('detailPanel');
  panel.textContent = '';

  const passed = record.coverage && record.coverage.passed;
  const cov = record.coverage || {{}};
  const m = record.metrics || {{}};
  const taskId = record.task_id || record.task_title || '';

  // Header
  const headerDiv = document.createElement('div');
  headerDiv.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px';
  const h3 = document.createElement('h3');
  h3.textContent = 'Task Detail: ' + taskId;
  const closeBtn = document.createElement('button');
  closeBtn.className = 'detail-close';
  closeBtn.textContent = 'Close';
  closeBtn.onclick = hideDetail;
  headerDiv.appendChild(h3);
  headerDiv.appendChild(closeBtn);
  panel.appendChild(headerDiv);

  // Meta grid
  const metaGrid = document.createElement('div');
  metaGrid.className = 'meta-grid';
  const metaItems = [
    ['Status', passed ? 'PASS' : 'FAIL', passed ? 'pass' : 'fail'],
    ['Architecture', ARCH_LABELS[record.architecture] || record.architecture],
    ['Model', record.model_display_name || ''],
    ['Run', record.run_number || ''],
    ['Tokens', ((m.total_input_tokens || 0) + (m.total_output_tokens || 0)).toLocaleString()],
    ['Cost', '$' + (m.estimated_cost_usd || 0).toFixed(4)],
    ['Latency', (m.end_to_end_latency_s || 0).toFixed(1) + 's'],
    ['Agent Turns', m.agent_turns || 0],
    ['Retries', record.retry_count || 0],
  ];
  if (passed) {{
    metaItems.push(['Line Coverage', ((cov.line_coverage || 0) * 100).toFixed(1) + '%']);
    metaItems.push(['Branch Coverage', ((cov.branch_coverage || 0) * 100).toFixed(1) + '%']);
  }}
  metaItems.forEach(([label, value, cls]) => {{
    const item = document.createElement('div');
    item.className = 'meta-item';
    const lbl = document.createElement('div');
    lbl.className = 'meta-label';
    lbl.textContent = label;
    const val = document.createElement('div');
    val.className = 'meta-value' + (cls ? ' ' + cls : '');
    val.textContent = value;
    item.appendChild(lbl);
    item.appendChild(val);
    metaGrid.appendChild(item);
  }});
  panel.appendChild(metaGrid);

  // Error output
  if (!passed && cov.error_message) {{
    const errTitle = document.createElement('div');
    errTitle.className = 'section-title';
    errTitle.textContent = 'Error Output';
    panel.appendChild(errTitle);
    const errPre = document.createElement('pre');
    errPre.className = 'code-block error-text';
    errPre.textContent = cov.error_message;
    panel.appendChild(errPre);
  }}

  // Agent trace
  const traces = record.agent_trace || [];
  if (traces.length > 0) {{
    const traceTitle = document.createElement('div');
    traceTitle.className = 'section-title';
    traceTitle.textContent = 'Agent Interactions (' + traces.length + ' messages)';
    panel.appendChild(traceTitle);

    const flow = document.createElement('div');
    flow.className = 'trace-flow';

    traces.forEach((t, idx) => {{
      const msg = document.createElement('div');
      msg.className = 'trace-msg';

      const header = document.createElement('div');
      header.className = 'trace-header';

      const agents = document.createElement('span');
      agents.className = 'trace-agents';
      const fromSpan = document.createElement('span');
      fromSpan.className = 'trace-from';
      fromSpan.textContent = t.from_agent;
      const arrow = document.createElement('span');
      arrow.className = 'trace-arrow';
      arrow.textContent = ' -> ';
      const toSpan = document.createElement('span');
      toSpan.className = 'trace-to';
      toSpan.textContent = t.to_agent;
      agents.appendChild(fromSpan);
      agents.appendChild(arrow);
      agents.appendChild(toSpan);

      const tokenInfo = document.createElement('span');
      tokenInfo.className = 'trace-tokens';
      tokenInfo.textContent = (t.input_tokens || 0).toLocaleString() + ' in / ' + (t.output_tokens || 0).toLocaleString() + ' out';

      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'trace-toggle';
      toggleBtn.textContent = 'expand';

      header.appendChild(agents);
      const rightSide = document.createElement('span');
      rightSide.appendChild(tokenInfo);
      rightSide.appendChild(toggleBtn);
      header.appendChild(rightSide);
      msg.appendChild(header);

      const contentDiv = document.createElement('div');
      contentDiv.className = 'trace-content';
      const fullText = t.content || '';
      const preview = fullText.length > 300 ? fullText.slice(0, 300) + '...' : fullText;
      contentDiv.textContent = preview;
      msg.appendChild(contentDiv);

      let expanded = false;
      toggleBtn.onclick = function(e) {{
        e.stopPropagation();
        expanded = !expanded;
        contentDiv.textContent = expanded ? fullText : preview;
        contentDiv.style.maxHeight = expanded ? '600px' : '200px';
        toggleBtn.textContent = expanded ? 'collapse' : 'expand';
      }};

      flow.appendChild(msg);

      if (idx < traces.length - 1) {{
        const connector = document.createElement('div');
        connector.className = 'trace-connector';
        flow.appendChild(connector);
      }}
    }});

    panel.appendChild(flow);
  }}

  // Generated test code
  if (record.generated_tests) {{
    const codeTitle = document.createElement('div');
    codeTitle.className = 'section-title';
    codeTitle.textContent = 'Generated Test Code';
    panel.appendChild(codeTitle);
    const codePre = document.createElement('pre');
    codePre.className = 'code-block';
    codePre.textContent = record.generated_tests;
    panel.appendChild(codePre);
  }}

  panel.className = 'visible';
  panel.style.display = 'block';
  panel.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
}}

function hideDetail() {{
  const panel = document.getElementById('detailPanel');
  panel.style.display = 'none';
  if (selectedRow) {{ selectedRow.classList.remove('selected'); selectedRow = null; }}
}}

function renderTable(data) {{
  const section = document.getElementById('tableSection');
  section.textContent = '';

  const h3 = document.createElement('h3');
  h3.textContent = 'Detailed Results (click a row to inspect)';
  section.appendChild(h3);

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  ['Task', 'Title', 'Architecture', 'Model', 'Run', 'Status', 'Line Cov', 'Tokens', 'Cost', 'Latency', 'Retries'].forEach(text => {{
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.appendChild(th);
  }});
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  const sorted = [...data].sort((a, b) => {{
    const aId = a.task_id || a.task_title || '';
    const bId = b.task_id || b.task_title || '';
    return aId.localeCompare(bId) || a.architecture.localeCompare(b.architecture);
  }});

  sorted.forEach((r) => {{
    const tr = document.createElement('tr');
    tr.className = 'clickable';
    tr.onclick = function() {{
      if (selectedRow) selectedRow.classList.remove('selected');
      tr.classList.add('selected');
      selectedRow = tr;
      showDetail(r);
    }};
    const passed = r.coverage && r.coverage.passed;
    const tokens = r.metrics ? r.metrics.total_input_tokens + r.metrics.total_output_tokens : 0;
    const taskId = r.task_id || '';
    const cells = [
      taskId.length > 30 ? taskId.slice(0, 30) + '...' : taskId,
      (r.task_title || '').length > 40 ? (r.task_title || '').slice(0, 40) + '...' : (r.task_title || ''),
      ARCH_LABELS[r.architecture] || r.architecture,
      r.model_display_name,
      r.run_number,
      passed ? 'PASS' : 'FAIL',
      passed ? (r.coverage.line_coverage * 100).toFixed(1) + '%' : '-',
      tokens.toLocaleString(),
      '$' + (r.metrics ? r.metrics.estimated_cost_usd : 0).toFixed(4),
      (r.metrics ? r.metrics.end_to_end_latency_s : 0).toFixed(1) + 's',
      r.retry_count || 0,
    ];
    cells.forEach((val, cidx) => {{
      const td = document.createElement('td');
      td.textContent = val;
      if (cidx === 5) td.className = passed ? 'pass' : 'fail';
      tr.appendChild(td);
    }});
    tbody.appendChild(tr);
  }});

  table.appendChild(tbody);
  section.appendChild(table);
}}

function refresh() {{
  const data = getFiltered();
  renderKPIs(data);
  renderCharts(data);
  renderTable(data);
  hideDetail();
}}

populateFilters();
refresh();
</script>
</body>
</html>""";


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            html = build_dashboard()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def main():
    if not any(RESULTS_DIR.glob("*.jsonl")):
        print(f"No result files found in {RESULTS_DIR}/")
        return

    records = load_results()
    print(f"Loaded {len(records)} records from {RESULTS_DIR}/")
    print(f"Dashboard: http://localhost:{PORT}")
    print("Press Ctrl+C to stop")

    webbrowser.open(f"http://localhost:{PORT}")

    server = http.server.HTTPServer(("", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
        server.server_close()


if __name__ == "__main__":
    main()
