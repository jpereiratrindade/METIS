'use strict';

const $ = id => document.getElementById(id);

let scores = new Map();
let rawData = new Map();
let manifest = null;
let geometry = null;
let layer = 'resiliencia';
let current = null; // Nenhum município selecionado inicialmente
let activeCompTab = 'P'; // Iniciar com Produtiva (P) em foco
let geoBounds = new Map(); // código IBGE -> { x0, y0, width, height }
let zoomAnim = null;

// Paleta de cores idêntica à escala Morfo/SisTer (marinho -> teal -> sky -> verde)
const palette = ['#0c2844', '#087f8c', '#14805e', '#2ea8e8', '#7dd3fc'];

const fields = {
  resiliencia: ['resiliencia', 0, 100, 'Índice Composto R'],
  ecologica: ['ecologica_multiplicador', 0.5, 1.5, 'Multiplicador E'],
  produtiva: ['produtiva', 0, 50, 'Dimensão Produtiva P'],
  social: ['social', 0, 50, 'Dimensão Social S']
};

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
    for (const col of ['resiliencia', 'ecologica_multiplicador', 'produtiva', 'social', 'ecologica_indice']) {
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

function getValue(d) {
  let k = fields[layer][0];
  return d && d.status === 'experimental' && Number.isFinite(d[k]) ? d[k] : null;
}

function color(v) {
  if (v == null) return '#1e293b'; // sem dado / incompleto
  let [_, min, max] = fields[layer];
  let t = Math.max(0, Math.min(1, (v - min) / (max - min)));
  return palette[Math.min(4, Math.floor(t * 5))];
}

function fmt(v, d = 2) {
  return v == null || !Number.isFinite(v) ? 'Sem dado' : v.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: d });
}

function refreshMetrics() {
  let a = [...scores.values()];
  let valid = a.filter(x => x.status === 'experimental' && Number.isFinite(x.resiliencia));
  let mean = valid.length ? valid.reduce((s, x) => s + x.resiliencia, 0) / valid.length : null;

  if ($('metric-total')) $('metric-total').textContent = scores.size || '497';
  if ($('metric-valid')) $('metric-valid').textContent = valid.length || '492';
  if ($('metric-mean')) $('metric-mean').textContent = mean == null ? '44,3' : fmt(mean, 1);
  if ($('metric-year')) $('metric-year').textContent = '2017';

  if ($('source-state')) {
    $('source-state').textContent = `Resultados: ${scores.size} registros. Malha: ${geometry ? geometry.features.length + ' municípios' : 'carregando...'}. Operação local, sem envio externo de dados.`;
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

// Animação de viewBox do mapa SVG
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
    const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic

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
  if (legend) legend.replaceChildren();
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
  let match = 0;

  geoBounds.clear();

  for (const f of geometry.features) {
    const code = getCode(f.properties || {});
    const d = scores.get(code);
    const coords = coordinatesOf(f.geometry);
    const path = pathOf(f.geometry, project);
    if (!path) continue;

    // Calcular bounding box projetado para zoom suave
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
    el.setAttribute('fill', color(getValue(d)));
    el.setAttribute('class', 'map-municipality' + (current === code ? ' active' : ''));
    el.setAttribute('tabindex', '0');
    el.setAttribute('id', 'mun-' + code);

    const title = document.createElementNS(ns, 'title');
    const munName = getName(f.properties || {});
    const valText = d ? (d.status === 'dados_incompletos' ? 'dados incompletos' : fmt(getValue(d))) : 'sem dados';
    title.textContent = `${munName} (${code}) · ${fields[layer][3]}: ${valText}`;
    el.append(title);

    el.addEventListener('click', () => choose(code, munName));
    svg.appendChild(el);
    if (d) match++;
  }

  if (legend) {
    const tx = document.createElement('span');
    tx.textContent = `${fields[layer][3]}: ${fields[layer][1]} a ${fields[layer][2]} · (${match} municípios)`;
    legend.append(tx);

    const swGroup = document.createElement('div');
    swGroup.className = 'swatch-group';
    for (const c of palette) {
      let e = document.createElement('span');
      e.className = 'swatch';
      e.style.background = c;
      swGroup.append(e);
    }
    legend.append(swGroup);
  }
}

function updateComponentDetail(code) {
  const box = $('comp-detail-box');
  if (!box) return;

  if (!code) {
    box.innerHTML = '<p class="comp-empty-hint">Selecione um município no mapa para inspecionar as equações e os dados censitários abertos.</p>';
    return;
  }

  const d = scores.get(code);
  const raw = rawData.get(code);
  const q10 = manifest?.calibracao?.q10 ?? 7.272989;
  const q90 = manifest?.calibracao?.q90 ?? 8.932076;
  const q10Val = Math.expm1(q10);
  const q90Val = Math.expm1(q90);
  const modelId = manifest?.model_id || 'EPS-REF-001/0.1.0';

  if (activeCompTab === 'P') {
    const vp = raw?.valor_producao_reais;
    const area = raw?.area_estabelecimentos_ha;
    const prodHa = (vp != null && area != null && area > 0) ? (vp / area) : null;
    const pVal = d?.produtiva;

    let noteClass = 'comp-note-box';
    let noteText = '';
    if (pVal === 0) {
      noteClass += ' warning';
      noteText = `A pontuação zero (P = 0,00) resulta do corte pelo percentil inferior q10 (${fmt(q10Val, 2)} R$/ha) na distribuição de densidade monetária estadual. Não significa ausência de produção ou terra improdutiva, mas reflete sistemas com menor faturamento bruto por hectare (como pecuária pastoril extensiva).`;
    } else if (pVal >= 50) {
      noteText = `A pontuação atinge o teto calibrado do estado (P = 50,00), situando-se no percentil superior q90 (${fmt(q90Val, 2)} R$/ha) da produção por hectare.`;
    } else if (pVal != null) {
      noteText = `Pontuação normalizada linearmente entre os percentis q10 (${fmt(q10Val, 2)} R$/ha) e q90 (${fmt(q90Val, 2)} R$/ha) dos municípios do Rio Grande do Sul.`;
    } else {
      noteClass += ' warning';
      noteText = `Variáveis de valor da produção ou área não reportadas para este município no Censo 2017.`;
    }

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Dimensão Produtiva (P)</strong>
        <span class="score-tag">${pVal != null ? fmt(pVal, 2) + ' / 50' : 'Incompleto'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Valor da produção agropecuária</td><td class="val">${vp != null ? 'R$ ' + vp.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Área dos estabelecimentos</td><td class="val">${area != null ? area.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Produção monetária por hectare</td><td class="val">${prodHa != null ? 'R$ ' + fmt(prodHa, 2) + '/ha' : '—'}</td></tr>
        <tr><td>Limite inferior normalizado (q10)</td><td class="val">R$ ${fmt(q10Val, 2)}/ha</td></tr>
        <tr><td>Limite superior normalizado (q90)</td><td class="val">R$ ${fmt(q90Val, 2)}/ha</td></tr>
      </table>
      <div class="comp-formula-box">
        P = 50 × clamp((ln(1 + VP/área) - q10) / (q90 - q10), 0, 1)
      </div>
      <div class="${noteClass}">
        ${noteText}
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>IBGE/SIDRA · Censo Agro 2017 · Tabela 6898 · Modelo ${modelId}</span>
      </div>
    `;
  } else if (activeCompTab === 'E') {
    const pastagem = raw?.pastagem_natural_ha;
    const mata = raw?.mata_natural_ha;
    const area = raw?.area_estabelecimentos_ha;
    const natTot = (pastagem != null && mata != null) ? pastagem + mata : null;
    const natPerc = (natTot != null && area != null && area > 0) ? (natTot / area * 100) : null;
    const eVal = d?.ecologica_multiplicador;
    const isAmp = eVal != null && eVal >= 1.0;

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Multiplicador Ecológico (E)</strong>
        <span class="score-tag">${eVal != null ? fmt(eVal, 3) + '× (' + (isAmp ? 'Amplificador' : 'Atenuador') + ')' : 'Incompleto'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Pastagens naturais</td><td class="val">${pastagem != null ? pastagem.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Matas & florestas naturais</td><td class="val">${mata != null ? mata.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Vegetação natural combinada</td><td class="val">${natTot != null ? natTot.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Área dos estabelecimentos</td><td class="val">${area != null ? area.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Proporção de vegetação natural (e)</td><td class="val">${natPerc != null ? fmt(natPerc, 1) + '%' : '—'}</td></tr>
      </table>
      <div class="comp-formula-box">
        E = 0.5 + clamp((pastagem_natural + mata_natural) / área_total, 0, 1)
      </div>
      <div class="comp-note-box">
        Integra pastagens naturais e matas preservadas em estabelecimentos agropecuários. O ponto neutro é E = 1,0 (50% de cobertura natural). Valores &gt; 1,0 atuam como multiplicador amplificador sobre a base produtiva e social.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>IBGE/SIDRA · Censo Agro 2017 · Tabela 6881 · Malha IBGE 2022</span>
      </div>
    `;
  } else if (activeCompTab === 'S') {
    const nTot = raw?.estabelecimentos_total;
    const nAss = raw?.estabelecimentos_orientacao_tecnica;
    const nCoop = raw?.estabelecimentos_associados;
    const sVal = d?.social;
    const pAss = (nAss != null && nTot != null && nTot > 0) ? (nAss / nTot * 100) : null;
    const pCoop = (nCoop != null && nTot != null && nTot > 0) ? (nCoop / nTot * 100) : null;

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Dimensão Social (S)</strong>
        <span class="score-tag">${sVal != null ? fmt(sVal, 2) + ' / 50' : 'Incompleto'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Total de estabelecimentos</td><td class="val">${nTot != null ? nTot.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Com orientação técnica</td><td class="val">${nAss != null ? nAss.toLocaleString('pt-BR') + (pAss != null ? ' (' + fmt(pAss, 1) + '%)' : '') : '—'}</td></tr>
        <tr><td>Associados a cooperativas</td><td class="val">${nCoop != null ? nCoop.toLocaleString('pt-BR') + (pCoop != null ? ' (' + fmt(pCoop, 1) + '%)' : '') : '—'}</td></tr>
      </table>
      <div class="comp-formula-box">
        S = 25 × (assistência/total + associados/total)
      </div>
      <div class="comp-note-box">
        Avalia a capilaridade da assistência técnica agronômica e o engajamento cooperativo como medidas de articulação agroinstitucional e coesão dos produtores no território.
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>IBGE/SIDRA · Censo Agro 2017 · Tabelas 6780 e 6773</span>
      </div>
    `;
  } else if (activeCompTab === 'R') {
    const rVal = d?.resiliencia;
    const eVal = d?.ecologica_multiplicador;
    const pVal = d?.produtiva;
    const sVal = d?.social;
    const basePS = (pVal != null && sVal != null) ? pVal + sVal : null;

    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Síntese do Estado de Resiliência (R)</strong>
        <span class="score-tag">${rVal != null ? fmt(rVal, 2) : 'Incompleto'}</span>
      </div>
      <table class="comp-table">
        <tr><td>Base Produtiva + Social (P + S)</td><td class="val">${basePS != null ? fmt(basePS, 2) + ' / 100' : '—'}</td></tr>
        <tr><td>Multiplicador Ecológico (E)</td><td class="val">${eVal != null ? fmt(eVal, 3) + '×' : '—'}</td></tr>
        <tr><td>Estado de Resiliência Composto (R)</td><td class="val">${rVal != null ? fmt(rVal, 2) : '—'}</td></tr>
        <tr><td>Status de integridade amostral</td><td class="val">${d?.status || 'desconhecido'}</td></tr>
      </table>
      <div class="comp-formula-box">
        R = E × (P + S)
      </div>
      <div class="comp-note-box">
        O sistema opera em leitura relacional: a resiliência não decorre de variáveis isoladas, mas da capacidade de sustentação socioeconômica (P+S) atenuada ou amplificada pelas condições ecológicas (E).
      </div>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>Manifesto: results/RS_497_RESULTADOS.manifest.json</span>
      </div>
    `;
  } else if (activeCompTab === 'RAW') {
    box.innerHTML = `
      <div class="comp-title-bar">
        <strong>Insumos Censitários Originais</strong>
        <span class="score-tag">IBGE 2017</span>
      </div>
      <table class="comp-table">
        <tr><td>Área dos estabelecimentos</td><td class="val">${raw?.area_estabelecimentos_ha ? raw.area_estabelecimentos_ha.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Pastagens naturais</td><td class="val">${raw?.pastagem_natural_ha ? raw.pastagem_natural_ha.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Matas & florestas naturais</td><td class="val">${raw?.mata_natural_ha ? raw.mata_natural_ha.toLocaleString('pt-BR') + ' ha' : '—'}</td></tr>
        <tr><td>Valor total da produção</td><td class="val">${raw?.valor_producao_reais ? 'R$ ' + raw.valor_producao_reais.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Estabelecimentos agropecuários</td><td class="val">${raw?.estabelecimentos_total ? raw.estabelecimentos_total.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Com orientação técnica</td><td class="val">${raw?.estabelecimentos_orientacao_tecnica ? raw.estabelecimentos_orientacao_tecnica.toLocaleString('pt-BR') : '—'}</td></tr>
        <tr><td>Associados a cooperativa</td><td class="val">${raw?.estabelecimentos_associados ? raw.estabelecimentos_associados.toLocaleString('pt-BR') : '—'}</td></tr>
      </table>
      <div class="comp-provenance-box">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        <span>data/gerados/municipios_rs_2017_homologado.csv</span>
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
      statusAlert.innerHTML = '⚠️ <strong>Dados Incompletos no Censo 2017:</strong> Variáveis essenciais não foram reportadas pelo IBGE para este município (por sigilo amostral ou omissão na fonte). Por rigor científico, o MÉTIS não realiza imputação fictícia e mantém o registro auditável.';
    } else {
      statusAlert.style.display = 'none';
    }
  }

  if (d && d.status === 'experimental') {
    const r = d.resiliencia ?? 0;
    const e = d.ecologica_multiplicador ?? 1;
    const p = d.produtiva ?? 0;
    const s = d.social ?? 0;

    if ($('detail-r')) $('detail-r').textContent = fmt(r);
    if ($('detail-e')) $('detail-e').textContent = `${fmt(e, 3)}× (${e >= 1.0 ? 'Amplificador' : 'Atenuador'})`;
    if ($('detail-p')) $('detail-p').textContent = `${fmt(p, 1)} / 50`;
    if ($('detail-s')) $('detail-s').textContent = `${fmt(s, 1)} / 50`;

    if ($('bar-r')) $('bar-r').style.width = Math.min(100, (r / 100) * 100) + '%';
    if ($('bar-e')) $('bar-e').style.width = Math.min(100, Math.max(0, (e - 0.5) / 1.0 * 100)) + '%';
    if ($('bar-p')) $('bar-p').style.width = Math.min(100, (p / 50) * 100) + '%';
    if ($('bar-s')) $('bar-s').style.width = Math.min(100, (s / 50) * 100) + '%';
  } else {
    if ($('detail-r')) $('detail-r').textContent = 'Incompleto';
    if ($('detail-e')) $('detail-e').textContent = 'Sem dado';
    if ($('detail-p')) $('detail-p').textContent = 'Sem dado';
    if ($('detail-s')) $('detail-s').textContent = 'Sem dado';

    if ($('bar-r')) $('bar-r').style.width = '0%';
    if ($('bar-e')) $('bar-e').style.width = '0%';
    if ($('bar-p')) $('bar-p').style.width = '0%';
    if ($('bar-s')) $('bar-s').style.width = '0%';
  }

  // Atualizar detalhamento analítico do componente ativo
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
      if (rMan.ok) manifest = await rMan.json();
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

// Botões de camada
document.querySelectorAll('[data-layer]').forEach(b => {
  b.addEventListener('click', () => {
    layer = b.dataset.layer;
    document.querySelectorAll('[data-layer]').forEach(x => x.classList.toggle('selected', x === b));
    renderMap();
    choose(current, $('detail-name') ? $('detail-name').textContent : '');
  });
});

// Botão de restaurar enquadramento do estado (reset zoom)
const btnResetZoom = $('btn-reset-zoom');
if (btnResetZoom) {
  btnResetZoom.addEventListener('click', () => resetZoom());
}

// Abas de exploração dos componentes (P, E, S, R, RAW)
document.querySelectorAll('.comp-tab-btn').forEach(b => {
  b.addEventListener('click', () => {
    activeCompTab = b.dataset.comp;
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
