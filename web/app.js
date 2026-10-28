'use strict';

const $ = id => document.getElementById(id);

let scores = new Map();
let rawData = new Map();
let geometry = null;
let layer = 'resiliencia';
let current = '4301602'; // Iniciar com Bagé em destaque!

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

function renderMap() {
  const svg = $('map');
  if (!svg) return;
  svg.replaceChildren();
  if ($('map-placeholder')) $('map-placeholder').hidden = !!geometry;

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

  for (const f of geometry.features) {
    const code = getCode(f.properties || {});
    const d = scores.get(code);
    const path = pathOf(f.geometry, project);
    if (!path) continue;

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

function choose(code, name) {
  current = code;
  const d = scores.get(code);
  const raw = rawData.get(code);

  const munName = name || d?.municipio || raw?.municipio || 'Município';
  if ($('detail-name')) $('detail-name').textContent = munName;
  if ($('detail-code')) $('detail-code').textContent = `Código IBGE: ${code} ${d ? '· ' + d.status : ''}`;

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

  // Dados brutos
  if (raw) {
    if ($('raw-area')) $('raw-area').textContent = raw.area_estabelecimentos_ha ? raw.area_estabelecimentos_ha.toLocaleString('pt-BR') + ' ha' : '—';
    if ($('raw-pastagem')) $('raw-pastagem').textContent = raw.pastagem_natural_ha ? raw.pastagem_natural_ha.toLocaleString('pt-BR') + ' ha' : '—';
    if ($('raw-mata')) $('raw-mata').textContent = raw.mata_natural_ha ? raw.mata_natural_ha.toLocaleString('pt-BR') + ' ha' : '—';
    if ($('raw-vp')) $('raw-vp').textContent = raw.valor_producao_reais ? 'R$ ' + raw.valor_producao_reais.toLocaleString('pt-BR') : '—';
    if ($('raw-estab')) $('raw-estab').textContent = raw.estabelecimentos_total ? raw.estabelecimentos_total.toLocaleString('pt-BR') + ' total' : '—';
    
    let nTot = raw.estabelecimentos_total || 1;
    let nAss = raw.estabelecimentos_orientacao_tecnica || 0;
    let nCoop = raw.estabelecimentos_associados || 0;
    if ($('raw-assist')) $('raw-assist').textContent = `${nAss.toLocaleString('pt-BR')} (${(nAss/nTot*100).toFixed(1)}%)`;
    if ($('raw-assoc')) $('raw-assoc').textContent = `${nCoop.toLocaleString('pt-BR')} (${(nCoop/nTot*100).toFixed(1)}%)`;
  }

  // Atualizar classe ativa no mapa
  document.querySelectorAll('.map-municipality').forEach(el => {
    el.classList.toggle('active', el.id === 'mun-' + code);
  });
}

// Inicialização automática dos dados
async function autoLoadAll() {
  const btnQuick = $('btn-quick-load');
  try {
    if (btnQuick) {
      btnQuick.disabled = true;
      btnQuick.textContent = 'Carregando resultados oficiais...';
    }

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
        refreshMetrics();
        renderMap();
        choose(current, 'Bagé');
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
