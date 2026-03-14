/* ============================================================
   GPU WRANGLER - app.js
   Vanilla JS control panel for ML training runs
   Polls API endpoints with graceful fallback to demo data
   ============================================================ */

(function () {
  'use strict';

  // ---- Config ----
  const API_BASE = '';  // same origin
  const POLL_INTERVAL = 3000;
  const CHART_HISTORY = 200;

  // ---- State ----
  let apiConnected = false;
  let gpuState = null;
  let runsState = [];
  let servicesState = [];
  let lossHistory = { train: [], val: [], steps: [] };
  let sortCol = 'id';
  let sortDir = 'desc';
  let meterAnimations = { util: 0, vram: 0, temp: 0, power: 0, fan: 0 };
  let meterTargets   = { util: 0, vram: 0, temp: 0, power: 0, fan: 0 };

  // ---- Demo data ----
  const DEMO_GPU = {
    name: 'NVIDIA RTX 4090',
    utilization: 73,
    vram_used: 18.2,
    vram_total: 24.0,
    temperature: 67,
    power_draw: 285,
    power_limit: 450,
    fan_speed: 62,
    driver: '550.54.14',
    cuda: '12.4'
  };

  const DEMO_SERVICES = [
    { name: 'TensorBoard', port: 6006, status: 'up', url: '/tensorboard/' },
    { name: 'Jupyter',     port: 8080, status: 'up', url: '/jupyter/' },
    { name: 'Streamlit',   port: 1111, status: 'down', url: '/streamlit/' },
    { name: 'API Server',  port: 19842, status: 'up', url: '/' },
    { name: 'SSH',         port: 22,    status: 'up', url: null },
    { name: 'VS Code',     port: 8443,  status: 'down', url: null }
  ];

  const DEMO_RUNS = [
    { id: 'run-042', name: 'rna3d_gcbias_sweep', status: 'running', epochs: '34/50', best_loss: 0.0342, duration: '2h 14m', started: '2026-03-14 09:22', params: { gc_bias: 0.45, max_depth: 8 } },
    { id: 'run-041', name: 'rna3d_baseline_v3',  status: 'complete', epochs: '50/50', best_loss: 0.0289, duration: '3h 02m', started: '2026-03-13 22:10', params: {} },
    { id: 'run-040', name: 'rna3d_wobble_test',  status: 'failed',  epochs: '12/50', best_loss: 0.1205, duration: '0h 44m', started: '2026-03-13 18:30', params: {} },
    { id: 'run-039', name: 'rna3d_deep_model',   status: 'complete', epochs: '100/100', best_loss: 0.0198, duration: '6h 18m', started: '2026-03-13 10:00', params: {} },
    { id: 'run-038', name: 'rna3d_quick_sanity', status: 'complete', epochs: '10/10', best_loss: 0.0891, duration: '0h 22m', started: '2026-03-12 15:45', params: {} },
    { id: 'run-037', name: 'rna3d_lr_search',    status: 'complete', epochs: '30/30', best_loss: 0.0312, duration: '1h 50m', started: '2026-03-12 08:00', params: {} },
  ];

  const DEMO_NOTEBOOKS = [
    { name: '01_data_preprocessing.ipynb',     cells: 42, last_run: '2026-03-13 14:00', status: 'clean' },
    { name: '02_rna_3d_training_filled.ipynb',  cells: 68, last_run: '2026-03-14 08:30', status: 'dirty' },
    { name: '03_evaluation_metrics.ipynb',      cells: 35, last_run: '2026-03-12 16:00', status: 'clean' },
    { name: '04_structure_visualization.ipynb',  cells: 28, last_run: '2026-03-11 20:00', status: 'clean' },
    { name: '05_hyperparameter_analysis.ipynb',  cells: 55, last_run: '2026-03-13 22:00', status: 'dirty' },
    { name: '06_ablation_studies.ipynb',         cells: 39, last_run: '2026-03-10 12:00', status: 'clean' },
  ];

  // ---- Presets ----
  const PRESETS = {
    default: { gc_bias: 0.5, max_depth: 6, wobble_p: 0.1, n_samples: 10000, n_epochs: 50 },
    quick:   { gc_bias: 0.5, max_depth: 4, wobble_p: 0.05, n_samples: 2000, n_epochs: 10 },
    full:    { gc_bias: 0.45, max_depth: 12, wobble_p: 0.15, n_samples: 50000, n_epochs: 200 },
    sweep:   { gc_bias: 0.5, max_depth: 8, wobble_p: 0.1, n_samples: 20000, n_epochs: 100 },
  };

  // ---- Utilities ----
  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  async function apiFetch(path) {
    try {
      const res = await fetch(API_BASE + path, { signal: AbortSignal.timeout(2000) });
      if (!res.ok) throw new Error(res.status);
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  function setConnected(connected) {
    apiConnected = connected;
    const dot = $('#connDot');
    const label = $('#connLabel');
    if (connected) {
      dot.classList.add('connected');
      label.textContent = 'Online';
    } else {
      dot.classList.remove('connected');
      label.textContent = 'Demo Mode';
    }
  }

  // ---- Clock ----
  function tickClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    $('#clock').textContent = `${h}:${m}:${s}`;
  }

  // ---- Meter Drawing ----
  function drawMeter(canvasId, value, maxVal, unit, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const cy = H - 10;
    const r = Math.min(W, H) - 30;

    ctx.clearRect(0, 0, W, H);

    // Meter arc background
    ctx.beginPath();
    ctx.arc(cx, cy, r, Math.PI, 0, false);
    ctx.lineWidth = 16;
    ctx.strokeStyle = '#1a1e28';
    ctx.stroke();

    // Colored zone arcs
    const startAngle = Math.PI;
    // Green zone 0-60%
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, startAngle + Math.PI * 0.6, false);
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(61, 214, 140, 0.15)';
    ctx.stroke();
    // Amber zone 60-85%
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle + Math.PI * 0.6, startAngle + Math.PI * 0.85, false);
    ctx.strokeStyle = 'rgba(232, 160, 32, 0.15)';
    ctx.stroke();
    // Red zone 85-100%
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle + Math.PI * 0.85, startAngle + Math.PI, false);
    ctx.strokeStyle = 'rgba(224, 80, 80, 0.15)';
    ctx.stroke();

    // Active arc
    const pct = Math.min(value / maxVal, 1);
    const activeAngle = startAngle + Math.PI * pct;
    const arcColor = pct > 0.85 ? '#e05050' : pct > 0.6 ? '#e8a020' : '#3dd68c';
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, activeAngle, false);
    ctx.lineWidth = 8;
    ctx.strokeStyle = arcColor;
    ctx.shadowColor = arcColor;
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Tick marks
    for (let i = 0; i <= 10; i++) {
      const angle = startAngle + (Math.PI * i / 10);
      const inner = r - 20;
      const outer = r + 12;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(angle) * inner, cy + Math.sin(angle) * inner);
      ctx.lineTo(cx + Math.cos(angle) * outer, cy + Math.sin(angle) * outer);
      ctx.lineWidth = i % 5 === 0 ? 2 : 1;
      ctx.strokeStyle = i % 5 === 0 ? '#4a4e58' : '#2a2e38';
      ctx.stroke();
    }

    // Needle
    const needleAngle = startAngle + Math.PI * pct;
    const needleLen = r - 8;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(needleAngle) * needleLen, cy + Math.sin(needleAngle) * needleLen);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#e8ecf4';
    ctx.shadowColor = 'rgba(232, 236, 244, 0.4)';
    ctx.shadowBlur = 4;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Center dot
    ctx.beginPath();
    ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#3a3e48';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, 3, 0, Math.PI * 2);
    ctx.fillStyle = '#5a5e68';
    ctx.fill();
  }

  function animateMeters() {
    const ease = 0.08;
    let changed = false;
    for (const key of Object.keys(meterAnimations)) {
      const diff = meterTargets[key] - meterAnimations[key];
      if (Math.abs(diff) > 0.1) {
        meterAnimations[key] += diff * ease;
        changed = true;
      } else {
        meterAnimations[key] = meterTargets[key];
      }
    }

    const gpu = gpuState || DEMO_GPU;
    drawMeter('meterUtil', meterAnimations.util, 100, '%', '#3dd68c');
    drawMeter('meterVram', meterAnimations.vram, gpu.vram_total, 'GB', '#3dd68c');
    drawMeter('meterTemp', meterAnimations.temp, 100, 'C', '#3dd68c');
    drawMeter('meterPower', meterAnimations.power, gpu.power_limit || 450, 'W', '#3dd68c');
    drawMeter('meterFan', meterAnimations.fan, 100, '%', '#3dd68c');

    requestAnimationFrame(animateMeters);
  }

  function updateMeterValues(gpu) {
    meterTargets.util  = gpu.utilization;
    meterTargets.vram  = gpu.vram_used;
    meterTargets.temp  = gpu.temperature;
    meterTargets.power = gpu.power_draw;
    meterTargets.fan   = gpu.fan_speed;

    const pctUtil = gpu.utilization / 100;
    const pctVram = gpu.vram_used / gpu.vram_total;
    const pctTemp = gpu.temperature / 100;

    const valUtil = $('#valUtil');
    const valVram = $('#valVram');
    const valTemp = $('#valTemp');
    const valPower = $('#valPower');
    const valFan = $('#valFan');

    valUtil.textContent = `${gpu.utilization}%`;
    valUtil.className = 'meter-value' + (pctUtil > 0.85 ? ' danger' : pctUtil > 0.6 ? ' warning' : '');

    valVram.textContent = `${gpu.vram_used.toFixed(1)} / ${gpu.vram_total.toFixed(1)} GB`;
    valVram.className = 'meter-value' + (pctVram > 0.9 ? ' danger' : pctVram > 0.7 ? ' warning' : '');

    valTemp.innerHTML = `${gpu.temperature}&deg;C`;
    valTemp.className = 'meter-value' + (pctTemp > 0.85 ? ' danger' : pctTemp > 0.7 ? ' warning' : '');

    valPower.textContent = `${gpu.power_draw} W`;
    valFan.textContent = `${gpu.fan_speed}%`;

    $('#gpuName').textContent = `${gpu.name}  |  Driver ${gpu.driver || '???'}  |  CUDA ${gpu.cuda || '???'}`;
  }

  // ---- Services ----
  function renderServices(services) {
    const grid = $('#servicesGrid');
    grid.innerHTML = services.map(s => `
      <div class="service-card">
        <div class="service-card-header">
          <span class="service-name">${s.name}</span>
          <span class="led ${s.status === 'up' ? 'led-green' : 'led-red'}"></span>
        </div>
        <div class="service-port">:${s.port}</div>
        <div class="service-status-text ${s.status === 'up' ? 'up' : 'down'}">
          ${s.status === 'up' ? 'Operational' : 'Offline'}
        </div>
        ${s.url && s.status === 'up' ? `<a href="${s.url}" target="_blank" style="font-size:0.7rem; color:var(--blue); text-decoration:none;">Open &rarr;</a>` : ''}
      </div>
    `).join('');
  }

  // ---- Active Runs ----
  function renderActiveRuns(runs) {
    const active = runs.filter(r => r.status === 'running');
    const body = $('#activeRunsBody');

    if (active.length === 0) {
      body.innerHTML = '<div class="empty-state"><div class="icon">&#9881;</div>No active training runs</div>';
      return;
    }

    body.innerHTML = active.map(r => `
      <div class="active-run">
        <div class="active-run-header">
          <div class="active-run-name">
            <span class="led led-green" style="animation: pulse-led 1s ease-in-out infinite;"></span>
            ${r.name}
          </div>
          <span class="active-run-time">${r.started}</span>
        </div>
        <div style="margin-bottom:8px;">
          <div style="height:4px; background:var(--bg-inset); border-radius:2px; border:1px solid var(--border-steel); overflow:hidden;">
            <div style="height:100%; width:${parseEpochPct(r.epochs)}%; background:var(--green); border-radius:2px; box-shadow: 0 0 6px var(--green-glow); transition: width 0.5s;"></div>
          </div>
          <div style="display:flex; justify-content:space-between; margin-top:4px; font-size:0.7rem; color:var(--text-dim);">
            <span>Epoch ${r.epochs}</span>
            <span>${r.duration}</span>
          </div>
        </div>
        <div class="active-run-stats">
          <div class="stat-item"><span class="stat-label">Best Loss</span><span class="stat-value">${r.best_loss.toFixed(4)}</span></div>
          <div class="stat-item"><span class="stat-label">Run ID</span><span class="stat-value">${r.id}</span></div>
        </div>
      </div>
    `).join('');
  }

  function parseEpochPct(epochStr) {
    const parts = epochStr.split('/');
    if (parts.length === 2) {
      return Math.round((parseInt(parts[0]) / parseInt(parts[1])) * 100);
    }
    return 0;
  }

  // ---- Loss Chart ----
  function renderLossChart() {
    const canvas = document.getElementById('lossCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const pad = { top: 20, right: 20, bottom: 30, left: 60 };

    ctx.clearRect(0, 0, W, H);

    // Background
    ctx.fillStyle = '#090b0f';
    ctx.fillRect(0, 0, W, H);

    const train = lossHistory.train;
    const val = lossHistory.val;
    if (train.length < 2) {
      ctx.fillStyle = '#3a3e48';
      ctx.font = '14px "JetBrains Mono"';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for data...', W / 2, H / 2);
      return;
    }

    const allVals = [...train, ...val].filter(v => v != null);
    const maxLoss = Math.max(...allVals) * 1.1;
    const minLoss = Math.min(0, Math.min(...allVals));
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    // Grid lines
    ctx.strokeStyle = '#1a1e28';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad.top + (plotH / 5) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(W - pad.right, y);
      ctx.stroke();

      // Y-axis labels
      const lossVal = maxLoss - (maxLoss - minLoss) * (i / 5);
      ctx.fillStyle = '#4a4e58';
      ctx.font = '10px "JetBrains Mono"';
      ctx.textAlign = 'right';
      ctx.fillText(lossVal.toFixed(3), pad.left - 8, y + 4);
    }

    // Draw line helper
    function drawLine(data, color, glow) {
      if (data.length < 2) return;
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.shadowColor = glow;
      ctx.shadowBlur = 6;
      for (let i = 0; i < data.length; i++) {
        if (data[i] == null) continue;
        const x = pad.left + (i / (data.length - 1)) * plotW;
        const y = pad.top + plotH - ((data[i] - minLoss) / (maxLoss - minLoss)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    drawLine(train, '#3dd68c', 'rgba(61, 214, 140, 0.4)');
    drawLine(val, '#e8a020', 'rgba(232, 160, 32, 0.4)');

    // X-axis label
    ctx.fillStyle = '#4a4e58';
    ctx.font = '10px "JetBrains Mono"';
    ctx.textAlign = 'center';
    ctx.fillText('Step', W / 2, H - 4);
  }

  // Generate synthetic loss curve for demo
  function generateDemoLoss() {
    const n = CHART_HISTORY;
    lossHistory.train = [];
    lossHistory.val = [];
    lossHistory.steps = [];
    let trainLoss = 0.8 + Math.random() * 0.3;
    let valLoss = trainLoss + 0.05;
    for (let i = 0; i < n; i++) {
      const decay = Math.exp(-i / (n * 0.3));
      const noise = (Math.random() - 0.5) * 0.01;
      trainLoss = 0.02 + (trainLoss - 0.02) * (1 - 0.02) + noise * decay;
      valLoss = trainLoss + 0.005 + Math.random() * 0.008;
      lossHistory.train.push(Math.max(0, trainLoss));
      lossHistory.val.push(Math.max(0, valLoss));
      lossHistory.steps.push(i * 50);
    }
  }

  // Append new point to loss curve (for live updates)
  function appendLossPoint() {
    if (lossHistory.train.length === 0) return;
    const last = lossHistory.train[lossHistory.train.length - 1];
    const noise = (Math.random() - 0.5) * 0.003;
    const newTrain = Math.max(0.01, last - 0.0003 + noise);
    const newVal = newTrain + 0.004 + Math.random() * 0.006;

    lossHistory.train.push(newTrain);
    lossHistory.val.push(newVal);
    lossHistory.steps.push((lossHistory.steps[lossHistory.steps.length - 1] || 0) + 50);

    if (lossHistory.train.length > CHART_HISTORY) {
      lossHistory.train.shift();
      lossHistory.val.shift();
      lossHistory.steps.shift();
    }
  }

  // ---- Run History Table ----
  function renderHistory(runs) {
    const body = $('#historyBody');
    const sorted = [...runs].sort((a, b) => {
      let va = a[sortCol], vb = b[sortCol];
      if (sortCol === 'loss') { va = a.best_loss; vb = b.best_loss; }
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });

    body.innerHTML = sorted.map(r => `
      <tr>
        <td style="color:var(--text-dim);">${r.id}</td>
        <td style="color:var(--text-bright);">${r.name}</td>
        <td><span class="status-badge ${r.status}"><span class="led led-${statusLedClass(r.status)}"></span>${r.status}</span></td>
        <td>${r.epochs}</td>
        <td style="color:var(--green);">${r.best_loss.toFixed(4)}</td>
        <td>${r.duration}</td>
        <td style="color:var(--text-dim);">${r.started}</td>
      </tr>
    `).join('');

    $('#runCount').textContent = `${runs.length} runs`;

    // Update sort indicators
    $$('#historyTable thead th').forEach(th => {
      th.classList.remove('sorted-asc', 'sorted-desc');
      if (th.dataset.col === sortCol) {
        th.classList.add(sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
      }
    });
  }

  function statusLedClass(status) {
    switch (status) {
      case 'running':  return 'amber';
      case 'complete': return 'green';
      case 'failed':   return 'red';
      case 'queued':   return 'amber';
      default:         return 'off';
    }
  }

  // Table sorting
  document.addEventListener('click', function (e) {
    const th = e.target.closest('#historyTable thead th');
    if (!th) return;
    const col = th.dataset.col;
    if (sortCol === col) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortCol = col;
      sortDir = 'asc';
    }
    renderHistory(runsState.length ? runsState : DEMO_RUNS);
  });

  // ---- Notebook Gallery ----
  function renderNotebooks(notebooks) {
    const grid = $('#notebookGrid');
    grid.innerHTML = notebooks.map(nb => `
      <div class="notebook-card">
        <div class="notebook-icon">&#128211;</div>
        <div class="notebook-name">${nb.name}</div>
        <div class="notebook-meta">
          <span>${nb.cells} cells</span>
          <span>Last run: ${nb.last_run}</span>
          <span style="color:${nb.status === 'dirty' ? 'var(--amber)' : 'var(--green)'};">${nb.status === 'dirty' ? 'Modified' : 'Clean'}</span>
        </div>
      </div>
    `).join('');
    $('#nbCount').textContent = `${notebooks.length} notebooks`;
  }

  // ---- Toggle Switches ----
  window.toggleSwitch = function (el) {
    el.classList.toggle('on');
    // Tactile click sound simulation via a short visual flash
    el.style.transition = 'none';
    el.style.transform = 'scale(0.95)';
    requestAnimationFrame(() => {
      el.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)';
      el.style.transform = 'scale(1)';
    });
  };

  // ---- Slider Updates ----
  window.updateSlider = function (name, value) {
    const display = $(`#val_${name}`);
    if (!display) return;
    if (name === 'n_samples') {
      display.textContent = parseInt(value).toLocaleString();
    } else if (name === 'n_epochs' || name === 'max_depth') {
      display.textContent = parseInt(value);
    } else {
      display.textContent = parseFloat(value).toFixed(2);
    }
  };

  // ---- Presets ----
  window.applyPreset = function (name) {
    const p = PRESETS[name];
    if (!p) return;

    $$('.preset-btn').forEach(b => b.classList.remove('active'));
    $(`.preset-btn[data-preset="${name}"]`).classList.add('active');

    for (const [key, val] of Object.entries(p)) {
      const slider = $(`#sl_${key}`);
      if (slider) {
        slider.value = val;
        updateSlider(key, val);
      }
    }
  };

  // ---- Launch Run ----
  window.launchRun = async function () {
    const btn = $('#btnLaunch');
    btn.classList.add('clicked');
    setTimeout(() => btn.classList.remove('clicked'), 300);

    const params = {
      gc_bias:    parseFloat($('#sl_gc_bias').value),
      max_depth:  parseInt($('#sl_max_depth').value),
      wobble_p:   parseFloat($('#sl_wobble_p').value),
      n_samples:  parseInt($('#sl_n_samples').value),
      n_epochs:   parseInt($('#sl_n_epochs').value),
      fp16:       $('#tgl_fp16').classList.contains('on'),
      grad_ckpt:  $('#tgl_grad_ckpt').classList.contains('on'),
      wandb:      $('#tgl_wandb').classList.contains('on'),
      autosave:   $('#tgl_autosave').classList.contains('on'),
    };

    try {
      const res = await fetch(API_BASE + '/api/launch-run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
        signal: AbortSignal.timeout(5000)
      });
      if (res.ok) {
        const data = await res.json();
        showToast(`Run ${data.run_id || 'launched'} started!`, 'green');
      } else {
        showToast('Launch failed: ' + res.status, 'red');
      }
    } catch (e) {
      showToast('API unavailable - demo mode', 'amber');
      // Add demo run
      const newId = `run-${String(43 + Math.floor(Math.random() * 100)).padStart(3, '0')}`;
      const demoRun = {
        id: newId,
        name: `rna3d_custom_${Date.now() % 10000}`,
        status: 'running',
        epochs: `0/${params.n_epochs}`,
        best_loss: 0.5 + Math.random() * 0.5,
        duration: '0h 00m',
        started: new Date().toISOString().slice(0, 16).replace('T', ' '),
        params
      };
      runsState = [demoRun, ...(runsState.length ? runsState : DEMO_RUNS)];
      renderActiveRuns(runsState);
      renderHistory(runsState);
    }
  };

  window.stopAllRuns = async function () {
    try {
      await fetch(API_BASE + '/api/stop-all', { method: 'POST', signal: AbortSignal.timeout(3000) });
      showToast('All runs stopped', 'amber');
    } catch (e) {
      showToast('Stop signal sent (demo mode)', 'amber');
      runsState = (runsState.length ? runsState : DEMO_RUNS).map(r =>
        r.status === 'running' ? { ...r, status: 'failed' } : r
      );
      renderActiveRuns(runsState);
      renderHistory(runsState);
    }
  };

  // ---- Toast Notification ----
  function showToast(msg, color) {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed; bottom: 24px; right: 24px; z-index: 1000;
      background: var(--bg-raised); border: 1px solid var(--${color === 'green' ? 'green' : color === 'red' ? 'red' : 'amber'}-dim);
      color: var(--${color === 'green' ? 'green' : color === 'red' ? 'red' : 'amber'});
      padding: 12px 20px; border-radius: 4px; font-family: var(--mono); font-size: 0.8rem;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5); animation: fade-in 0.3s ease-out;
    `;
    toast.textContent = msg;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ---- Polling ----
  async function pollGpu() {
    const data = await apiFetch('/api/gpu-status');
    if (data) {
      gpuState = data;
      setConnected(true);
    } else {
      // Add some jitter to demo data
      gpuState = {
        ...DEMO_GPU,
        utilization: DEMO_GPU.utilization + Math.floor((Math.random() - 0.5) * 8),
        vram_used: +(DEMO_GPU.vram_used + (Math.random() - 0.5) * 0.5).toFixed(1),
        temperature: DEMO_GPU.temperature + Math.floor((Math.random() - 0.5) * 3),
        power_draw: DEMO_GPU.power_draw + Math.floor((Math.random() - 0.5) * 15),
        fan_speed: DEMO_GPU.fan_speed + Math.floor((Math.random() - 0.5) * 4),
      };
      setConnected(false);
    }
    updateMeterValues(gpuState);
  }

  async function pollRuns() {
    const data = await apiFetch('/api/runs');
    if (data && data.runs) {
      runsState = data.runs;
      setConnected(true);
    } else if (!runsState.length) {
      runsState = DEMO_RUNS;
    }
    renderActiveRuns(runsState);
    renderHistory(runsState);
  }

  async function pollServices() {
    const data = await apiFetch('/api/services');
    if (data && data.services) {
      servicesState = data.services;
    } else {
      servicesState = DEMO_SERVICES;
    }
    renderServices(servicesState);
  }

  // ---- Init ----
  function init() {
    tickClock();
    setInterval(tickClock, 1000);

    // Start meter animation loop
    requestAnimationFrame(animateMeters);

    // Generate demo loss data
    generateDemoLoss();
    renderLossChart();

    // Initial renders with demo data
    renderServices(DEMO_SERVICES);
    renderNotebooks(DEMO_NOTEBOOKS);
    renderHistory(DEMO_RUNS);
    renderActiveRuns(DEMO_RUNS);
    updateMeterValues(DEMO_GPU);

    // Start polling
    pollGpu();
    pollRuns();
    pollServices();
    setInterval(pollGpu, POLL_INTERVAL);
    setInterval(pollRuns, POLL_INTERVAL * 2);
    setInterval(pollServices, POLL_INTERVAL * 5);

    // Animate loss chart
    setInterval(() => {
      appendLossPoint();
      renderLossChart();
    }, 2000);

    // Simulate demo epoch progress for running runs
    setInterval(() => {
      runsState = runsState.map(r => {
        if (r.status !== 'running') return r;
        const [cur, total] = r.epochs.split('/').map(Number);
        if (cur < total) {
          const newLoss = Math.max(0.01, r.best_loss - Math.random() * 0.001);
          return { ...r, epochs: `${cur + 1}/${total}`, best_loss: newLoss };
        } else {
          return { ...r, status: 'complete' };
        }
      });
      renderActiveRuns(runsState);
      renderHistory(runsState);
    }, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
