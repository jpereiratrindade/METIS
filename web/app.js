'use strict';

const $ = id => document.getElementById(id);

let scores = new Map();
let rawData = new Map();
let scores2017 = new Map();
let scores2006 = new Map();
let rawData2017 = new Map();
let rawData2006 = new Map();
let evidenciasData = null;
let episodiosData = null;
let manifest = null;

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
let geometry = null;
let current = null; // Nenhum município selecionado inicialmente
let activeArea = 'D'; // Área D (Resultados) padrão, ou 'T', 'M', 'A', 'B', 'C'
let geoBounds = new Map(); // código IBGE -> { x0, y0, width, height }
let zoomAnim = null;

// Eixos Triaxiais de Investigação Científica (METIS-DIR-MULTI-002)
let activeModel = 'EPS-REF-001';
let activeYear = '2017';
let activeTrajectory = 'experimental';

// Parâmetros do laboratório multimodelo
let paramK = 1500.0;
let paramQ10 = 7.272989;
let paramQ90 = 8.932076;
let paramWe = 0.33;
let paramWp = 0.33;
let paramWs = 0.34;
let paramLambda = 0.5;

const modelCatalog = {
  'EPS-REF-001': {
    name: 'EPS-REF-001 — Referência E-P-S',
    formula: 'R = E × (P + S)',
    pFormula: 'P = 50 × clamp((ln(1+dm) - q10)/(q90 - q10), 0, 1)',
    hypothesis: 'Formulação original de referência histórica com normalização da produtividade por percentis estaduais (q10 e q90).'
  },
  'EPS-EXP-002': {
    name: 'EPS-EXP-002 — Aditivo Linear Ponderado',
    formula: 'R = we·E + wp·P + ws·S',
    pFormula: 'P = 100 × dm / (dm + k)',
    hypothesis: 'Hipótese de componentes independentes combinados por soma ponderada linear, sem acoplamento multiplicativo restritivo.'
  },
  'EPS-EXP-003': {
    name: 'EPS-EXP-003 — Interativo (Acoplamento Não-Linear)',
    formula: 'R = E × (P + S) + λ·(P·S/50)',
    pFormula: 'P = 50 × dm / (dm + k)',
    hypothesis: 'Interações sinérgicas explícitas entre coesão social/cooperativa e capacidade produtiva sob modulação ecossistêmica.'
  },
  'EPS-EXP-004': {
    name: 'EPS-EXP-004 — Autônomo Municipal (DIR-MUN-001)',
    formula: 'R = E × (P + S)',
    pFormula: 'P = 50 × dm / (dm + k)',
    hypothesis: 'Análise municipal autônoma com escala declarada k, estritamente invariante a dados de outros municípios.'
  }
};

// Camada ativa de tendência territorial (R por padrão, com alternância para E, P, S)
let layer = 'resiliencia';

// Paleta de gradiente SisTer/Morfo para expressar a tendência espacial contínua
const palette = ['#08203e', '#0b406e', '#087f8c', '#109789', '#2ea8e8', '#38bdf8', '#7dd3fc'];

// Contrato de campos, limites de escala e rótulos
const fields = {
  resiliencia: ['resiliencia', 0, 90, 'Resiliência (R)'],
  evolucao: ['evolucao', -10, 10, 'Evolução Temporal (Δ R: 2006➔2017)'],
  inmet: ['inmet', 0, 3, 'Avisos Meteorológicos Ativos (INMET)'],
  adaptabrasil: ['adaptabrasil', 0, 1, 'Risco Climático Alimentos (AdaptaBrasil MCTI)'],
  ecologica: ['ecologica_multiplicador', 0.5, 1.5, 'Multiplicador Ecológico (E)'],
  produtiva: ['produtiva', 0, 50, 'Dimensão Produtiva (P)'],
  social: ['social', 0, 50, 'Dimensão Social (S)']
};

function getValue(d) {
  if (!d) return null;
  if (layer === 'evolucao') {
    const code = d.codigo_ibge;
    const r17 = scores2017.get(code)?.resiliencia;
    const r06 = scores2006.get(code)?.resiliencia;
    if (r17 == null || r06 == null || !Number.isFinite(r17) || !Number.isFinite(r06)) return null;
    return r17 - r06;
  }
  if (layer === 'inmet') {
    const code = d.codigo_ibge;
    const muniEvid = evidenciasData?.municipios?.[code];
    const avisos = muniEvid?.avisos_inmet || [];
    if (!avisos.length) return 0;
    let maxSev = 1;
    for (const a of avisos) {
      if (a.severidade === 'Grande Perigo') return 3;
      if (a.severidade === 'Perigo') maxSev = 2;
    }
    return maxSev;
  }
  if (layer === 'adaptabrasil') {
    const code = d.codigo_ibge;
    const muniEvid = evidenciasData?.municipios?.[code];
    const ind = muniEvid?.adaptabrasil?.find(x => x.indicador_id === 5001 && x.ano === 2017);
    return ind ? ind.valor : null;
  }
  if (d.status !== 'experimental') return null;
  const col = fields[layer][0];
  const v = d[col];
  return Number.isFinite(v) ? v : null;
}

function colorForValue(v) {
  if (v == null) return '#1e293b'; // dados incompletos ou ausentes
  if (layer === 'evolucao') {
    if (v > 5.0) return '#065f46';   // Ganho muito expressivo (+5 pts)
    if (v > 2.0) return '#10b981';   // Ganho moderado a forte (+2 a +5 pts)
    if (v > 0.3) return '#34d399';   // Leve ganho (+0.3 a +2 pts)
    if (v >= -0.3) return '#64748b'; // Estável (-0.3 a +0.3 pts)
    if (v >= -2.0) return '#fb923c'; // Leve perda (-0.3 a -2 pts)
    if (v >= -5.0) return '#f97316'; // Perda moderada (-2 a -5 pts)
    return '#ef4444';                // Perda expressiva (<-5 pts)
  }
  if (layer === 'inmet') {
    if (v === 3) return '#ef4444'; // Grande Perigo (Vermelho)
    if (v === 2) return '#f97316'; // Perigo (Laranja)
    if (v === 1) return '#eab308'; // Perigo Potencial (Amarelo)
    return '#1e293b';              // Sem alertas ativos
  }
  if (layer === 'adaptabrasil') {
    if (v == null) return '#1e293b';
    if (v > 0.60) return '#ef4444'; // Muito alto
    if (v > 0.40) return '#f97316'; // Alto
    if (v > 0.25) return '#eab308'; // Médio
    if (v > 0.12) return '#84cc16'; // Baixo
    return '#10b981';               // Muito baixo
  }
  const [_, min, max] = fields[layer];
  const t = Math.max(0, Math.min(1, (v - min) / (max - min)));
  const idx = Math.min(palette.length - 1, Math.floor(t * palette.length));
  return palette[idx];
}

// Cálculo formal de qualquer modelo para uma linha de dados brutos
function computeSingleModel(raw, modelId) {
  if (!raw) return null;
  const area = raw.area_estabelecimentos_ha;
  const vp = raw.valor_producao_reais;
  const past = raw.pastagem_natural_ha;
  const mata = raw.mata_natural_ha;
  const estab = raw.estabelecimentos_total;
  const orient = raw.estabelecimentos_orientacao_tecnica;
  const assoc = raw.estabelecimentos_associados;

  if (area == null || vp == null || past == null || mata == null || estab == null || orient == null || assoc == null ||
      area <= 0 || estab <= 0) {
    return { status: 'dados_incompletos', modelo: modelId };
  }

  const e0 = Math.max(0, Math.min(1, (past + mata) / area));
  const dm = vp / area;
  const socBase = (orient + assoc) / estab;

  let E, P, S, R;

  if (modelId === 'EPS-REF-001') {
    E = 0.5 + e0;
    const L = Math.log1p(dm);
    P = (paramQ90 > paramQ10) ? 50.0 * Math.max(0, Math.min(1, (L - paramQ10) / (paramQ90 - paramQ10))) : 0;
    S = 25.0 * socBase;
    R = E * (P + S);
  } else if (modelId === 'EPS-EXP-002') {
    const E_norm = 100.0 * e0;
    const P_100 = 100.0 * (dm / (dm + paramK));
    const S_100 = 50.0 * socBase;
    E = E_norm;
    P = P_100;
    S = S_100;
    R = paramWe * E_norm + paramWp * P_100 + paramWs * S_100;
  } else if (modelId === 'EPS-EXP-003') {
    E = 0.5 + e0;
    P = 50.0 * (dm / (dm + paramK));
    S = 25.0 * socBase;
    const sinergia = paramLambda * (P * S / 50.0);
    R = E * (P + S) + sinergia;
  } else {
    // EPS-EXP-004
    E = 0.5 + e0;
    P = 50.0 * (dm / (dm + paramK));
    S = 25.0 * socBase;
    R = E * (P + S);
  }

  return {
    status: 'experimental',
    modelo: modelId,
    densidade_monetaria_ha: dm,
    ecologica_indice: e0,
    ecologica_multiplicador: E,
    produtiva: P,
    social: S,
    resiliencia: R
  };
}

// Recalcular todos os municípios com o modelo ativo
function recalculateAllScores() {
  for (const [code, d] of scores) {
    const raw = rawData.get(code);
    if (raw) {
      const res = computeSingleModel(raw, activeModel);
      if (res && res.status === 'experimental') {
        d.modelo = activeModel;
        d.densidade_monetaria_ha = res.densidade_monetaria_ha;
        d.ecologica_indice = res.ecologica_indice;
        d.ecologica_multiplicador = res.ecologica_multiplicador;
        d.produtiva = res.produtiva;
        d.social = res.social;
        d.resiliencia = res.resiliencia;
        d.status = 'experimental';
      }
    }
  }
}

function csvRows(text) {
  const rows = [];
  let row = [], cur = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i + 1] === '"') { cur += '"'; i++; }
      else quoted = !quoted;
    } else if (c === ',' && !quoted) {
      row.push(cur); cur = '';
    } else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cur); cur = '';
      if (row.some(x => x.trim() !== '')) rows.push(row);
      row = [];
    } else cur += c;
  }
  if (cur.length || row.length) { row.push(cur); rows.push(row); }
  return rows;
}

function parseScores(text) {
  let rows = csvRows(text.replace(/^\uFEFF/, ''));
  if (!rows.length) throw Error('CSV vazio');
  const hdr = rows.shift();
  const m = new Map();
  for (const rr of rows) {
    const d = Object.fromEntries(hdr.map((h, i) => [h, rr[i] || '']));
    if (!d.codigo_ibge) continue;
    for (const col of ['densidade_monetaria_ha', 'ecologica_multiplicador', 'produtiva', 'social', 'resiliencia', 'ecologica_indice']) {
      d[col] = d[col] === '' || d[col] == null ? null : Number(d[col]);
    }
    m.set(String(d.codigo_ibge).trim(), d);
  }
  return m;
}

function parseRaw(text) {
  let rows = csvRows(text.replace(/^\uFEFF/, ''));
  if (!rows.length) return new Map();
  const hdr = rows.shift();
  const m = new Map();
  for (const rr of rows) {
    const d = Object.fromEntries(hdr.map((h, i) => [h, rr[i] || '']));
    if (!d.codigo_ibge) continue;
    for (const col of ['area_estabelecimentos_ha', 'pastagem_natural_ha', 'mata_natural_ha', 'valor_producao_reais', 'estabelecimentos_total', 'estabelecimentos_orientacao_tecnica', 'estabelecimentos_associados']) {
      d[col] = d[col] === '' || d[col] == null ? null : Number(d[col]);
    }
    m.set(String(d.codigo_ibge).trim(), d);
  }
  return m;
}

function getCode(p) {
  return String(p.CD_MUN ?? p.CD_MUN_22 ?? p.CD_GEOCMU ?? p.codigo_ibge ?? p.codarea ?? p.CD_MUN_2022 ?? '').trim();
}

function getName(p) {
  return String(p.NM_MUN ?? p.NM_MUN_22 ?? p.nome ?? p.NOME ?? 'Município').trim();
}

function fmt(v, d = 2) {
  return v == null || !Number.isFinite(v) ? 'Sem dado' : v.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: d });
}

function updateTriaxialSummary() {
  const modelName = modelCatalog[activeModel]?.name.split('—')[0].trim() || activeModel;
  const trajText = activeTrajectory === 'experimental' ? 'Trajetória Experimental' : 'Trajetória Histórica';
  if ($('badge-config-summary')) {
    $('badge-config-summary').textContent = `${modelName} · ${activeYear} · ${trajText}`;
  }
  if ($('metric-unit')) $('metric-unit').textContent = modelName;
  if ($('metric-model-sub')) $('metric-model-sub').textContent = modelCatalog[activeModel]?.hypothesis.slice(0, 48) + '...';
  if ($('model-hypothesis-hint')) $('model-hypothesis-hint').textContent = modelCatalog[activeModel]?.hypothesis || '';
}

function refreshMetrics() {
  let a = [...scores.values()];
  let valid = a.filter(x => x.status === 'experimental');

  if ($('metric-total')) $('metric-total').textContent = scores.size || '497';
  if ($('metric-valid')) $('metric-valid').textContent = valid.length || '492';
  if ($('metric-year')) $('metric-year').textContent = activeYear || '2017';
  updateTriaxialSummary();

  if ($('source-state')) {
    $('source-state').textContent = `Resultados: ${scores.size} registros. Modelo ativo: ${activeModel}. Metodologia METIS-DIR-MULTI-002 (laboratório multimodelo).`;
  }
}

function coordinatesOf(g) {
  if (!g) return [];
  let out = [];
  function recur(a) {
    if (typeof a[0] === 'number') { out.push(a); }
    else for (const v of a) recur(v);
  }
  recur(g.coordinates);
  return out;
}

function pathOf(g, project) {
  if (!g || !['Polygon', 'MultiPolygon'].includes(g.type)) return '';
  let rings = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  let out = '';
  for (const poly of rings) {
    for (const ring of poly) {
      ring.forEach((p, i) => {
        const [x, y] = project(p);
        out += (i ? 'L' : 'M') + x.toFixed(2) + ',' + y.toFixed(2);
      });
      out += 'Z';
    }
  }
  return out;
}

// Animação suave do viewBox no SVG
function animateViewBox(targetX, targetY, targetW, targetH, duration = 350) {
  const svg = $('map');
  if (!svg) return;
  if (zoomAnim) cancelAnimationFrame(zoomAnim);

  let startX = 0, startY = 0, startW = 740, startH = 590;
  const vb = svg.getAttribute('viewBox');
  if (vb) {
    const parts = vb.trim().split(/\s+/).map(Number);
    if (parts.length === 4 && parts.every(Number.isFinite)) {
      [startX, startY, startW, startH] = parts;
    }
  }

  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const t = Math.min(1, elapsed / duration);
    const ease = 1 - Math.pow(1 - t, 3); // cubic ease-out

    const curX = startX + (targetX - startX) * ease;
    const curY = startY + (targetY - startY) * ease;
    const curW = startW + (targetW - startW) * ease;
    const curH = startH + (targetH - startH) * ease;

    svg.setAttribute('viewBox', `${curX.toFixed(2)} ${curY.toFixed(2)} ${curW.toFixed(2)} ${curH.toFixed(2)}`);

    if (t < 1) {
      zoomAnim = requestAnimationFrame(step);
    } else {
      zoomAnim = null;
    }
  }
  zoomAnim = requestAnimationFrame(step);
}

function zoomToMunicipality(code) {
  const b = geoBounds.get(code);
  if (!b) return;

  const padW = b.width * 0.32;
  const padH = b.height * 0.32;

  let targetW = b.width + 2 * padW;
  let targetH = b.height + 2 * padH;

  const minDim = 45;
  if (targetW < minDim) targetW = minDim;
  if (targetH < minDim) targetH = minDim;

  const cx = b.x0 + b.width / 2;
  const cy = b.y0 + b.height / 2;

  const targetX = Math.max(0, Math.min(740 - targetW, cx - targetW / 2));
  const targetY = Math.max(0, Math.min(590 - targetH, cy - targetH / 2));

  animateViewBox(targetX, targetY, targetW, targetH, 350);
  if ($('btn-reset-zoom')) $('btn-reset-zoom').style.display = 'inline-flex';
}

function resetZoom() {
  animateViewBox(0, 0, 740, 590, 350);
  if ($('btn-reset-zoom')) $('btn-reset-zoom').style.display = 'none';
}

// Renderizar mapa territorial caracterizado por R (ou E, P, S) para revelar a tendência estadual
function renderMap() {
  const svg = $('map');
  if (!svg) return;
  svg.replaceChildren();
  const placeholder = $('map-placeholder');
  if (placeholder) {
    placeholder.hidden = !!geometry;
    placeholder.classList.toggle('is-hidden', !!geometry);
    placeholder.style.display = geometry ? 'none' : 'flex';
  }

  const legend = $('legend');
  if (legend) {
    if (layer === 'evolucao') {
      legend.innerHTML = `
        <div class="legend-item">
          <strong>Variação Decenal (Δ R: 2006➔2017):</strong>
          <span style="color:#ef4444; font-weight:700;">-10 (Perda)</span>
          <div class="swatch-group">
            <span class="swatch" style="background:#ef4444" title="Perda severa > 5 pts"></span>
            <span class="swatch" style="background:#f97316" title="Perda moderada 2 a 5 pts"></span>
            <span class="swatch" style="background:#fb923c" title="Perda leve 0.3 a 2 pts"></span>
            <span class="swatch" style="background:#64748b" title="Estabilidade (-0.3 a +0.3 pts)"></span>
            <span class="swatch" style="background:#34d399" title="Ganho leve 0.3 a 2 pts"></span>
            <span class="swatch" style="background:#10b981" title="Ganho moderado 2 a 5 pts"></span>
            <span class="swatch" style="background:#065f46" title="Ganho expressivo > 5 pts"></span>
          </div>
          <span style="color:#10b981; font-weight:700;">+10 (Ganho)</span>
        </div>
        <div class="legend-item"><span class="legend-dot active"></span><span>Selecionado</span></div>
        <div class="legend-item"><span class="legend-dot incomplete"></span><span>Incompleto</span></div>
      `;
    } else if (layer === 'inmet') {
      legend.innerHTML = `
        <div class="legend-item">
          <strong>Avisos Meteorológicos INMET:</strong>
          <div class="swatch-group">
            <span class="swatch" style="background:#1e293b" title="Sem alertas ativos no momento"></span>
            <span class="swatch" style="background:#eab308" title="Perigo Potencial (Amarelo)"></span>
            <span class="swatch" style="background:#f97316" title="Perigo Moderado a Severo (Laranja)"></span>
            <span class="swatch" style="background:#ef4444" title="Grande Perigo Extremo (Vermelho)"></span>
          </div>
          <span style="font-size: 0.70rem; color: #94a3b8;">Normalidade ➔ Grande Perigo</span>
        </div>
        <div class="legend-item"><span class="legend-dot active"></span><span>Selecionado</span></div>
        <div class="legend-item"><span class="legend-dot incomplete"></span><span>Incompleto</span></div>
      `;
    } else if (layer === 'adaptabrasil') {
      legend.innerHTML = `
        <div class="legend-item">
          <strong>Risco Climático (AdaptaBrasil MCTI):</strong>
          <div class="swatch-group">
            <span class="swatch" style="background:#10b981" title="Muito baixo (0 a 0.12)"></span>
            <span class="swatch" style="background:#84cc16" title="Baixo (0.12 a 0.25)"></span>
            <span class="swatch" style="background:#eab308" title="Médio (0.25 a 0.40)"></span>
            <span class="swatch" style="background:#f97316" title="Alto (0.40 a 0.60)"></span>
            <span class="swatch" style="background:#ef4444" title="Muito alto (> 0.60)"></span>
          </div>
          <span style="font-size: 0.70rem; color: #94a3b8;">Muito Baixo ➔ Muito Alto</span>
        </div>
        <div class="legend-item"><span class="legend-dot active"></span><span>Selecionado</span></div>
        <div class="legend-item"><span class="legend-dot incomplete"></span><span>Incompleto</span></div>
      `;
    } else {
      const [_, min, max, label] = fields[layer];
      const swatchesHtml = palette.map(c => `<span class="swatch" style="background:${c}"></span>`).join('');
      legend.innerHTML = `
        <div class="legend-item">
          <strong>${label}:</strong>
          <span style="opacity: 0.85;">${fmt(min, 1)}</span>
          <div class="swatch-group">${swatchesHtml}</div>
          <span style="opacity: 0.85;">${fmt(max, 1)}</span>
        </div>
        <div class="legend-item"><span class="legend-dot active"></span><span>Selecionado</span></div>
        <div class="legend-item"><span class="legend-dot incomplete"></span><span>Incompleto</span></div>
      `;
    }
  }
  if (!geometry) return;

  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const f of geometry.features) {
    for (const p of coordinatesOf(f.geometry)) {
      if (p[0] < x0) x0 = p[0];
      if (p[0] > x1) x1 = p[0];
      if (p[1] < y0) y0 = p[1];
      if (p[1] > y1) y1 = p[1];
    }
  }
  if (!Number.isFinite(x0)) return;

  const width = 740, height = 590, margin = 20;
  const s = Math.min((width - 2 * margin) / Math.max(.001, x1 - x0), (height - 2 * margin) / Math.max(.001, y1 - y0));
  const dx = (width - (x1 - x0) * s) / 2;
  const dy = (height - (y1 - y0) * s) / 2;
  const project = p => [dx + (p[0] - x0) * s, height - dy - (p[1] - y0) * s];
  const ns = 'http://www.w3.org/2000/svg';

  geoBounds.clear();

  for (const f of geometry.features) {
    const code = getCode(f.properties || {});
    const d = scores.get(code);
    const coords = coordinatesOf(f.geometry);
    const path = pathOf(f.geometry, project);
    if (!path) continue;

    let bx0 = Infinity, bx1 = -Infinity, by0 = Infinity, by1 = -Infinity;
    for (const p of coords) {
      const [px, py] = project(p);
      if (px < bx0) bx0 = px;
      if (px > bx1) bx1 = px;
      if (py < by0) by0 = py;
      if (py > by1) by1 = py;
    }
    if (Number.isFinite(bx0) && Number.isFinite(bx1)) {
      geoBounds.set(code, {
        x0: bx0,
        y0: by0,
        x1: bx1,
        y1: by1,
        width: Math.max(1, bx1 - bx0),
        height: Math.max(1, by1 - by0)
      });
    }

    const val = getValue(d);
    const el = document.createElementNS(ns, 'path');
    el.setAttribute('d', path);
    el.setAttribute('fill', colorForValue(val));

    let cls = 'map-municipality';
    if (current === code) cls += ' active';
    if (d && d.status === 'dados_incompletos') cls += ' incomplete';
    el.setAttribute('class', cls);
    el.setAttribute('tabindex', '0');
    el.setAttribute('id', 'mun-' + code);

    const title = document.createElementNS(ns, 'title');
    const munName = getName(f.properties || {});
    const valText = d ? (d.status === 'dados_incompletos' ? 'dados incompletos na fonte' : fmt(val)) : 'sem dados';
    title.textContent = `${munName} (${code}) · ${fields[layer][3]}: ${valText}`;
    el.append(title);

    el.addEventListener('click', () => choose(code, munName));
    svg.appendChild(el);
  }
}

// Calcular P e R dinamicamente com base no parâmetro k atual
function calculateP(dm, k) {
  if (dm == null || !Number.isFinite(dm) || dm < 0 || k <= 0) return null;
  return 50.0 * (dm / (dm + k));
}

function calculateR(e, p, s) {
  if (e == null || p == null || s == null) return null;
  return e * (p + s);
}

// Renderizador das 4 áreas do ambiente analítico municipal (METIS-DIR-MUN-001)
// Renderizador do ambiente analítico municipal com catálogo multimodelo (METIS-DIR-MULTI-002)
function updateComponentDetail(code) {
  const box = $('comp-detail-box');
  if (!box) return;

  if (!code) {
    box.innerHTML = '<p class="comp-empty-hint">Selecione um município no mapa para abrir sua investigação analítica individual (METIS-DIR-MULTI-002).</p>';
    return;
  }

  const d = scores.get(code);
  const raw = rawData.get(code);
  const activeRes = computeSingleModel(raw, activeModel);
  const curCat = modelCatalog[activeModel] || modelCatalog['EPS-REF-001'];

  const dm = activeRes?.densidade_monetaria_ha;
  const eVal = activeRes?.ecologica_multiplicador;
  const pVal = activeRes?.produtiva;
  const sVal = activeRes?.social;
  const rVal = activeRes?.resiliencia;

  const area = raw?.area_estabelecimentos_ha;
  const vp = raw?.valor_producao_reais;
  const pastagem = raw?.pastagem_natural_ha;
  const mata = raw?.mata_natural_ha;
  const nTot = raw?.estabelecimentos_total;
  const nAss = raw?.estabelecimentos_orientacao_tecnica;
  const nCoop = raw?.estabelecimentos_associados;

  // Atualizar barras de resumo no painel superior
  if (rVal != null) {
    if ($('detail-r')) $('detail-r').textContent = fmt(rVal, 2);
    if ($('detail-e')) $('detail-e').textContent = `${fmt(eVal, 2)} ${activeModel === 'EPS-EXP-002' ? 'pts' : '×'}`;
    if ($('detail-p')) $('detail-p').textContent = `${fmt(pVal, 2)} ${activeModel === 'EPS-EXP-002' ? '/ 100' : '/ 50'}`;
    if ($('detail-s')) $('detail-s').textContent = `${fmt(sVal, 2)} ${activeModel === 'EPS-EXP-002' ? '/ 100' : '/ 50'}`;

    if ($('bar-r')) $('bar-r').style.width = Math.min(100, (rVal / 100) * 100) + '%';
    if ($('bar-e')) $('bar-e').style.width = Math.min(100, Math.max(0, activeModel === 'EPS-EXP-002' ? eVal : ((eVal - 0.5) / 1.0 * 100))) + '%';
    if ($('bar-p')) $('bar-p').style.width = Math.min(100, activeModel === 'EPS-EXP-002' ? pVal : ((pVal / 50) * 100)) + '%';
    if ($('bar-s')) $('bar-s').style.width = Math.min(100, activeModel === 'EPS-EXP-002' ? sVal : ((sVal / 50) * 100)) + '%';
  } else {
    if ($('detail-r')) $('detail-r').textContent = '—';
    if ($('detail-e')) $('detail-e').textContent = '—';
    if ($('detail-p')) $('detail-p').textContent = '—';
    if ($('detail-s')) $('detail-s').textContent = '—';
    if ($('bar-r')) $('bar-r').style.width = '0%';
    if ($('bar-e')) $('bar-e').style.width = '0%';
    if ($('bar-p')) $('bar-p').style.width = '0%';
    if ($('bar-s')) $('bar-s').style.width = '0%';
  }

  // ÁREA D: RESULTADOS DO MODELO ATIVO
  if (activeArea === 'D') {
    let noteText = '';
    if (d && d.status === 'dados_incompletos') {
      noteText = 'Variáveis essenciais estão ausentes no Censo 2017 para este município. Por rigor metodológico, o MÉTIS não substitui dados ausentes por zero nem realiza imputações.';
    } else {
      noteText = `Modelo ativo: ${curCat.name}. Densidade monetária observada dm = ${fmt(dm, 2)} R$/ha. A escolha do modelo constitui decisão explícita do pesquisador.`;
    }

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área D · Resultados &amp; Diagnóstico</strong>
        <span class="score-tag">${rVal != null ? 'R = ' + fmt(rVal, 2) : 'Não calculado'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Modelo Ativo</td><td class="val">${curCat.name}</td></tr>
        <tr><td>Densidade monetária da produção (dm)</td><td class="val">${dm != null ? 'R$ ' + fmt(dm, 2) + '/ha' : '—'}</td></tr>
        <tr><td>Multiplicador Ecológico (E)</td><td class="val">${eVal != null ? fmt(eVal, 3) + (activeModel === 'EPS-EXP-002' ? ' pts' : '×') : '—'}</td></tr>
        <tr><td>Dimensão Produtiva (P)</td><td class="val">${pVal != null ? fmt(pVal, 2) : '—'}</td></tr>
        <tr><td>Dimensão Social (S)</td><td class="val">${sVal != null ? fmt(sVal, 2) : '—'}</td></tr>
        <tr><td>Estado de Resiliência Hipotético (R)</td><td class="val">${rVal != null ? fmt(rVal, 2) : '—'}</td></tr>
      </table>
      <div class="comp-formula-box">
        ${curCat.formula}
      </div>
      <div class="comp-note-box">
        ${noteText}
      </div>
      <div class="comp-note-box warning" style="margin-top: 4px;">
        <strong>Advertência Epistêmica:</strong> O valor de R resulta da hipótese selecionada e não de validação empírica observada de resiliência. Use a aba <strong>M · Confronto</strong> para comparar com os outros modelos.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Laboratório Multimodelo METIS-DIR-MULTI-002 · Ano ${activeYear}</span>
      </div>
    `;
  }
  // ÁREA T: TRAJETÓRIA DECENAL (2006 ➔ 2017)
  else if (activeArea === 'T') {
    const raw06 = rawData2006.get(code);
    const raw17 = rawData2017.get(code);
    const res06 = computeSingleModel(raw06, activeModel);
    const res17 = computeSingleModel(raw17, activeModel);

    const r06 = res06?.resiliencia;
    const r17 = res17?.resiliencia;
    const deltaR = (r17 != null && r06 != null) ? (r17 - r06) : null;

    let deltaRHtml = '—';
    let summaryText = '';

    if (deltaR != null) {
      const cls = deltaR > 0.5 ? 'traj-delta-pos' : (deltaR < -0.5 ? 'traj-delta-neg' : 'traj-delta-neutral');
      const sign = deltaR > 0 ? '+' : '';
      deltaRHtml = `<span class="traj-delta-badge ${cls}">${sign}${fmt(deltaR, 2)} pts</span>`;

      if (deltaR > 3.0) {
        summaryText = `<strong>Trajetória de Expansão de Resiliência (+${fmt(deltaR, 1)} pts):</strong> O município apresentou ganho consistente na década, impulsionado pelo fortalecimento de seus fatores determinantes.`;
      } else if (deltaR > 0.5) {
        summaryText = `<strong>Trajetória de Evolução Moderada (+${fmt(deltaR, 1)} pts):</strong> Crescimento positivo gradual da resiliência agroterritorial entre 2006 e 2017.`;
      } else if (deltaR >= -0.5) {
        summaryText = `<strong>Trajetória de Estabilidade Relativa (${sign}${fmt(deltaR, 1)} pts):</strong> O município preservou sua estrutura de resiliência territorial praticamente inalterada no decênio.`;
      } else if (deltaR >= -3.0) {
        summaryText = `<strong>Trajetória de Perda Moderada (${fmt(deltaR, 1)} pts):</strong> Redução no índice de resiliência, sugerindo aumento de vulnerabilidade territorial ou pressão nos fatores ecológico/produtivos.`;
      } else {
        summaryText = `<strong>Trajetória Crítica de Redução (${fmt(deltaR, 1)} pts):</strong> Perda severa de resiliência agroterritorial no período, recomendando auditoria aprofundada nas causas de supressão ou estagnação.`;
      }
    } else {
      summaryText = `<strong>Dados Incompletos em um dos Censos:</strong> Não foi possível calcular a variação decenal estrita para este município devido à ausência de observações completas em 2006 ou 2017 (ex: emancipação política ou sigilo estatístico).`;
    }

    function rowDiff(label, v06, v17, unit = '', digits = 1, isPercent = false) {
      if (v06 == null && v17 == null) return `<tr><td>${label}</td><td class="val">—</td><td class="val">—</td><td class="val">—</td></tr>`;
      const d06 = v06 != null ? fmt(v06, digits) + unit : '—';
      const d17 = v17 != null ? fmt(v17, digits) + unit : '—';
      let dHtml = '—';
      if (v06 != null && v17 != null) {
        const diff = v17 - v06;
        const sign = diff > 0 ? '+' : '';
        const cls = diff > 0.001 ? 'traj-delta-pos' : (diff < -0.001 ? 'traj-delta-neg' : 'traj-delta-neutral');
        const pcent = v06 !== 0 ? ` (${sign}${fmt((diff / Math.abs(v06)) * 100, 1)}%)` : '';
        dHtml = `<span class="traj-delta-badge ${cls}">${sign}${fmt(diff, digits)}${unit}${isPercent ? '' : pcent}</span>`;
      }
      return `<tr><td>${label}</td><td class="val">${d06}</td><td class="val">${d17}</td><td class="val" style="text-align:right;">${dHtml}</td></tr>`;
    }

    const e06 = res06?.ecologica_multiplicador;
    const e17 = res17?.ecologica_multiplicador;
    const p06 = res06?.produtiva;
    const p17 = res17?.produtiva;
    const s06 = res06?.social;
    const s17 = res17?.social;

    const area06 = raw06?.area_estabelecimentos_ha;
    const area17 = raw17?.area_estabelecimentos_ha;
    const mata06 = raw06?.mata_natural_ha;
    const mata17 = raw17?.mata_natural_ha;
    const past06 = raw06?.pastagem_natural_ha;
    const past17 = raw17?.pastagem_natural_ha;
    const vp06 = raw06?.valor_producao_reais;
    const vp17 = raw17?.valor_producao_reais;

    const orient06 = (raw06?.estabelecimentos_total > 0 && raw06?.estabelecimentos_orientacao_tecnica != null) ? (raw06.estabelecimentos_orientacao_tecnica / raw06.estabelecimentos_total * 100) : null;
    const orient17 = (raw17?.estabelecimentos_total > 0 && raw17?.estabelecimentos_orientacao_tecnica != null) ? (raw17.estabelecimentos_orientacao_tecnica / raw17.estabelecimentos_total * 100) : null;

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área T · Trajetória Decenal (2006 ➔ 2017)</strong>
        ${deltaRHtml}
      </div>
      <p style="font-size: 0.72rem; color: #475569; margin: 4px 0 8px;">
        Evolução multitemporal observada entre os Censos Agropecuários Oficiais do IBGE:
      </p>
      <table class="comp-table">
        <thead>
          <tr style="border-bottom: 1px solid var(--line); font-size: 0.70rem; color: var(--muted);">
            <th>Componente / Insumo</th>
            <th style="text-align:right;">2006</th>
            <th style="text-align:right;">2017</th>
            <th style="text-align:right;">Variação (Δ)</th>
          </tr>
        </thead>
        <tbody>
          <tr style="font-weight: 750; background: var(--bg);">
            <td>Resiliência Territorial (R)</td>
            <td class="val">${r06 != null ? fmt(r06, 2) : '—'}</td>
            <td class="val">${r17 != null ? fmt(r17, 2) : '—'}</td>
            <td class="val" style="text-align:right;">${deltaRHtml}</td>
          </tr>
          ${rowDiff('Multiplicador Ecológico (E)', e06, e17, activeModel === 'EPS-EXP-002' ? ' pts' : '×', 3)}
          ${rowDiff('Dimensão Produtiva (P)', p06, p17, '', 2)}
          ${rowDiff('Dimensão Social (S)', s06, s17, '', 2)}
          <tr style="border-top: 1px dashed var(--line);"><td colspan="4" style="padding: 2px 0;"></td></tr>
          ${rowDiff('Mata Natural', mata06, mata17, ' ha', 0)}
          ${rowDiff('Pastagem Natural', past06, past17, ' ha', 0)}
          ${rowDiff('Área Estabelecimentos', area06, area17, ' ha', 0)}
          ${rowDiff('Valor da Produção', vp06 != null ? vp06 / 1e6 : null, vp17 != null ? vp17 / 1e6 : null, ' M R$', 2)}
          ${rowDiff('Assistência Técnica', orient06, orient17, '%', 1, true)}
        </tbody>
      </table>
      <div class="traj-summary-box" style="margin-top: 8px;">
        ${summaryText}
      </div>
      <div class="comp-provenance-box" style="margin-top: 6px;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Série Histórica Auditada · IBGE Censo 2006 e 2017</span>
      </div>
    `;
  }
  // ÁREA E: EVIDÊNCIAS EPISTÊMICAS (AdaptaBrasil MCTI + INMET + METIS-DIR-EVID-001)
  else if (activeArea === 'E') {
    const muniEvid = evidenciasData?.municipios?.[code];
    const avisos = muniEvid?.avisos_inmet || [];
    const adapta = muniEvid?.adaptabrasil || [];
    const eps = episodiosData?.por_municipio?.[code] || [];

    // 0. Episódios Investigativos Ativos (METIS-DIR-EVID-001)
    let epsHtml = '';
    if (eps.length > 0) {
      epsHtml = eps.map(ep => {
        const estadoLabels = {
          'ameaca_anunciada': 'Ameaça Anunciada',
          'em_verificacao': 'Em Verificação Operacional',
          'impactos_respostas': 'Impactos & Respostas Documentadas',
          'avaliacao_concluida': 'Avaliação Concluída'
        };
        const estadoBadge = estadoLabels[ep.estado_episodio] || ep.estado_episodio;
        const rBasal = ep.estado_metis_congelado?.resiliencia;
        const rBasalStr = rBasal != null ? fmt(rBasal, 2) : '—';

        return `
          <div class="episode-card">
            <div class="episode-header-row">
              <span class="episode-state-badge">🔬 ${escapeHtml(estadoBadge)}</span>
              <span style="font-size:0.66rem; color:#64748b; font-family:monospace;">${escapeHtml(ep.id)}</span>
            </div>
            <strong style="color:var(--navy); font-size:0.75rem;">Ameaça: ${escapeHtml(ep.tipo_ameaca)} (${escapeHtml(ep.severidade)})</strong>
            <div style="font-size:0.68rem; color:#64748b; margin:2px 0 4px;">
              Janela: ${ep.janela_inicio ? ep.janela_inicio.substring(0, 16).replace('T', ' ') : '—'} até ${ep.janela_fim ? ep.janela_fim.substring(0, 16).replace('T', ' ') : '—'}
            </div>
            <div class="episode-hypothesis-box">
              <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                <span>Estado Basal MÉTIS (t₀ congelado):</span>
                <strong>R = ${rBasalStr}</strong>
              </div>
              <div style="font-size:0.67rem; color:#64748b;">
                Hipótese sob estresse: O município sustentará suas funções ecológicas, produtivas e sociais diante desta perturbação?
              </div>
              <div style="margin-top:4px; font-weight:700; color:#4338ca;">
                Status Epistêmico: ${escapeHtml(ep.desfecho_cientifico === 'em_aberto' ? 'Confrontação em aberto (aguardando dados pós-evento)' : ep.desfecho_cientifico)}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    // 1. Avisos INMET Operacionais
    let inmetHtml = '';
    if (avisos.length > 0) {
      inmetHtml = avisos.map(a => {
        let cardCls = '';
        if (a.severidade === 'Grande Perigo') cardCls = '';
        else if (a.severidade === 'Perigo') cardCls = 'warning-moderate';
        else cardCls = 'warning-potential';

        const riscosList = (a.riscos || []).map(r => `<li>${escapeHtml(r)}</li>`).join('');
        const instrucoesList = (a.instrucoes || []).map(i => `<li>${escapeHtml(i)}</li>`).join('');

        return `
          <div class="inmet-alert-card ${cardCls}">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:4px;">
              <span class="inmet-badge" style="background:${a.cor || '#eab308'};">⚠️ ${escapeHtml(a.severidade)}</span>
              <span style="font-size:0.67rem; color:#64748b; font-weight:600;">INMET Operacional (${escapeHtml(a.estado_vigencia || 'vigente')})</span>
            </div>
            <strong style="color:#0f172a; font-size:0.75rem;">${escapeHtml(a.descricao)}</strong>
            <div style="font-size:0.68rem; color:#64748b; margin:2px 0 6px;">
              <span>Vigência: ${escapeHtml(a.inicio.replace('T', ' ').substring(0, 16))} até ${escapeHtml(a.fim.replace('T', ' ').substring(0, 16))}</span>
            </div>
            ${riscosList ? `<div style="font-size:0.68rem; margin-bottom:4px;"><strong>Riscos declarados:</strong> <ul style="margin:2px 0 0 14px; padding:0;">${riscosList}</ul></div>` : ''}
            ${instrucoesList ? `<div style="font-size:0.68rem; color:#0369a1;"><strong>Instruções de Defesa Civil:</strong> <ul style="margin:2px 0 0 14px; padding:0;">${instrucoesList}</ul></div>` : ''}
          </div>
        `;
      }).join('');
    } else {
      inmetHtml = `
        <div class="inmet-calm-box">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
          <div>
            <strong>Sem avisos meteorológicos vigentes emitidos pelo INMET</strong>
            <p style="margin:2px 0 0; font-size:0.67rem; opacity:0.85; color:#166534;">A ausência de alerta meteorológico oficial não comprova ausência de perturbação no território nem garante resiliência.</p>
          </div>
        </div>
      `;
    }

    // 2. Indicadores AdaptaBrasil
    let adaptaHtml = '';
    if (adapta.length > 0) {
      const baselines = adapta.filter(x => x.cenario.startsWith('baseline'));
      const projecoes = adapta.filter(x => !x.cenario.startsWith('baseline'));

      const metersHtml = baselines.map(ind => {
        const valPct = Math.min(100, Math.max(0, (ind.valor || 0) * 100));
        return `
          <div class="climate-meter-row">
            <div class="climate-meter-label">
              <span>${escapeHtml(ind.nome)} (${ind.ano})</span>
              <strong style="color:${ind.cor || 'var(--navy)'}">${fmt(ind.valor, 2)} · ${escapeHtml(ind.classe)}</strong>
            </div>
            <div class="climate-bar-bg">
              <div class="climate-bar-fill" style="width:${valPct}%; background:${ind.cor || '#10b981'};"></div>
            </div>
          </div>
        `;
      }).join('');

      let projHtml = '';
      if (projecoes.length > 0) {
        const projRows = projecoes.map(p => `
          <tr>
            <td>${escapeHtml(p.nome)}</td>
            <td style="text-align:center;"><strong>${p.ano}</strong></td>
            <td style="text-align:right;">${fmt(p.valor, 2)}</td>
            <td style="text-align:right;"><span style="color:${p.cor || 'var(--navy)'}; font-weight:700;">${escapeHtml(p.classe)}</span></td>
          </tr>
        `).join('');

        projHtml = `
          <div style="margin-top: 10px;">
            <span style="font-size:0.70rem; font-weight:700; color:#475569; text-transform:uppercase;">Projeções Climáticas (IPCC AR5 / RCP4.5):</span>
            <table class="comp-table" style="margin-top: 4px;">
              <thead>
                <tr style="font-size:0.67rem; color:var(--muted);">
                  <th>Dimensão / Cenário</th>
                  <th style="text-align:center;">Ano</th>
                  <th style="text-align:right;">Índice</th>
                  <th style="text-align:right;">Classe</th>
                </tr>
              </thead>
              <tbody>${projRows}</tbody>
            </table>
          </div>
        `;
      }

      adaptaHtml = `
        <div style="margin-top: 6px;">
          ${metersHtml}
          ${projHtml}
        </div>
      `;
    } else {
      adaptaHtml = `<p style="font-size: 0.72rem; color: #64748b;">Nenhum dado do AdaptaBrasil sincronizado para este município.</p>`;
    }

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área E · Evidências Epistêmicas &amp; Perturbações</strong>
        <span class="score-tag">${avisos.length > 0 ? '⚠️ Alerta Ativo' : '✓ Sem Avisos'}</span>
      </div>
      <p style="font-size: 0.72rem; color: #475569; margin: 4px 0 10px;">
        Confronto empírico do território sob estresse meteorológico e riscos climáticos auditados:
      </p>

      ${epsHtml ? `
        <div class="evidence-section-block">
          <div class="evidence-block-header">
            <span class="evidence-block-title" style="color:#4338ca;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
              Episódios Investigativos (METIS-DIR-EVID-001)
            </span>
            <span style="font-size:0.67rem; color:#6366f1; font-weight:700;">${eps.length} episódio(s)</span>
          </div>
          ${epsHtml}
        </div>
      ` : ''}

      <div class="evidence-section-block">
        <div class="evidence-block-header">
          <span class="evidence-block-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>
            INMET · Avisos Meteorológicos Operacionais
          </span>
          <span style="font-size:0.67rem; color:#64748b;">${avisos.length} aviso(s) vigente(s)</span>
        </div>
        ${inmetHtml}
      </div>

      <div class="evidence-section-block" style="margin-top:12px;">
        <div class="evidence-block-header">
          <span class="evidence-block-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
            AdaptaBrasil MCTI · Riscos Climáticos Estruturais
          </span>
          <span style="font-size:0.67rem; color:#64748b;">Segurança Alimentar e Desastres</span>
        </div>
        ${adaptaHtml}
      </div>

      <div class="comp-note-box" style="margin-top: 10px;">
        <strong>Princípio Epistêmico:</strong> Indicadores climáticos e avisos meteorológicos não alteram a fórmula de <em>R</em>. Constituem a bancada empírica para testar se os municípios resilientes efetivamente resistiram e adaptaram-se às perturbações documentadas.
      </div>
      <div class="comp-provenance-box" style="margin-top: 6px;">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Fontes: MCTI/AdaptaBrasil &amp; INMET/CPTEC · Proveniência SHA-256</span>
      </div>
    `;
  }
  // ÁREA M: CONFRONTO MULTIMODELO PARA O MUNICÍPIO
  else if (activeArea === 'M') {
    const mRef = computeSingleModel(raw, 'EPS-REF-001');
    const mExp2 = computeSingleModel(raw, 'EPS-EXP-002');
    const mExp3 = computeSingleModel(raw, 'EPS-EXP-003');
    const mExp4 = computeSingleModel(raw, 'EPS-EXP-004');

    const refR = mRef?.resiliencia;
    const list = [
      { id: 'EPS-REF-001', res: mRef, cat: modelCatalog['EPS-REF-001'] },
      { id: 'EPS-EXP-002', res: mExp2, cat: modelCatalog['EPS-EXP-002'] },
      { id: 'EPS-EXP-003', res: mExp3, cat: modelCatalog['EPS-EXP-003'] },
      { id: 'EPS-EXP-004', res: mExp4, cat: modelCatalog['EPS-EXP-004'] }
    ];

    const rowsHtml = list.map(item => {
      const isAct = item.id === activeModel;
      const r = item.res?.resiliencia;
      const diff = (r != null && refR != null) ? (r - refR) : null;
      let diffHtml = '—';
      if (item.id === 'EPS-REF-001') {
        diffHtml = '<span class="confrontation-diff zero">Referência</span>';
      } else if (diff != null) {
        const cls = diff > 0.05 ? 'pos' : (diff < -0.05 ? 'neg' : 'zero');
        const sign = diff > 0 ? '+' : '';
        diffHtml = `<span class="confrontation-diff ${cls}">${sign}${fmt(diff, 2)}</span>`;
      }

      return `
        <tr class="${isAct ? 'active-model-row' : ''}">
          <td>
            <span class="confrontation-model-tag">${item.id} ${isAct ? '★ (Ativo)' : ''}</span>
            <span class="confrontation-sub">${item.cat.formula}</span>
          </td>
          <td>${fmt(item.res?.ecologica_multiplicador, 2)}</td>
          <td>${fmt(item.res?.produtiva, 1)}</td>
          <td>${fmt(item.res?.social, 1)}</td>
          <td><strong>${fmt(r, 2)}</strong></td>
          <td>${diffHtml}</td>
        </tr>
      `;
    }).join('');

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área M · Confronto Multimodelo</strong>
        <span class="score-tag">Intramunicipal</span>
      </div>
      <p style="font-size: 0.72rem; color: #475569; margin: 4px 0 8px;">
        Confronto das 4 hipóteses do catálogo sob os <strong>mesmos dados observados</strong> de ${d?.municipio || 'deste município'}:
      </p>
      <table class="confrontation-table">
        <thead>
          <tr>
            <th>Modelo</th>
            <th>E</th>
            <th>P</th>
            <th>S</th>
            <th>R</th>
            <th>Δ vs REF</th>
          </tr>
        </thead>
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
      <div class="comp-note-box" style="margin-top: 10px;">
        <strong>Conclusão Epistêmica:</strong> A variação entre os valores decorre estritamente da estrutura matemática de cada hipótese (acoplamento multiplicativo, independência aditiva ou sinergia não-linear), não de variações nos dados do território.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Critério 5 METIS-DIR-MULTI-002: Comparar modelos exclusivamente no contexto do município.</span>
      </div>
    `;
  }
  // ÁREA A: OBSERVAÇÕES DO MUNICÍPIO
  else if (activeArea === 'A') {
    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área A · Observações do Município</strong>
        <span class="score-tag">Censo Agro 2017</span>
      </div>
      <table class="comp-table">
        <tr><td>Área dos estabelecimentos agropecuários</td><td class="val">${area != null ? area.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Pastagens naturais declaradas</td><td class="val">${pastagem != null ? pastagem.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Matas e florestas naturais</td><td class="val">${mata != null ? mata.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Valor da produção agropecuária (VP)</td><td class="val">${vp != null ? 'R$ ' + vp.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Total de estabelecimentos</td><td class="val">${nTot != null ? nTot.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Estabelecimentos com assistência técnica</td><td class="val">${nAss != null ? nAss.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Estabelecimentos associados a cooperativa</td><td class="val">${nCoop != null ? nCoop.toLocaleString('pt-BR') : '—'}</td></tr>
      </table>
      <div class="comp-note-box">
        Observáveis censitários originais circunscritos aos estabelecimentos agropecuários do município. Idênticos para todos os modelos do catálogo.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>IBGE SIDRA · Tabelas 6881, 6898, 6780, 6773</span>
      </div>
    `;
  }
  // ÁREA B: PARAMETRIZAÇÃO EXPERIMENTAL
  else if (activeArea === 'B') {
    let paramControlsHtml = '';
    const isFrozen = (activeTrajectory === 'historica');
    const disabledAttr = isFrozen ? 'disabled="disabled"' : '';
    const frozenBanner = isFrozen ? `
      <div class="frozen-params-banner">
        🔒 <strong>Trajetória Histórica Imutável:</strong> Os parâmetros estão fixados no padrão homologado para reprodução científica. Para simular e calibrar valores interativamente, selecione <strong>Experimental</strong> no Eixo 3.
      </div>
    ` : '';

    if (activeModel === 'EPS-REF-001') {
      paramControlsHtml = `
        <table class="comp-table">
          <tr><td>Corte Percentil q10</td><td class="val">${fmt(paramQ10, 3)} (ln 1+dm)</td></tr>
          <tr><td>Corte Percentil q90</td><td class="val">${fmt(paramQ90, 3)} (ln 1+dm)</td></tr>
          <tr><td>Natureza da Calibração</td><td class="val">Distribuição empírica RS (496 mun)</td></tr>
        </table>
        <div class="comp-note-box" style="margin-top: 8px;">
          O EPS-REF-001 utiliza percentis estaduais fixos. Seus parâmetros não devem ser alterados para preservar a reprodução histórica.
        </div>
      `;
    } else if (activeModel === 'EPS-EXP-002') {
      paramControlsHtml = `
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Peso Ecológico (we):</strong>
            <span id="disp-we">${fmt(paramWe, 2)}</span>
          </div>
          <input type="range" class="param-slider" id="slider-we" min="0.1" max="0.8" step="0.05" value="${paramWe}" ${disabledAttr}/>
        </div>
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Peso Produtivo (wp):</strong>
            <span id="disp-wp">${fmt(paramWp, 2)}</span>
          </div>
          <input type="range" class="param-slider" id="slider-wp" min="0.1" max="0.8" step="0.05" value="${paramWp}" ${disabledAttr}/>
        </div>
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Escala k (Produtiva):</strong>
            <span id="disp-k2">${fmt(paramK, 0)} R$/ha</span>
          </div>
          <input type="range" class="param-slider" id="slider-k2" min="300" max="6000" step="100" value="${paramK}" ${disabledAttr}/>
        </div>
      `;
    } else if (activeModel === 'EPS-EXP-003') {
      paramControlsHtml = `
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Intensidade Sinergia (λ):</strong>
            <span id="disp-lambda">${fmt(paramLambda, 2)}</span>
          </div>
          <input type="range" class="param-slider" id="slider-lambda" min="0" max="1.0" step="0.05" value="${paramLambda}" ${disabledAttr}/>
        </div>
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Escala k (Produtiva):</strong>
            <span id="disp-k3">${fmt(paramK, 0)} R$/ha</span>
          </div>
          <input type="range" class="param-slider" id="slider-k3" min="300" max="6000" step="100" value="${paramK}" ${disabledAttr}/>
        </div>
      `;
    } else {
      // EPS-EXP-004
      paramControlsHtml = `
        <div class="param-control-group">
          <div class="param-control-header">
            <strong>Parâmetro de Escala k:</strong>
            <span id="param-k-display">${fmt(paramK, 0)} R$/ha</span>
          </div>
          <div class="param-input-wrap">
            <input type="range" class="param-slider" id="param-k-slider" min="300" max="6000" step="100" value="${paramK}" ${disabledAttr}/>
            <input type="number" class="param-val-input" id="param-k-input" min="100" max="20000" step="50" value="${paramK}" ${disabledAttr}/>
          </div>
        </div>
      `;
    }

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área B · Parametrização ${isFrozen ? 'Homologada (Fixa)' : 'Experimental'}</strong>
        <span class="score-tag">${activeModel}</span>
      </div>
      ${frozenBanner}
      ${paramControlsHtml}
      <div class="comp-note-box" style="margin-top: 8px;">
        ${isFrozen ? 'Parâmetros imutáveis protegidos pela portaria científica.' : 'Em modalidade experimental, a alteração dos parâmetros reconfigura o modelo e atualiza a cartografia e o diagnóstico em tempo real.'}
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Trajetória: ${activeTrajectory === 'experimental' ? 'Experimental (Interativa)' : 'Histórica (Fixa / Imutável)'}</span>
      </div>
    `;

    // Vincular listeners específicos de cada modelo
    if (activeModel === 'EPS-EXP-004') {
      const slider = $('param-k-slider');
      const input = $('param-k-input');
      const display = $('param-k-display');
      const onKChange = val => {
        const num = Number(val);
        if (num > 0 && Number.isFinite(num)) {
          paramK = num;
          if (slider) slider.value = String(num);
          if (input) input.value = String(num);
          if (display) display.textContent = `${fmt(num, 0)} R$/ha`;
          recalculateAllScores();
          updateComponentDetail(code);
          renderMap();
        }
      };
      if (slider) slider.addEventListener('input', ev => onKChange(ev.target.value));
      if (input) input.addEventListener('change', ev => onKChange(ev.target.value));
    } else if (activeModel === 'EPS-EXP-002') {
      const slWe = $('slider-we'), slWp = $('slider-wp'), slK = $('slider-k2');
      if (slWe) slWe.addEventListener('input', ev => {
        paramWe = Number(ev.target.value);
        paramWs = Math.max(0, 1.0 - paramWe - paramWp);
        $('disp-we').textContent = fmt(paramWe, 2);
        recalculateAllScores();
        updateComponentDetail(code);
        renderMap();
      });
      if (slWp) slWp.addEventListener('input', ev => {
        paramWp = Number(ev.target.value);
        paramWs = Math.max(0, 1.0 - paramWe - paramWp);
        $('disp-wp').textContent = fmt(paramWp, 2);
        recalculateAllScores();
        updateComponentDetail(code);
        renderMap();
      });
      if (slK) slK.addEventListener('input', ev => {
        paramK = Number(ev.target.value);
        $('disp-k2').textContent = `${fmt(paramK, 0)} R$/ha`;
        recalculateAllScores();
        updateComponentDetail(code);
        renderMap();
      });
    } else if (activeModel === 'EPS-EXP-003') {
      const slLam = $('slider-lambda'), slK = $('slider-k3');
      if (slLam) slLam.addEventListener('input', ev => {
        paramLambda = Number(ev.target.value);
        $('disp-lambda').textContent = fmt(paramLambda, 2);
        recalculateAllScores();
        updateComponentDetail(code);
        renderMap();
      });
      if (slK) slK.addEventListener('input', ev => {
        paramK = Number(ev.target.value);
        $('disp-k3').textContent = `${fmt(paramK, 0)} R$/ha`;
        recalculateAllScores();
        updateComponentDetail(code);
        renderMap();
      });
    }
  }
  // ÁREA C: HIPÓTESE RELACIONAL
  else if (activeArea === 'C') {
    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área C · Hipótese Relacional</strong>
        <span class="score-tag">${activeModel}</span>
      </div>
      <div class="comp-formula-box" style="font-size: 0.85rem; padding: 10px;">
        ${curCat.formula}
      </div>
      <table class="comp-table">
        <tr><td>Modelo</td><td class="val">${curCat.name}</td></tr>
        <tr><td>Hipótese Científica</td><td class="val">${curCat.hypothesis}</td></tr>
        <tr><td>Transformação de P</td><td class="val">${curCat.pFormula}</td></tr>
      </table>
      <div class="comp-note-box">
        Cada modelo no MÉTIS expressa uma pergunta científica distinta. As divergências entre os resultados refletem os limites teóricos das formulações concorrentes.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Diretriz METIS-DIR-MULTI-002 · Catálogo Experimental</span>
      </div>
    `;
  }
}

function choose(code, name) {
  current = code;
  if (!code) {
    if ($('detail-name')) $('detail-name').textContent = 'Selecione um município';
    if ($('detail-code')) $('detail-code').textContent = 'Clique na malha territorial ou busque acima';
    if ($('climate-quick-badge')) $('climate-quick-badge').style.display = 'none';
    if ($('status-alert')) $('status-alert').style.display = 'none';
    if ($('detail-r')) $('detail-r').textContent = '—';
    if ($('detail-e')) $('detail-e').textContent = '—';
    if ($('detail-p')) $('detail-p').textContent = '—';
    if ($('detail-s')) $('detail-s').textContent = '—';
    if ($('bar-r')) $('bar-r').style.width = '0%';
    if ($('bar-e')) $('bar-e').style.width = '0%';
    if ($('bar-p')) $('bar-p').style.width = '0%';
    if ($('bar-s')) $('bar-s').style.width = '0%';
    updateComponentDetail(null);
    document.querySelectorAll('.map-municipality').forEach(el => el.classList.remove('active'));
    resetZoom();
    return;
  }

  const d = scores.get(code);
  const raw = rawData.get(code);

  const munName = name || d?.municipio || raw?.municipio || 'Município';
  if ($('detail-name')) $('detail-name').textContent = munName;
  if ($('detail-code')) $('detail-code').textContent = `Código IBGE: ${code} ${d ? '· ' + d.status : ''}`;

  const climateBadge = $('climate-quick-badge');
  if (climateBadge) {
    const muniEvid = evidenciasData?.municipios?.[code];
    const ind5001 = muniEvid?.adaptabrasil?.find(x => x.indicador_id === 5001 && x.ano === 2017);
    const avisos = muniEvid?.avisos_inmet || [];

    if (ind5001) {
      climateBadge.style.display = 'flex';
      climateBadge.style.alignItems = 'center';
      climateBadge.style.justifyContent = 'space-between';
      climateBadge.style.gap = '8px';

      const alertStr = avisos.length > 0 
        ? `⚠️ <span style="color:#b45309; font-weight:700;">${avisos.length} Alerta INMET</span>` 
        : `✓ <span style="color:#15803d;">Sem alertas INMET</span>`;

      climateBadge.innerHTML = `
        <div style="line-height:1.35;">
          <div>🌱 <strong>AdaptaBrasil:</strong> Risco <span style="color:${ind5001.cor || 'var(--teal)'}; font-weight:750;">${fmt(ind5001.valor, 2)} (${escapeHtml(ind5001.classe)})</span></div>
          <div style="font-size:0.67rem; color:#64748b; margin-top:1px;">${alertStr}</div>
        </div>
        <button id="btn-goto-evid" type="button" style="background:#e0e7ff; color:#4338ca; border:1px solid #c7d2fe; padding:3px 7px; border-radius:4px; font-size:0.67rem; font-weight:700; cursor:pointer; white-space:nowrap;">
          Ver Evidências →
        </button>
      `;

      const btnGo = $('btn-goto-evid');
      if (btnGo) {
        btnGo.onclick = () => {
          activeArea = 'E';
          document.querySelectorAll('.comp-tab-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.area === 'E');
          });
          updateComponentDetail(code);
        };
      }
    } else {
      climateBadge.style.display = 'none';
    }
  }

  const statusAlert = $('status-alert');
  if (statusAlert) {
    if (d && d.status === 'dados_incompletos') {
      statusAlert.style.display = 'block';
      statusAlert.innerHTML = '⚠️ <strong>Dados Incompletos no Censo 2017:</strong> Variáveis essenciais não foram divulgadas pelo IBGE (por omissão amostral ou sigilo). Por rigor metodológico, o MÉTIS não realiza imputações fictícias.';
    } else {
      statusAlert.style.display = 'none';
    }
  }

  // Atualizar detalhamento analítico na área ativa
  updateComponentDetail(code);

  // Atualizar classe ativa no mapa
  document.querySelectorAll('.map-municipality').forEach(el => {
    el.classList.toggle('active', el.id === 'mun-' + code);
  });

  // Executar zoom suave no município selecionado
  zoomToMunicipality(code);
}

// Seleção de ano ativo na memória
function loadYearScores(year) {
  activeYear = String(year);
  scores = (activeYear === '2006') ? scores2006 : scores2017;
  rawData = (activeYear === '2006') ? rawData2006 : rawData2017;

  if (activeTrajectory !== 'historica') {
    recalculateAllScores();
  }

  refreshMetrics();
  if (geometry) {
    renderMap();
    if (current) choose(current);
  }
}

// Inicialização automática das séries oficiais 2006 e 2017 e da malha vetorial
async function autoLoadAll() {
  try {
    // 1. Carregar paralelamente os manifestos e CSVs oficiais homologados (2017 e 2006)
    const [rMan17, rScores17, rRaw17, rScores06, rRaw06] = await Promise.all([
      fetch('/results/RS_497_RESULTADOS.manifest.json'),
      fetch('/results/RS_497_RESULTADOS.csv'),
      fetch('/data/gerados/municipios_rs_2017_homologado.csv'),
      fetch('/results/RS_497_RESULTADOS_2006.csv'),
      fetch('/data/gerados/municipios_rs_2006_homologado.csv')
    ]);

    if (rMan17.ok) {
      manifest = await rMan17.json();
      if (manifest?.parametrizacao?.k_produtiva) {
        paramK = Number(manifest.parametrizacao.k_produtiva);
      }
    }

    if (rScores17.ok) scores2017 = parseScores(await rScores17.text());
    if (rScores06.ok) scores2006 = parseScores(await rScores06.text());
    if (rRaw17.ok) rawData2017 = parseRaw(await rRaw17.text());
    if (rRaw06.ok) rawData2006 = parseRaw(await rRaw06.text());

    // Associar os dados do ano ativo
    scores = (activeYear === '2006') ? scores2006 : scores2017;
    rawData = (activeYear === '2006') ? rawData2006 : rawData2017;
    recalculateAllScores();
    refreshMetrics();

    // 2. Carregar a malha GeoJSON oficial do IBGE 2022
    const rGeo = await fetch('/data/gerados/municipios_rs_2022.geojson');
    if (rGeo.ok) {
      const o = await rGeo.json();
      if (o.type === 'FeatureCollection' && Array.isArray(o.features)) {
        geometry = o;
        const placeholder = $('map-placeholder');
        if (placeholder) {
          placeholder.hidden = true;
          placeholder.classList.add('is-hidden');
          placeholder.style.display = 'none';
        }
        refreshMetrics();
        renderMap();
        if (current) choose(current);
        else choose(null);
      }
    }

    // 3. Carregar repositório de evidências epistêmicas (AdaptaBrasil + INMET)
    try {
      const [rEvid, rEps] = await Promise.all([
        fetch('/api/public/evidencias_rs.json'),
        fetch('/api/public/episodios_rs.json')
      ]);
      if (rEvid.ok) {
        evidenciasData = await rEvid.json();
      }
      if (rEps.ok) {
        episodiosData = await rEps.json();
      }
      if (layer === 'inmet' || layer === 'adaptabrasil') {
        renderMap();
      }
      if (current && activeArea === 'E') {
        updateComponentDetail(current);
      }
    } catch (eEvid) {
      console.warn('Evidências climáticas ou episódios offline:', eEvid);
    }
  } catch (err) {
    console.warn('Carregamento automático de dados offline ou em rede restrita:', err);
  }
}

// Busca rápida de municípios
const searchInput = $('search-input');
if (searchInput) {
  searchInput.addEventListener('input', ev => {
    const q = ev.target.value.trim().toLowerCase();
    if (!q) return;
    for (const [code, d] of scores) {
      if (d.municipio && d.municipio.toLowerCase().includes(q)) {
        choose(code, d.municipio);
        break;
      }
    }
  });
}

// Botão de restaurar enquadramento do estado (reset zoom)
const btnResetZoom = $('btn-reset-zoom');
if (btnResetZoom) {
  btnResetZoom.addEventListener('click', () => resetZoom());
}

// Alternância de camadas de tendência territorial (R por padrão, ou Evolução, E, P, S)
document.querySelectorAll('[data-layer]').forEach(b => {
  b.addEventListener('click', () => {
    layer = b.dataset.layer;
    document.querySelectorAll('[data-layer]').forEach(x => x.classList.toggle('selected', x === b));
    renderMap();
    if (current) {
      const activeEl = $('mun-' + current);
      if (activeEl) activeEl.classList.add('active');
    }
  });
});

// Abas do ambiente analítico municipal (Áreas D, T, M, A, B, C)
document.querySelectorAll('.comp-tab-btn').forEach(b => {
  b.addEventListener('click', () => {
    activeArea = b.dataset.area;
    document.querySelectorAll('.comp-tab-btn').forEach(x => x.classList.toggle('active', x === b));
    updateComponentDetail(current);
  });
});

// Controles da Bancada Epistêmica Triaxial (METIS-DIR-MULTI-002)
const selModel = $('select-model');
if (selModel) {
  selModel.addEventListener('change', ev => {
    activeModel = ev.target.value;
    updateTriaxialSummary();
    recalculateAllScores();
    renderMap();
    if (current) {
      updateComponentDetail(current);
      const activeEl = $('mun-' + current);
      if (activeEl) activeEl.classList.add('active');
    }
  });
}

const selYear = $('select-year');
if (selYear) {
  selYear.addEventListener('change', ev => {
    activeYear = ev.target.value;
    updateTriaxialSummary();
    loadYearScores(activeYear);
  });
}

const selTraj = $('select-trajectory');
if (selTraj) {
  selTraj.addEventListener('change', ev => {
    activeTrajectory = ev.target.value;
    updateTriaxialSummary();

    const hint = $('trajectory-hint');
    if (hint) {
      if (activeTrajectory === 'historica') {
        hint.textContent = '🔒 Série histórica auditada e imutável: parâmetros congelados no padrão homologado para reprodução científica.';
        hint.style.color = '#0284c7';
      } else {
        hint.textContent = '⚡ Modo experimental ativo: permite simular parâmetros k, pesos e testar hipóteses em tempo real.';
        hint.style.color = '';
      }
    }

    if (activeTrajectory === 'historica') {
      scores = (activeYear === '2006') ? new Map(scores2006) : new Map(scores2017);
    } else {
      recalculateAllScores();
    }

    renderMap();
    if (current) updateComponentDetail(current);
  });
}

// Executar carga inicial imediata dos dados oficiais
autoLoadAll();

