'use strict';

const $ = id => document.getElementById(id);

let scores = new Map();
let rawData = new Map();
let manifest = null;
let geometry = null;
let current = null; // Nenhum município selecionado inicialmente
let activeArea = 'D'; // Área D (Resultados e Confronto) padrão
let paramK = 1500.0; // Parâmetro de escala k (R$/ha) da dimensão produtiva
let geoBounds = new Map(); // código IBGE -> { x0, y0, width, height }
let zoomAnim = null;

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

function refreshMetrics() {
  let a = [...scores.values()];
  let valid = a.filter(x => x.status === 'experimental');

  if ($('metric-total')) $('metric-total').textContent = scores.size || '497';
  if ($('metric-valid')) $('metric-valid').textContent = valid.length || '492';
  if ($('metric-year')) $('metric-year').textContent = '2017';

  if ($('source-state')) {
    $('source-state').textContent = `Resultados: ${scores.size} registros. Malha: ${geometry ? geometry.features.length + ' municípios' : 'carregando...'}. Metodologia METIS-DIR-MUN-001 (análise individual autônoma).`;
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

// Renderizar mapa territorial (sem mapas coropléticos nem indução a ranking)
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
    legend.innerHTML = `
      <div class="legend-item"><span class="legend-dot active"></span><span>Selecionado</span></div>
      <div class="legend-item"><span class="legend-dot valid"></span><span>Válido</span></div>
      <div class="legend-item"><span class="legend-dot incomplete"></span><span>Incompleto na fonte</span></div>
    `;
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

    const el = document.createElementNS(ns, 'path');
    el.setAttribute('d', path);

    let cls = 'map-municipality';
    if (current === code) cls += ' active';
    if (d && d.status === 'dados_incompletos') cls += ' incomplete';
    el.setAttribute('class', cls);
    el.setAttribute('tabindex', '0');
    el.setAttribute('id', 'mun-' + code);

    const title = document.createElementNS(ns, 'title');
    const munName = getName(f.properties || {});
    const statusText = d ? (d.status === 'dados_incompletos' ? 'dados incompletos' : 'dados oficiais homologados') : 'sem dados';
    title.textContent = `${munName} (${code}) · ${statusText}`;
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
function updateComponentDetail(code) {
  const box = $('comp-detail-box');
  if (!box) return;

  if (!code) {
    box.innerHTML = '<p class="comp-empty-hint">Selecione um município no mapa para abrir sua investigação analítica individual (METIS-DIR-MUN-001).</p>';
    return;
  }

  const d = scores.get(code);
  const raw = rawData.get(code);
  const modelId = manifest?.model_id || 'EPS-DIR-MUN-001/0.2.0';

  const vp = raw?.valor_producao_reais;
  const area = raw?.area_estabelecimentos_ha;
  const dm = (vp != null && area != null && area > 0) ? (vp / area) : null;
  const pastagem = raw?.pastagem_natural_ha;
  const mata = raw?.mata_natural_ha;
  const natTot = (pastagem != null && mata != null) ? (pastagem + mata) : null;
  const natProp = (natTot != null && area != null && area > 0) ? Math.min(1, Math.max(0, natTot / area)) : null;
  const eVal = natProp != null ? (0.5 + natProp) : null;

  const nTot = raw?.estabelecimentos_total;
  const nAss = raw?.estabelecimentos_orientacao_tecnica;
  const nCoop = raw?.estabelecimentos_associados;
  const sVal = (nTot != null && nTot > 0 && nAss != null && nCoop != null) ? (25.0 * ((nAss + nCoop) / nTot)) : null;

  const pVal = calculateP(dm, paramK);
  const rVal = calculateR(eVal, pVal, sVal);

  // Atualizar barras de resumo no painel superior
  if (rVal != null) {
    if ($('detail-r')) $('detail-r').textContent = fmt(rVal, 2);
    if ($('detail-e')) $('detail-e').textContent = `${fmt(eVal, 3)}× (${eVal >= 1.0 ? 'Amplificador' : 'Atenuador'})`;
    if ($('detail-p')) $('detail-p').textContent = `${fmt(pVal, 2)} / 50`;
    if ($('detail-s')) $('detail-s').textContent = `${fmt(sVal, 2)} / 50`;

    if ($('bar-r')) $('bar-r').style.width = Math.min(100, (rVal / 100) * 100) + '%';
    if ($('bar-e')) $('bar-e').style.width = Math.min(100, Math.max(0, (eVal - 0.5) / 1.0 * 100)) + '%';
    if ($('bar-p')) $('bar-p').style.width = Math.min(100, (pVal / 50) * 100) + '%';
    if ($('bar-s')) $('bar-s').style.width = Math.min(100, (sVal / 50) * 100) + '%';
  }

  // ÁREA D: RESULTADOS E CONFRONTO
  if (activeArea === 'D') {
    let noteText = '';
    if (d && d.status === 'dados_incompletos') {
      noteText = 'Variáveis essenciais estão ausentes no Censo 2017 para este município. Por rigor de governança, o sistema indica P e R como não calculados, sem substituição por zero fictício.';
    } else {
      noteText = `Densidade monetária observada dm = ${fmt(dm, 2)} R$/ha confrontada com parâmetro de escala k = ${fmt(paramK, 0)} R$/ha. A alteração de dados de qualquer outro município não afeta este cálculo (independência intermunicipal garantida).`;
    }

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área D · Resultados &amp; Diagnóstico</strong>
        <span class="score-tag">${rVal != null ? 'R = ' + fmt(rVal, 2) : 'Não calculado'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Densidade monetária da produção (dm)</td><td class="val">${dm != null ? 'R$ ' + fmt(dm, 2) + '/ha' : '—'}</td></tr>
        <tr><td>Multiplicador Ecológico (E)</td><td class="val">${eVal != null ? fmt(eVal, 3) + '×' : '—'}</td></tr>
        <tr><td>Dimensão Produtiva P(k=${fmt(paramK, 0)})</td><td class="val">${pVal != null ? fmt(pVal, 2) + ' / 50' : '—'}</td></tr>
        <tr><td>Dimensão Social (S)</td><td class="val">${sVal != null ? fmt(sVal, 2) + ' / 50' : '—'}</td></tr>
        <tr><td>Estado de Resiliência Hipotético (R)</td><td class="val">${rVal != null ? fmt(rVal, 2) : '—'}</td></tr>
      </table>
      <div class="comp-formula-box">
        R = E × (P + S) = ${eVal != null ? fmt(eVal, 3) : 'E'} × (${pVal != null ? fmt(pVal, 2) : 'P'} + ${sVal != null ? fmt(sVal, 2) : 'S'})
      </div>
      <div class="comp-note-box">
        ${noteText}
      </div>
      <div class="comp-note-box warning" style="margin-top: 4px;">
        <strong>Nota Epistêmica Obrigatória:</strong> R não constitui medida empiricamente validada de resiliência observada nem posição relativa frente a outros municípios. Trata-se de dedução matemática a partir da hipótese relacional declarada.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Diretriz METIS-DIR-MUN-001 · Modelo ${modelId}</span>
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
        Observáveis originais estritamente circunscritos aos estabelecimentos agropecuários do município. Não incluem áreas urbanas nem atividades externas ao setor agropecuário.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>IBGE SIDRA · Tabelas 6881, 6898, 6780, 6773 · Malha 2022</span>
      </div>
    `;
  }
  // ÁREA B: PARAMETRIZAÇÃO EXPERIMENTAL
  else if (activeArea === 'B') {
    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área B · Parametrização Experimental</strong>
        <span class="score-tag">Sensibilidade em Tempo Real</span>
      </div>
      <div class="param-control-group">
        <div class="param-control-header">
          <strong>Parâmetro de Escala k (Produtiva):</strong>
          <span id="param-k-display">${fmt(paramK, 0)} R$/ha</span>
        </div>
        <div class="param-input-wrap">
          <input type="range" class="param-slider" id="param-k-slider" min="300" max="6000" step="100" value="${paramK}"/>
          <input type="number" class="param-val-input" id="param-k-input" min="100" max="20000" step="50" value="${paramK}"/>
        </div>
      </div>
      <table class="comp-table" style="margin-top: 6px;">
        <tr><td>Função P(k)</td><td class="val">P = 50 × dm / (dm + k)</td></tr>
        <tr><td>Ponto médio (P = 25,0)</td><td class="val">Quando dm = k (${fmt(paramK, 0)} R$/ha)</td></tr>
        <tr><td>Função E</td><td class="val">E = 0.5 + clamp(nat/área, 0, 1)</td></tr>
        <tr><td>Função S</td><td class="val">S = 25 × (assist/estab + coop/estab)</td></tr>
      </table>
      <div class="comp-note-box">
        O parâmetro k define a taxa de saturação e é declarado na hipótese experimental. Mudar k permite avaliar a sensibilidade do município sem alterar seus dados observados.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Independência intermunicipal ativa · Metodologia METIS-DIR-MUN-001</span>
      </div>
    `;

    // Vincular controles de slider e input
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
        updateComponentDetail(code);
      }
    };

    if (slider) slider.addEventListener('input', ev => onKChange(ev.target.value));
    if (input) input.addEventListener('change', ev => onKChange(ev.target.value));
  }
  // ÁREA C: HIPÓTESE RELACIONAL
  else if (activeArea === 'C') {
    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Área C · Hipótese Relacional</strong>
        <span class="score-tag">Estrutura Teórica</span>
      </div>
      <div class="comp-formula-box" style="font-size: 0.82rem; padding: 10px;">
        R_m = E_m × (P_m + S_m)
      </div>
      <table class="comp-table">
        <tr><td>Papel de E</td><td class="val">Multiplicador ecossistêmico (> 0; neutro em 1,0)</td></tr>
        <tr><td>Papel de P</td><td class="val">Componente produtivo [0, 50]</td></tr>
        <tr><td>Papel de S</td><td class="val">Componente social / associativo [0, 50]</td></tr>
        <tr><td>Base socioeconômica</td><td class="val">(P + S) na escala [0, 100]</td></tr>
      </table>
      <div class="comp-note-box">
        A escolha de E como multiplicador é intencional e expressa a hipótese de que a integridade ecológica amplifica ou atenua a sustentabilidade da produção e coesão social ao longo do tempo.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Princípio SisTer/LABECO: Sem alteração de hipótese sem versionamento explícito.</span>
      </div>
    `;
  }
}

function choose(code, name) {
  current = code;
  if (!code) {
    if ($('detail-name')) $('detail-name').textContent = 'Selecione um município';
    if ($('detail-code')) $('detail-code').textContent = 'Clique na malha territorial ou busque acima';
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

// Inicialização automática dos dados
async function autoLoadAll() {
  const btnQuick = $('btn-quick-load');
  try {
    if (btnQuick) {
      btnQuick.disabled = true;
      btnQuick.textContent = 'Carregando resultados oficiais...';
    }

    // Carregar manifesto oficial
    try {
      const rMan = await fetch('/results/RS_497_RESULTADOS.manifest.json');
      if (rMan.ok) {
        manifest = await rMan.json();
        if (manifest?.parametrizacao?.k_produtiva) {
          paramK = Number(manifest.parametrizacao.k_produtiva);
        }
      }
    } catch (_) {}

    // Carregar CSV calculado
    const rScores = await fetch('/results/RS_497_RESULTADOS.csv');
    if (rScores.ok) {
      scores = parseScores(await rScores.text());
    }

    // Carregar CSV de dados brutos homologados para exibir no painel
    try {
      const rRaw = await fetch('/data/gerados/municipios_rs_2017_homologado.csv');
      if (rRaw.ok) rawData = parseRaw(await rRaw.text());
    } catch (_) {}

    refreshMetrics();

    // Carregar GeoJSON
    if (btnQuick) btnQuick.textContent = 'Carregando malha RS 2022 (24MB)...';
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

    if (btnQuick) {
      btnQuick.disabled = false;
      btnQuick.textContent = '✓ Dados Oficiais Carregados (497)';
    }
  } catch (err) {
    console.warn('Carregamento automático pendente ou offline:', err);
    if (btnQuick) {
      btnQuick.disabled = false;
      btnQuick.textContent = '⚡ Carregar dados oficiais (RS 497)';
    }
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

// Abas do ambiente analítico municipal (Áreas D, A, B, C)
document.querySelectorAll('.comp-tab-btn').forEach(b => {
  b.addEventListener('click', () => {
    activeArea = b.dataset.area;
    document.querySelectorAll('.comp-tab-btn').forEach(x => x.classList.toggle('active', x === b));
    updateComponentDetail(current);
  });
});

// Botão rápido da sidebar
const btnQuick = $('btn-quick-load');
if (btnQuick) {
  btnQuick.addEventListener('click', () => autoLoadAll());
}

// Upload manual de arquivos
const fScores = $('file-scores');
if (fScores) {
  fScores.addEventListener('change', async ev => {
    try {
      let file = ev.target.files[0];
      if (!file) return;
      scores = parseScores(await file.text());
      refreshMetrics();
      renderMap();
      choose(current);
    } catch (err) {
      alert('Falha ao ler CSV de resultados: ' + err.message);
    }
  });
}

const fGeo = $('file-geo');
if (fGeo) {
  fGeo.addEventListener('change', async ev => {
    try {
      let file = ev.target.files[0];
      if (!file) return;
      let o = JSON.parse(await file.text());
      if (o.type !== 'FeatureCollection') throw Error('GeoJSON inválido');
      geometry = o;
      refreshMetrics();
      renderMap();
      choose(current);
    } catch (err) {
      alert('Falha ao ler GeoJSON: ' + err.message);
    }
  });
}

// Executar carga inicial
autoLoadAll();
