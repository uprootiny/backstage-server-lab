/* ================================================================
   RNA 3D Lab — Notebook App  (vanilla JS, ~750 lines)
   ================================================================ */

// ---- Constants ----
const API_BASE = window.location.origin;
const POLL_GPU_MS = 5000;
const POLL_NB_MS  = 8000;

// ---- DOM refs ----
const $sidebarList   = document.getElementById('sidebar-list');
const $cellsContainer= document.getElementById('cells-container');
const $notebookTitle = document.getElementById('notebook-title');
const $gpuDot        = document.getElementById('gpu-dot');
const $gpuLabel      = document.getElementById('gpu-label');
const $connLed       = document.getElementById('conn-led');
const $kernelDot     = document.getElementById('kernel-dot');
const $kernelStatus  = document.getElementById('kernel-status');
const $execTime      = document.getElementById('exec-time');
const $cellCount     = document.getElementById('cell-count');
const $memUsage      = document.getElementById('mem-usage');
const $btnRunAll     = document.getElementById('btn-run-all');
const $btnRestart    = document.getElementById('btn-restart');
const $btnDemo       = document.getElementById('btn-demo');

// ---- Notebook State ----
class NotebookState {
  constructor() {
    this.cells = [];
    this.activeIdx = -1;
    this.executionCounter = 0;
    this.isRunning = false;
    this.notebookName = '';
    this.apiAvailable = false;
  }

  addCell(type, source, outputs, execCount, idx) {
    const cell = {
      id: 'cell-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8),
      type: type || 'code',
      source: source || '',
      outputs: outputs || [],
      execCount: execCount || null,
      isRunning: false,
      hasError: false,
    };
    if (idx !== undefined && idx >= 0 && idx <= this.cells.length) {
      this.cells.splice(idx, 0, cell);
    } else {
      this.cells.push(cell);
    }
    return cell;
  }

  removeCell(idx) {
    if (this.cells.length <= 1) return;
    this.cells.splice(idx, 1);
    if (this.activeIdx >= this.cells.length) this.activeIdx = this.cells.length - 1;
  }

  moveCell(idx, dir) {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= this.cells.length) return;
    const tmp = this.cells[idx];
    this.cells[idx] = this.cells[newIdx];
    this.cells[newIdx] = tmp;
    this.activeIdx = newIdx;
  }

  toggleType(idx) {
    const c = this.cells[idx];
    if (!c) return;
    c.type = c.type === 'code' ? 'markdown' : 'code';
    c.outputs = [];
    c.execCount = null;
  }

  clear() {
    this.cells = [];
    this.activeIdx = -1;
    this.executionCounter = 0;
  }
}

const state = new NotebookState();

// ---- Syntax Highlighting ----
const PY_KEYWORDS = new Set([
  'False','None','True','and','as','assert','async','await','break','class',
  'continue','def','del','elif','else','except','finally','for','from',
  'global','if','import','in','is','lambda','nonlocal','not','or','pass',
  'raise','return','try','while','with','yield'
]);

const PY_BUILTINS = new Set([
  'print','len','range','int','float','str','list','dict','set','tuple',
  'type','isinstance','enumerate','zip','map','filter','sorted','sum',
  'min','max','abs','round','open','super','property','staticmethod',
  'classmethod','hasattr','getattr','setattr','input','format','repr',
  'bool','bytes','complex','frozenset','hex','id','iter','next','oct',
  'ord','pow','chr','vars','dir','hash','memoryview','object','reversed',
  'slice','all','any','bin','breakpoint','callable','compile','exec','eval',
]);

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function highlightPython(code) {
  // Tokenize and highlight
  let result = '';
  let i = 0;
  const n = code.length;

  while (i < n) {
    // Comments
    if (code[i] === '#') {
      let end = code.indexOf('\n', i);
      if (end === -1) end = n;
      result += '<span class="syn-comment">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // Decorators
    if (code[i] === '@' && (i === 0 || code[i-1] === '\n')) {
      let end = i + 1;
      while (end < n && /[\w.]/.test(code[end])) end++;
      result += '<span class="syn-decorator">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // Triple-quoted strings
    if ((code.slice(i, i+3) === '"""' || code.slice(i, i+3) === "'''")) {
      const q = code.slice(i, i+3);
      let end = code.indexOf(q, i+3);
      if (end === -1) end = n - 3;
      end += 3;
      result += '<span class="syn-string">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // Strings
    if (code[i] === '"' || code[i] === "'") {
      const q = code[i];
      let end = i + 1;
      while (end < n && code[end] !== q && code[end] !== '\n') {
        if (code[end] === '\\') end++;
        end++;
      }
      if (end < n && code[end] === q) end++;
      result += '<span class="syn-string">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // f-strings (basic — just color the f and string)
    if ((code[i] === 'f' || code[i] === 'F') && i+1 < n && (code[i+1] === '"' || code[i+1] === "'")) {
      const q = code[i+1];
      let end = i + 2;
      while (end < n && code[end] !== q && code[end] !== '\n') {
        if (code[end] === '\\') end++;
        end++;
      }
      if (end < n && code[end] === q) end++;
      result += '<span class="syn-string">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // Numbers
    if (/\d/.test(code[i]) && (i === 0 || !/\w/.test(code[i-1]))) {
      let end = i;
      while (end < n && /[\d.eE_xXoObBa-fA-F]/.test(code[end])) end++;
      result += '<span class="syn-number">' + escapeHtml(code.slice(i, end)) + '</span>';
      i = end;
      continue;
    }

    // Words (keywords, builtins, identifiers)
    if (/[a-zA-Z_]/.test(code[i])) {
      let end = i;
      while (end < n && /[\w]/.test(code[end])) end++;
      const word = code.slice(i, end);
      if (PY_KEYWORDS.has(word)) {
        result += '<span class="syn-keyword">' + escapeHtml(word) + '</span>';
      } else if (PY_BUILTINS.has(word)) {
        result += '<span class="syn-builtin">' + escapeHtml(word) + '</span>';
      } else if (end < n && code[end] === '(') {
        result += '<span class="syn-function">' + escapeHtml(word) + '</span>';
      } else {
        result += escapeHtml(word);
      }
      i = end;
      continue;
    }

    // Operators
    if ('=+-*/<>!&|%^~'.includes(code[i])) {
      result += '<span class="syn-operator">' + escapeHtml(code[i]) + '</span>';
      i++;
      continue;
    }

    // Everything else
    result += escapeHtml(code[i]);
    i++;
  }
  return result;
}

// ---- Markdown Renderer ----
function renderMarkdown(src) {
  let lines = src.split('\n');
  let html = '';
  let inCodeBlock = false;
  let codeAccum = '';
  let inList = false;
  let listType = '';

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // Code blocks
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        html += '<pre><code>' + escapeHtml(codeAccum) + '</code></pre>';
        codeAccum = '';
        inCodeBlock = false;
      } else {
        if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; }
        inCodeBlock = true;
      }
      continue;
    }
    if (inCodeBlock) {
      codeAccum += (codeAccum ? '\n' : '') + line;
      continue;
    }

    // Close list if needed
    if (inList && !/^\s*([-*]|\d+\.)\s/.test(line) && line.trim() !== '') {
      html += listType === 'ul' ? '</ul>' : '</ol>';
      inList = false;
    }

    // Headings
    if (/^### /.test(line)) { html += '<h3>' + inlineMarkdown(line.slice(4)) + '</h3>'; continue; }
    if (/^## /.test(line))  { html += '<h2>' + inlineMarkdown(line.slice(3)) + '</h2>'; continue; }
    if (/^# /.test(line))   { html += '<h1>' + inlineMarkdown(line.slice(2)) + '</h1>'; continue; }

    // Unordered list
    if (/^\s*[-*]\s/.test(line)) {
      if (!inList || listType !== 'ul') {
        if (inList) html += listType === 'ul' ? '</ul>' : '</ol>';
        html += '<ul>';
        inList = true;
        listType = 'ul';
      }
      html += '<li>' + inlineMarkdown(line.replace(/^\s*[-*]\s/, '')) + '</li>';
      continue;
    }

    // Ordered list
    if (/^\s*\d+\.\s/.test(line)) {
      if (!inList || listType !== 'ol') {
        if (inList) html += listType === 'ul' ? '</ul>' : '</ol>';
        html += '<ol>';
        inList = true;
        listType = 'ol';
      }
      html += '<li>' + inlineMarkdown(line.replace(/^\s*\d+\.\s/, '')) + '</li>';
      continue;
    }

    // Empty line
    if (line.trim() === '') { html += '<br>'; continue; }

    // Paragraph
    html += '<p>' + inlineMarkdown(line) + '</p>';
  }

  if (inCodeBlock) html += '<pre><code>' + escapeHtml(codeAccum) + '</code></pre>';
  if (inList) html += listType === 'ul' ? '</ul>' : '</ol>';
  return html;
}

function inlineMarkdown(text) {
  let s = escapeHtml(text);
  // Inline code
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Italic
  s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
  s = s.replace(/_(.+?)_/g, '<em>$1</em>');
  return s;
}

// ---- Line Numbers ----
function generateLineNumbers(code) {
  const lines = code.split('\n');
  return lines.map((_, i) => i + 1).join('\n');
}

// ---- Render Cells ----
function renderAllCells() {
  $cellsContainer.innerHTML = '';
  state.cells.forEach((cell, idx) => {
    // Add cell divider above
    if (idx === 0) {
      $cellsContainer.appendChild(createAddCellBar(idx));
    }
    $cellsContainer.appendChild(renderCell(cell, idx));
    $cellsContainer.appendChild(createAddCellBar(idx + 1));
  });
  $cellCount.textContent = state.cells.length + ' cells';
}

function createAddCellBar(insertIdx) {
  const bar = document.createElement('div');
  bar.className = 'add-cell-bar';

  const btnCode = document.createElement('button');
  btnCode.className = 'add-btn';
  btnCode.textContent = '+ Code';
  btnCode.onclick = () => { state.addCell('code', '', [], null, insertIdx); renderAllCells(); };

  const btnMd = document.createElement('button');
  btnMd.className = 'add-btn';
  btnMd.textContent = '+ Markdown';
  btnMd.style.marginLeft = '4px';
  btnMd.onclick = () => { state.addCell('markdown', '', [], null, insertIdx); renderAllCells(); };

  bar.appendChild(btnCode);
  bar.appendChild(btnMd);
  return bar;
}

function renderCell(cell, idx) {
  const wrapper = document.createElement('div');
  wrapper.className = 'cell' + (idx === state.activeIdx ? ' active' : '') + (cell.isRunning ? ' running' : '') + (cell.hasError ? ' error-cell' : '');
  wrapper.dataset.idx = idx;
  wrapper.onclick = (e) => {
    if (e.target.tagName === 'BUTTON') return;
    state.activeIdx = idx;
    document.querySelectorAll('.cell').forEach((el, i) => {
      el.classList.toggle('active', i === idx);
    });
  };

  // Toolbar
  const toolbar = document.createElement('div');
  toolbar.className = 'cell-toolbar';

  const typeLabel = document.createElement('span');
  typeLabel.className = 'cell-type-label';
  typeLabel.textContent = cell.type;

  const execC = document.createElement('span');
  execC.className = 'exec-counter' + (cell.execCount ? ' has-run' : '');
  execC.textContent = cell.execCount ? '[' + cell.execCount + ']' : '[ ]';

  toolbar.appendChild(typeLabel);
  toolbar.appendChild(execC);

  if (cell.type === 'code') {
    const runBtn = document.createElement('button');
    runBtn.className = 'tb-btn run-btn';
    runBtn.textContent = '\u25B6 Run';
    runBtn.onclick = () => executeCell(idx);
    toolbar.appendChild(runBtn);
  }

  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'tb-btn';
  toggleBtn.textContent = cell.type === 'code' ? 'MD' : 'Code';
  toggleBtn.title = 'Toggle cell type';
  toggleBtn.onclick = () => { state.toggleType(idx); renderAllCells(); };
  toolbar.appendChild(toggleBtn);

  const upBtn = document.createElement('button');
  upBtn.className = 'tb-btn';
  upBtn.textContent = '\u2191';
  upBtn.onclick = () => { state.moveCell(idx, -1); renderAllCells(); };
  toolbar.appendChild(upBtn);

  const dnBtn = document.createElement('button');
  dnBtn.className = 'tb-btn';
  dnBtn.textContent = '\u2193';
  dnBtn.onclick = () => { state.moveCell(idx, 1); renderAllCells(); };
  toolbar.appendChild(dnBtn);

  const delBtn = document.createElement('button');
  delBtn.className = 'tb-btn del-btn';
  delBtn.textContent = '\u2715';
  delBtn.onclick = () => { state.removeCell(idx); renderAllCells(); };
  toolbar.appendChild(delBtn);

  wrapper.appendChild(toolbar);

  // Cell body
  if (cell.type === 'code') {
    wrapper.appendChild(renderCodeCell(cell, idx));
  } else {
    wrapper.appendChild(renderMarkdownCell(cell, idx));
  }

  // Outputs
  if (cell.outputs && cell.outputs.length > 0) {
    cell.outputs.forEach(out => {
      const outEl = document.createElement('div');
      outEl.className = 'cell-output' + (out.error ? ' error-output' : '');
      if (out.image) {
        const img = document.createElement('img');
        img.src = 'data:image/png;base64,' + out.image;
        outEl.appendChild(img);
      }
      if (out.text) {
        const txt = document.createElement('span');
        txt.textContent = out.text;
        outEl.appendChild(txt);
      }
      if (out.html) {
        outEl.innerHTML = out.html;
      }
      wrapper.appendChild(outEl);
    });
  }

  return wrapper;
}

function renderCodeCell(cell, idx) {
  const wrap = document.createElement('div');
  wrap.className = 'cell-code-wrap';

  const lineNums = document.createElement('div');
  lineNums.className = 'line-numbers';
  lineNums.textContent = generateLineNumbers(cell.source);

  const editorWrap = document.createElement('div');
  editorWrap.className = 'code-editor';

  const highlight = document.createElement('div');
  highlight.className = 'code-highlight';
  highlight.innerHTML = highlightPython(cell.source) + '\n';

  const textarea = document.createElement('textarea');
  textarea.value = cell.source;
  textarea.spellcheck = false;
  textarea.rows = Math.max(cell.source.split('\n').length, 1);
  textarea.style.height = 'auto';

  textarea.addEventListener('input', () => {
    cell.source = textarea.value;
    highlight.innerHTML = highlightPython(textarea.value) + '\n';
    lineNums.textContent = generateLineNumbers(textarea.value);
    autoResize(textarea);
  });

  textarea.addEventListener('keydown', (e) => handleCellKeydown(e, idx));

  textarea.addEventListener('focus', () => {
    state.activeIdx = idx;
    document.querySelectorAll('.cell').forEach((el, i) => el.classList.toggle('active', i === idx));
  });

  editorWrap.appendChild(highlight);
  editorWrap.appendChild(textarea);
  wrap.appendChild(lineNums);
  wrap.appendChild(editorWrap);

  // Auto-resize after paint
  requestAnimationFrame(() => autoResize(textarea));
  return wrap;
}

function renderMarkdownCell(cell, idx) {
  const wrap = document.createElement('div');
  wrap.className = 'cell-markdown';

  if (idx === state.activeIdx && cell._editing) {
    wrap.classList.add('editing');
    const textarea = document.createElement('textarea');
    textarea.value = cell.source;
    textarea.spellcheck = false;

    textarea.addEventListener('input', () => {
      cell.source = textarea.value;
      autoResize(textarea);
    });

    textarea.addEventListener('keydown', (e) => handleCellKeydown(e, idx));

    textarea.addEventListener('blur', () => {
      cell._editing = false;
      renderAllCells();
    });

    wrap.appendChild(textarea);
    requestAnimationFrame(() => { textarea.focus(); autoResize(textarea); });
  } else {
    const rendered = document.createElement('div');
    rendered.className = 'md-rendered';
    rendered.innerHTML = renderMarkdown(cell.source);
    wrap.appendChild(rendered);

    wrap.ondblclick = () => {
      cell._editing = true;
      state.activeIdx = idx;
      renderAllCells();
    };
  }

  return wrap;
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
}

// ---- Keyboard Shortcuts ----
function handleCellKeydown(e, idx) {
  // Shift+Enter: run cell and advance
  if (e.key === 'Enter' && e.shiftKey && !e.ctrlKey) {
    e.preventDefault();
    executeCell(idx).then(() => {
      if (idx + 1 < state.cells.length) {
        state.activeIdx = idx + 1;
      } else {
        state.addCell('code');
        state.activeIdx = state.cells.length - 1;
      }
      renderAllCells();
      focusActiveCell();
    });
    return;
  }

  // Ctrl+Enter: run cell in place
  if (e.key === 'Enter' && e.ctrlKey) {
    e.preventDefault();
    executeCell(idx);
    return;
  }

  // Escape: blur (command mode)
  if (e.key === 'Escape') {
    e.target.blur();
    const cell = state.cells[idx];
    if (cell && cell.type === 'markdown') {
      cell._editing = false;
      renderAllCells();
    }
    return;
  }
}

// Global keydown for command mode
document.addEventListener('keydown', (e) => {
  const active = document.activeElement;
  if (active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT')) return;

  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
    // Enter edit mode
    e.preventDefault();
    const cell = state.cells[state.activeIdx];
    if (cell && cell.type === 'markdown') {
      cell._editing = true;
      renderAllCells();
    } else {
      focusActiveCell();
    }
    return;
  }

  if (e.key === 'j' || e.key === 'ArrowDown') {
    e.preventDefault();
    if (state.activeIdx < state.cells.length - 1) {
      state.activeIdx++;
      renderAllCells();
    }
    return;
  }

  if (e.key === 'k' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (state.activeIdx > 0) {
      state.activeIdx--;
      renderAllCells();
    }
    return;
  }

  if (e.key === 'b') {
    state.addCell('code', '', [], null, state.activeIdx + 1);
    state.activeIdx++;
    renderAllCells();
    return;
  }

  if (e.key === 'a') {
    state.addCell('code', '', [], null, state.activeIdx);
    renderAllCells();
    return;
  }

  if (e.key === 'd') {
    // Double-d to delete not implemented; single d deletes
    return;
  }
});

function focusActiveCell() {
  const cells = document.querySelectorAll('.cell');
  if (cells[state.activeIdx]) {
    const ta = cells[state.activeIdx].querySelector('textarea');
    if (ta) ta.focus();
  }
}

// ---- Execution ----
async function executeCell(idx) {
  const cell = state.cells[idx];
  if (!cell || cell.type !== 'code') return;

  cell.isRunning = true;
  cell.hasError = false;
  cell.outputs = [];
  state.isRunning = true;
  updateKernelStatus('busy');
  renderAllCells();

  const startTime = performance.now();

  try {
    const resp = await fetch(API_BASE + '/api/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: cell.source }),
    });

    if (resp.ok) {
      const data = await resp.json();
      state.executionCounter++;
      cell.execCount = state.executionCounter;
      cell.outputs = [];

      if (data.output && data.output.trim()) {
        cell.outputs.push({ text: data.output });
      }
      if (data.images && data.images.length > 0) {
        data.images.forEach(img => cell.outputs.push({ image: img }));
      }
      if (data.error) {
        cell.outputs.push({ text: data.error, error: true });
        cell.hasError = true;
      }

      const elapsed = data.duration_ms || (performance.now() - startTime);
      $execTime.textContent = 'Last: ' + formatDuration(elapsed);
    } else {
      throw new Error('API returned ' + resp.status);
    }
  } catch (err) {
    // Demo mode fallback
    state.executionCounter++;
    cell.execCount = state.executionCounter;
    simulateDemoExecution(cell);
    $execTime.textContent = 'Last: ' + formatDuration(performance.now() - startTime);
  }

  cell.isRunning = false;
  state.isRunning = false;
  updateKernelStatus('idle');
  renderAllCells();
}

async function runAllCells() {
  for (let i = 0; i < state.cells.length; i++) {
    if (state.cells[i].type === 'code') {
      state.activeIdx = i;
      await executeCell(i);
    }
  }
}

function simulateDemoExecution(cell) {
  // Provide a basic simulated output for demo mode
  const code = cell.source.trim();
  if (!code) return;

  const lines = code.split('\n');
  const printLines = lines.filter(l => l.trim().startsWith('print('));
  if (printLines.length > 0) {
    let fakeOutput = '';
    printLines.forEach(l => {
      const m = l.match(/print\((.+)\)/);
      if (m) {
        let content = m[1].trim();
        // Try to evaluate simple string literals
        if ((content.startsWith("'") && content.endsWith("'")) ||
            (content.startsWith('"') && content.endsWith('"'))) {
          fakeOutput += content.slice(1, -1) + '\n';
        } else if (content.startsWith('f"') || content.startsWith("f'")) {
          fakeOutput += content.slice(2, -1).replace(/\{[^}]+\}/g, '...') + '\n';
        } else {
          fakeOutput += '[output]\n';
        }
      }
    });
    cell.outputs = [{ text: fakeOutput.trim() }];
  } else if (code.includes('import')) {
    cell.outputs = [];  // imports produce no output
  } else {
    cell.outputs = [{ text: '[Executed in demo mode]' }];
  }
}

// ---- API Integration ----
async function fetchNotebooks() {
  try {
    const resp = await fetch(API_BASE + '/api/notebooks');
    if (!resp.ok) throw new Error('fail');
    const data = await resp.json();
    state.apiAvailable = true;
    $connLed.classList.add('connected');
    renderSidebar(data.notebooks || data);
  } catch {
    state.apiAvailable = false;
    $connLed.classList.remove('connected');
    renderSidebar([]);
  }
}

async function loadNotebook(name) {
  try {
    const resp = await fetch(API_BASE + '/api/notebook/' + encodeURIComponent(name));
    if (!resp.ok) throw new Error('fail');
    const data = await resp.json();
    state.clear();
    state.notebookName = name;
    $notebookTitle.textContent = name;
    (data.cells || data).forEach(c => {
      const outputs = (c.outputs || []).map(o => {
        if (typeof o === 'string') return { text: o };
        return o;
      });
      state.addCell(c.type || 'code', c.source || '', outputs, c.execution_count || null);
    });
    state.activeIdx = 0;
    renderAllCells();
  } catch {
    // Fallback to demo
    loadDemoNotebook();
  }
}

async function fetchGpuStatus() {
  try {
    const resp = await fetch(API_BASE + '/api/gpu-status');
    if (!resp.ok) throw new Error('fail');
    const data = await resp.json();
    $gpuDot.className = 'gpu-dot' + (data.utilization > 80 ? ' busy' : ' active');
    $gpuLabel.textContent = (data.name || 'GPU') + '  ' + data.utilization + '%  ' + data.vram_used + '/' + data.vram_total + ' GB';
    $memUsage.textContent = 'VRAM: ' + data.vram_used + '/' + data.vram_total + ' GB';
  } catch {
    $gpuDot.className = 'gpu-dot';
    $gpuLabel.textContent = 'GPU: offline';
    $memUsage.textContent = 'Mem: --';
  }
}

function renderSidebar(notebooks) {
  $sidebarList.innerHTML = '';
  if (notebooks.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'sidebar-item';
    empty.style.cssText = 'color:var(--cream-30);font-size:11px;justify-content:center;padding:24px;';
    empty.textContent = state.apiAvailable ? 'No notebooks found' : 'API offline — use demo';
    $sidebarList.appendChild(empty);
    return;
  }

  notebooks.forEach(nb => {
    const item = document.createElement('div');
    item.className = 'sidebar-item' + (nb.name === state.notebookName ? ' active' : '');

    const icon = document.createElement('span');
    icon.className = 'nb-icon';
    icon.textContent = '\u{1F4D3}';

    const name = document.createElement('span');
    name.className = 'nb-name';
    name.textContent = nb.name;

    const meta = document.createElement('span');
    meta.className = 'nb-meta';
    meta.textContent = nb.cells ? nb.cells + ' cells' : (nb.size ? formatBytes(nb.size) : '');

    item.appendChild(icon);
    item.appendChild(name);
    item.appendChild(meta);

    item.onclick = () => loadNotebook(nb.name || nb.path);
    $sidebarList.appendChild(item);
  });
}

// ---- Demo Notebook ----
async function loadDemoNotebook() {
  try {
    const resp = await fetch('demo_notebook.json');
    if (!resp.ok) throw new Error('no demo file');
    const data = await resp.json();
    state.clear();
    state.notebookName = 'RNA 3D Pipeline (Demo)';
    $notebookTitle.textContent = state.notebookName;
    data.cells.forEach((c, i) => {
      state.addCell(c.type, c.source, c.outputs || [], c.execution_count || null);
    });
    state.activeIdx = 0;
    renderAllCells();
  } catch {
    loadHardcodedDemo();
  }
}

function loadHardcodedDemo() {
  state.clear();
  state.notebookName = 'RNA 3D Pipeline (Demo)';
  $notebookTitle.textContent = state.notebookName;

  const demoCells = getHardcodedDemoCells();
  demoCells.forEach(c => {
    state.addCell(c.type, c.source, c.outputs || [], c.execCount || null);
  });
  state.activeIdx = 0;
  renderAllCells();
}

function getHardcodedDemoCells() {
  return [
    { type: 'markdown', source: '# RNA 3D Geometric Pipeline\n\nEnd-to-end: *generative grammar* -> *Nussinov folding* -> *3D geometry* -> *TDA* -> *EGNN forward pass*' },
    { type: 'code', source: 'import numpy as np\nfrom labops.rna_3d_pipeline import (\n    GrammarConfig, derive, fold_motif,\n    build_geometry, build_tda, build_graph,\n    EGNNModel, build_record\n)', outputs: [], execCount: 1 },
    { type: 'markdown', source: '## Generative Grammar\n\nSample RNA molecules from a stochastic context-free grammar with configurable GC-bias, wobble base-pair probability, and nesting depth.' },
    { type: 'code', source: "rng = np.random.default_rng(seed=42)\ncfg = GrammarConfig(gc_bias=0.55, wobble_p=0.12, max_depth=6)\n\nmolecules = [derive(rng, cfg) for _ in range(24)]\nprint(f'Generated {len(molecules)} molecules')\nprint(f'Lengths: {[m.n for m in molecules]}')", outputs: [{ text: 'Generated 24 molecules\nLengths: [34, 42, 28, 51, 38, 45, 31, 56, 40, 33, 47, 29, 52, 36, 44, 30, 48, 39, 55, 35, 43, 27, 50, 37]' }], execCount: 2 },
    { type: 'code', source: "# Statistics\nlengths = [m.n for m in molecules]\ngc_fracs = [sum(c in 'GC' for c in m.sequence) / m.n for m in molecules]\nprint(f'Mean length: {np.mean(lengths):.1f} +/- {np.std(lengths):.1f}')\nprint(f'Mean GC fraction: {np.mean(gc_fracs):.3f}')\nprint(f'Sequence[0]: {molecules[0].sequence[:40]}...')\nprint(f'Bracket[0]:  {molecules[0].bracket[:40]}...')", outputs: [{ text: 'Mean length: 40.0 +/- 8.6\nMean GC fraction: 0.548\nSequence[0]: GCGCAUUAGCGCAUUAGCGCAUUAGCGCAUUAGCGCAU...\nBracket[0]:  ((((....((((....))))..(((...)))....))))...' }], execCount: 3 },
    { type: 'markdown', source: '## Secondary Structure -- Nussinov DP\n\nFold each molecule using the Nussinov dynamic-programming algorithm with wobble base-pair support.' },
    { type: 'code', source: "records_2d = [fold_motif(m) for m in molecules]\n\nex = records_2d[0]\nprint(f'Molecule 0:')\nprint(f'  Sequence: {ex.motif.sequence[:50]}...')\nprint(f'  Bracket:  {ex.bracket[:50]}...')\nprint(f'  Pairs:    {len(ex.pairs)}')\nprint(f'  Pairing fraction: {ex.stats.pairing_fraction:.3f}')\nprint(f'  Max nesting depth: {ex.stats.max_nesting_depth}')", outputs: [{ text: 'Molecule 0:\n  Sequence: GCGCAUUAGCGCAUUAGCGCAUUAGCGCAUUAGCGCAUUAGCGCAUUA...\n  Bracket:  ((((....((((....))))..(((...)))....)))).............\n  Pairs:    12\n  Pairing fraction: 0.706\n  Max nesting depth: 4' }], execCount: 4 },
    { type: 'markdown', source: '## 3D Geometry\n\nBuild A-form helix coordinates with Bishop frame transport for stems and worm-like-chain loop regions.' },
    { type: 'code', source: "geometries = [build_geometry(sr) for sr in records_2d]\n\ng0 = geometries[0]\nprint(f'Coords shape: {g0.coords.shape}')\nprint(f'Coord range: [{g0.coords.min():.2f}, {g0.coords.max():.2f}]')\nprint(f'Dihedrals (non-NaN): {np.count_nonzero(~np.isnan(g0.dihedrals))}')\nprint(f'Mean dihedral: {np.nanmean(g0.dihedrals):.1f} deg')", outputs: [{ text: 'Coords shape: (34, 3)\nCoord range: [-14.22, 38.71]\nDihedrals (non-NaN): 30\nMean dihedral: -12.4 deg' }], execCount: 5 },
    { type: 'markdown', source: '## Topological Data Analysis\n\nCompute Vietoris-Rips persistence diagrams (H0, H1) and extract Betti curve features.' },
    { type: 'code', source: "tda_records = [build_tda(g) for g in geometries]\n\nt0 = tda_records[0]\nprint(f'Distance matrix: {t0.D.shape}')\nprint(f'H0 intervals: {len(t0.dgm.H0)}')\nprint(f'H1 intervals: {len(t0.dgm.H1)}')\nprint(f'Feature vector dim: {t0.feat.shape[0]}')\nprint(f'Max filtration: {t0.dgm.max_filtration:.2f}')", outputs: [{ text: 'Distance matrix: (34, 34)\nH0 intervals: 33\nH1 intervals: 8\nFeature vector dim: 48\nMax filtration: 52.37' }], execCount: 6 },
    { type: 'code', source: "# Build full molecule records with graphs\nfull_records = [build_record(m) for m in molecules[:8]]\n\ng = full_records[0].graph\nprint(f'Node features: {g.node_feats.shape}')\nprint(f'Edge index:    {g.edge_index.shape}')\nprint(f'Edge features: {g.edge_feats.shape}')\nprint(f'Coords:        {g.coords.shape}')", outputs: [{ text: 'Node features: (34, 16)\nEdge index:    (2, 198)\nEdge features: (198, 9)\nCoords:        (34, 3)' }], execCount: 7 },
    { type: 'code', source: "# EGNN forward pass\nmodel = EGNNModel.make(rng=np.random.default_rng(0))\nout = model.forward(full_records[0].graph)\n\nprint(f'Graph embedding: {out.graph_embed.shape}')\nprint(f'Node embedding:  {out.node_embed.shape}')\nprint(f'Refined coords:  {out.refined_coords.shape}')\nprint(f'Pred pairing fraction: {out.pred_pf:.4f}')\nprint(f'Pred nesting depth:    {out.pred_nd:.2f}')\nprint(f'True pairing fraction: {full_records[0].secondary.stats.pairing_fraction:.4f}')\nprint(f'True nesting depth:    {full_records[0].secondary.stats.max_nesting_depth}')\n\nprint('\\nPipeline complete.')", outputs: [{ text: 'Graph embedding: (64,)\nNode embedding:  (34, 64)\nRefined coords:  (34, 3)\nPred pairing fraction: 0.5127\nPred nesting depth:    2.84\nTrue pairing fraction: 0.7059\nTrue nesting depth:    4\n\nPipeline complete.' }], execCount: 8 },
  ];
}

// ---- Utility ----
function formatDuration(ms) {
  if (ms < 1000) return Math.round(ms) + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function updateKernelStatus(status) {
  $kernelDot.className = 'status-dot ' + status;
  $kernelStatus.textContent = status === 'busy' ? 'Running...' : 'Idle';
}

// ---- Event Bindings ----
$btnRunAll.onclick = runAllCells;
$btnRestart.onclick = () => {
  state.executionCounter = 0;
  state.cells.forEach(c => { c.execCount = null; c.outputs = []; c.isRunning = false; c.hasError = false; });
  updateKernelStatus('idle');
  renderAllCells();
};
$btnDemo.onclick = loadDemoNotebook;

// ---- Initialization ----
function init() {
  fetchNotebooks();
  fetchGpuStatus();
  loadDemoNotebook();

  setInterval(fetchGpuStatus, POLL_GPU_MS);
  setInterval(fetchNotebooks, POLL_NB_MS);
}

init();
