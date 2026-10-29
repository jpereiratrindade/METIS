'use strict';

// Utilitários
const $ = id => document.getElementById(id);

let scores = new Map();
let rawData = new Map();
let currentCode = '4302105'; // Bento Gonçalves como padrão inicial representativo
let manifest = null;
let evidenciasData = null;
let episodiosData = null;

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Eixos Triaxiais
let activeModel = 'EPS-REF-001';
let activeYear = '2017';
let activeTrajectory = 'experimental';

// Parâmetros de calibração
let paramK = 1500.0;
let paramQ10 = 7.272989;
let paramQ90 = 8.932076;
let paramWe = 0.33;
let paramWp = 0.33;
let paramWs = 0.34;
let paramLambda = 0.50;
let paramEcoFactor = 1.00; // Modulação de estado ecológico (1.00 = 100% censitário)

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
    hypothesis: 'Componentes independentes combinados por soma ponderada linear, permitindo isolar a sensibilidade de cada dimensão.'
  },
  'EPS-EXP-003': {
    name: 'EPS-EXP-003 — Interativo (Acoplamento Não-Linear)',
    formula: 'R = E × (P + S) + λ·(P·S/50)',
    pFormula: 'P = 50 × dm / (dm + k)',
    hypothesis: 'Interações sinérgicas explícitas entre coesão social/cooperativa e capacidade produtiva sob modulação ecológica.'
  },
  'EPS-EXP-004': {
    name: 'EPS-EXP-004 — Autônomo Municipal (DIR-MUN-001)',
    formula: 'R = E × (P + S)',
    pFormula: 'P = 50 × dm / (dm + k)',
    hypothesis: 'Análise municipal autônoma com escala declarada k, estritamente invariante aos dados de outros municípios.'
  }
};

function fmt(v, d = 2) {
  return v == null || !Number.isFinite(v) ? '—' : v.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: d });
}

// Parser de CSV robusto
function csvRows(text) {
  let rows = [], row = [], cur = '', inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (inQ && text[i + 1] === '"') { cur += '"'; i++; }
      else { inQ = !inQ; }
    } else if (c === ',' && !inQ) {
      row.push(cur.trim()); cur = '';
    } else if ((c === '\r' || c === '\n') && !inQ) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cur.trim()); cur = '';
      if (row.some(x => x.length > 0)) rows.push(row);
      row = [];
    } else cur += c;
  }
  if (cur.length || row.length) { row.push(cur.trim()); rows.push(row); }
  return rows;
}

function parseScores(text) {
  let rows = csvRows(text.replace(/^\uFEFF/, ''));
  if (!rows.length) return new Map();
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

// Cálculo matemático formal de um modelo
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

  const e0_base = Math.max(0, Math.min(1, (past + mata) / area));
  const e0 = Math.max(0, Math.min(1, e0_base * paramEcoFactor));
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

// Renderização dos dados no dashboard
function renderDashboard() {
  const raw = rawData.get(currentCode);
  const munName = raw?.municipio || scores.get(currentCode)?.municipio || 'Município Desconhecido';

  // Atualizar cabeçalhos e pills
  if ($('pill-selected-mun')) $('pill-selected-mun').textContent = `${munName} (${currentCode})`;
  if ($('pill-active-model')) $('pill-active-model').textContent = activeModel;
  if ($('card-mun-title')) $('card-mun-title').textContent = `${munName} — ${activeModel}`;
  if ($('tag-active-model')) $('tag-active-model').textContent = activeModel;
  if ($('tag-calib-model')) $('tag-calib-model').textContent = activeModel;

  updateModelTabs();

  const res = computeSingleModel(raw, activeModel);

  if (!res || res.status === 'dados_incompletos') {
    if ($('dash-val-r')) $('dash-val-r').textContent = 'Incompleto';
    if ($('dash-val-e')) $('dash-val-e').textContent = '—';
    if ($('dash-val-p')) $('dash-val-p').textContent = '—';
    if ($('dash-val-s')) $('dash-val-s').textContent = '—';
    return;
  }

  // Preencher cartões de escore
  if ($('dash-val-r')) $('dash-val-r').textContent = fmt(res.resiliencia, 2);
  if ($('dash-val-e')) $('dash-val-e').textContent = fmt(res.ecologica_multiplicador, 2);
  if ($('dash-val-p')) $('dash-val-p').textContent = fmt(res.produtiva, 2);
  if ($('dash-val-s')) $('dash-val-s').textContent = fmt(res.social, 2);

  // Preencher barras proporcionais
  const maxR = activeModel === 'EPS-EXP-002' ? 100 : 120;
  const maxE = activeModel === 'EPS-EXP-002' ? 100 : 1.5;
  const maxP = activeModel === 'EPS-EXP-002' ? 100 : 50;
  const maxS = activeModel === 'EPS-EXP-002' ? 100 : 50;

  if ($('b-text-r')) $('b-text-r').textContent = fmt(res.resiliencia, 2);
  if ($('b-fill-r')) $('b-fill-r').style.width = Math.min(100, Math.max(0, (res.resiliencia / maxR) * 100)) + '%';

  if ($('b-text-e')) $('b-text-e').textContent = fmt(res.ecologica_multiplicador, 2);
  if ($('b-fill-e')) $('b-fill-e').style.width = Math.min(100, Math.max(0, (res.ecologica_multiplicador / maxE) * 100)) + '%';

  if ($('b-text-p')) $('b-text-p').textContent = fmt(res.produtiva, 2);
  if ($('b-fill-p')) $('b-fill-p').style.width = Math.min(100, Math.max(0, (res.produtiva / maxP) * 100)) + '%';

  if ($('b-text-s')) $('b-text-s').textContent = fmt(res.social, 2);
  if ($('b-fill-s')) $('b-fill-s').style.width = Math.min(100, Math.max(0, (res.social / maxS) * 100)) + '%';

  // Renderizar tabela de variáveis censitárias
  renderRawVariables(raw, res);

  // Renderizar confronto intramunicipal
  renderConfrontation(raw);

  // Renderizar evidências climáticas e alertas (AdaptaBrasil + INMET)
  renderEvidenceSection(currentCode);
}

function renderEvidenceSection(code) {
  const boxAdapta = $('dash-adapta-content');
  const boxInmet = $('dash-inmet-content');
  if (!boxAdapta || !boxInmet) return;

  const muniEvid = evidenciasData?.municipios?.[code];
  const adapta = muniEvid?.adaptabrasil || [];
  const avisos = muniEvid?.avisos_inmet || [];
  const eps = episodiosData?.por_municipio?.[code] || [];

  // 1. AdaptaBrasil
  if (adapta.length > 0) {
    const baselines = adapta.filter(x => x.cenario.startsWith('baseline'));
    const projecoes = adapta.filter(x => !x.cenario.startsWith('baseline'));

    const metersHtml = baselines.map(ind => {
      const valPct = Math.min(100, Math.max(0, (ind.valor || 0) * 100));
      return `
        <div style="margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; font-size: 0.73rem; color: #334155; margin-bottom: 2px;">
            <span>${escapeHtml(ind.nome)} (${ind.ano})</span>
            <strong style="color: ${ind.cor || 'var(--navy)'};">${fmt(ind.valor, 2)} · ${escapeHtml(ind.classe)}</strong>
          </div>
          <div style="height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
            <div style="height: 100%; width: ${valPct}%; background: ${ind.cor || '#10b981'}; border-radius: 3px;"></div>
          </div>
        </div>
      `;
    }).join('');

    let projHtml = '';
    if (projecoes.length > 0) {
      const projRows = projecoes.map(p => `
        <tr style="border-bottom: 1px solid #f1f5f9; font-size: 0.72rem;">
          <td style="padding: 4px 6px;">${escapeHtml(p.nome)}</td>
          <td style="padding: 4px 6px; text-align: center;"><strong>${p.ano}</strong></td>
          <td style="padding: 4px 6px; text-align: right;">${fmt(p.valor, 2)}</td>
          <td style="padding: 4px 6px; text-align: right; color: ${p.cor || 'var(--navy)'}; font-weight: 700;">${escapeHtml(p.classe)}</td>
        </tr>
      `).join('');

      projHtml = `
        <div style="margin-top: 10px;">
          <small style="font-size: 0.70rem; font-weight: 750; color: #475569; text-transform: uppercase;">Projeções Futuras IPCC AR5 (Cenário RCP4.5):</small>
          <table style="width: 100%; border-collapse: collapse; margin-top: 4px;">
            <thead>
              <tr style="border-bottom: 1px solid #e2e8f0; font-size: 0.68rem; color: #64748b;">
                <th style="text-align: left; padding: 4px 6px;">Indicador</th>
                <th style="text-align: center; padding: 4px 6px;">Ano</th>
                <th style="text-align: right; padding: 4px 6px;">Índice</th>
                <th style="text-align: right; padding: 4px 6px;">Classe</th>
              </tr>
            </thead>
            <tbody>${projRows}</tbody>
          </table>
        </div>
      `;
    }

    boxAdapta.innerHTML = metersHtml + projHtml;
  } else {
    boxAdapta.innerHTML = `<p style="font-size: 0.75rem; color: #64748b;">Carregando ou sem dados do AdaptaBrasil para este município.</p>`;
  }

  // 2. INMET & Episódios
  let inmetHtml = '';
  if (eps.length > 0) {
    inmetHtml += eps.map(ep => `
      <div style="background: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid #6366f1; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; font-size: 0.72rem; line-height: 1.4;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
          <span style="background: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; padding: 1px 6px; border-radius: 4px; font-size: 0.66rem; font-weight: 750;">🔬 ${escapeHtml(ep.estado_episodio.toUpperCase())}</span>
          <span style="font-size: 0.66rem; color: #64748b; font-family: monospace;">${escapeHtml(ep.id)}</span>
        </div>
        <strong style="color: var(--navy); display: block;">Ameaça: ${escapeHtml(ep.tipo_ameaca)} (${escapeHtml(ep.severidade)})</strong>
        <div style="font-size: 0.68rem; color: #64748b; margin-top: 2px;">
          Vigência: ${ep.janela_inicio ? ep.janela_inicio.substring(0, 16).replace('T', ' ') : '—'} até ${ep.janela_fim ? ep.janela_fim.substring(0, 16).replace('T', ' ') : '—'}
        </div>
        <div style="margin-top: 4px; padding: 4px 6px; background: #f8fafc; border-radius: 4px; border: 1px solid #f1f5f9; font-size: 0.69rem;">
          Estado Basal Congelado: <strong>R = ${fmt(ep.estado_metis_congelado?.resiliencia, 2)}</strong> | Status: <em>${escapeHtml(ep.desfecho_cientifico)}</em>
        </div>
      </div>
    `).join('');
  }

  if (avisos.length > 0) {
    inmetHtml += avisos.map(a => `
      <div style="background: #ffffff; border: 1px solid #fed7aa; border-left: 4px solid #f97316; border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; font-size: 0.72rem; line-height: 1.4;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
          <span style="background: ${a.cor || '#f97316'}; color: #fff; padding: 1px 6px; border-radius: 4px; font-size: 0.66rem; font-weight: 750;">⚠️ ${escapeHtml(a.severidade)}</span>
          <span style="font-size: 0.66rem; color: #64748b;">INMET Operacional (${escapeHtml(a.estado_vigencia || 'vigente')})</span>
        </div>
        <strong style="color: #0f172a; display: block;">${escapeHtml(a.descricao)}</strong>
        <div style="font-size: 0.68rem; color: #64748b;">${escapeHtml(a.inicio.substring(0, 16).replace('T', ' '))} até ${escapeHtml(a.fim.substring(0, 16).replace('T', ' '))}</div>
      </div>
    `).join('');
  } else if (eps.length === 0) {
    inmetHtml = `
      <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 3px solid #22c55e; color: #15803d; padding: 8px 10px; border-radius: 6px; font-size: 0.72rem; line-height: 1.4;">
        <strong>Sem avisos meteorológicos vigentes emitidos pelo INMET</strong>
        <p style="margin: 2px 0 0; font-size: 0.67rem; opacity: 0.85;">A ausência de alerta meteorológico oficial não comprova ausência de perturbação no território nem garante resiliência.</p>
      </div>
    `;
  }

  boxInmet.innerHTML = inmetHtml;
}

function renderRawVariables(raw, res) {
  const tbody = $('dash-raw-tbody');
  if (!tbody || !raw) return;

  const area = raw.area_estabelecimentos_ha;
  const vp = raw.valor_producao_reais;
  const past = raw.pastagem_natural_ha;
  const mata = raw.mata_natural_ha;
  const estab = raw.estabelecimentos_total;
  const orient = raw.estabelecimentos_orientacao_tecnica;
  const assoc = raw.estabelecimentos_associados;

  const dm = area > 0 && vp != null ? vp / area : null;
  const vegTot = (past || 0) + (mata || 0);
  const vegPct = area > 0 ? (vegTot / area) * 100 : null;

  tbody.innerHTML = `
    <tr>
      <td><strong>Área dos Estabelecimentos</strong></td>
      <td><code>A</code></td>
      <td style="text-align: right; font-weight: 700;">${area ? area.toLocaleString('pt-BR') + ' ha' : '—'}</td>
      <td style="color: #64748b;">Denominador de escala espacial dos estabelecimentos</td>
    </tr>
    <tr>
      <td><strong>Valor da Produção Agropecuária</strong></td>
      <td><code>VP</code></td>
      <td style="text-align: right; font-weight: 700;">${vp ? 'R$ ' + vp.toLocaleString('pt-BR') : '—'}</td>
      <td style="color: #64748b;">Receita bruta total declarada no Censo Agro 2017</td>
    </tr>
    <tr>
      <td><strong>Densidade Econômica da Produção</strong></td>
      <td><code>d_m = VP / A</code></td>
      <td style="text-align: right; font-weight: 700; color: var(--teal);">${dm ? 'R$ ' + fmt(dm, 2) + '/ha' : '—'}</td>
      <td style="color: #64748b;">Intensidade monetária por hectare (insumo de P)</td>
    </tr>
    <tr>
      <td><strong>Vegetação Natural (Pastagens + Matas)</strong></td>
      <td><code>pastagem + mata</code></td>
      <td style="text-align: right; font-weight: 700;">${vegTot ? vegTot.toLocaleString('pt-BR') + ' ha (' + fmt(vegPct, 1) + '%)' : '—'}</td>
      <td style="color: #64748b;">Conservação de ecossistemas nativos (insumo de E)</td>
    </tr>
    <tr>
      <td><strong>Total de Estabelecimentos</strong></td>
      <td><code>N_estab</code></td>
      <td style="text-align: right; font-weight: 700;">${estab ? estab.toLocaleString('pt-BR') : '—'}</td>
      <td style="color: #64748b;">Total de unidades produtivas agropecuárias</td>
    </tr>
    <tr>
      <td><strong>Estabelecimentos com Assistência Técnica</strong></td>
      <td><code>N_assist</code></td>
      <td style="text-align: right; font-weight: 700;">${orient ? orient.toLocaleString('pt-BR') : '—'}</td>
      <td style="color: #64748b;">Acesso a difusão de tecnologia e capacitação</td>
    </tr>
    <tr>
      <td><strong>Estabelecimentos em Cooperativas</strong></td>
      <td><code>N_coop</code></td>
      <td style="text-align: right; font-weight: 700;">${assoc ? assoc.toLocaleString('pt-BR') : '—'}</td>
      <td style="color: #64748b;">Articulação comunitária e comercial (insumo de S)</td>
    </tr>
  `;
}

function renderConfrontation(raw) {
  const tbody = $('dash-confront-tbody');
  if (!tbody || !raw) return;

  const models = ['EPS-REF-001', 'EPS-EXP-002', 'EPS-EXP-003', 'EPS-EXP-004'];
  const refRes = computeSingleModel(raw, 'EPS-REF-001');
  const refR = refRes?.resiliencia;

  let html = '';
  for (const mId of models) {
    const res = computeSingleModel(raw, mId);
    const rVal = res?.resiliencia;
    let diffHtml = '—';
    if (rVal != null && refR != null && mId !== 'EPS-REF-001') {
      const diff = rVal - refR;
      const sign = diff > 0 ? '+' : '';
      const cls = diff > 0.05 ? 'pos' : (diff < -0.05 ? 'neg' : 'zero');
      diffHtml = `<span class="confrontation-diff ${cls}">${sign}${fmt(diff, 2)}</span>`;
    } else if (mId === 'EPS-REF-001') {
      diffHtml = '<span class="confrontation-diff zero">Base</span>';
    }

    const isActive = mId === activeModel;
    html += `
      <tr class="${isActive ? 'active-model-row' : ''}" data-model="${mId}" title="Clique para investigar este modelo no painel principal">
        <td>
          <span class="confrontation-model-tag">${mId}</span>
          <span class="confrontation-sub">${modelCatalog[mId].name.split('—')[1] || ''}</span>
        </td>
        <td style="text-align: center;">${fmt(res?.ecologica_multiplicador, 2)}</td>
        <td style="text-align: center;">${fmt(res?.produtiva, 2)}</td>
        <td style="text-align: center;">${fmt(res?.social, 2)}</td>
        <td style="text-align: center; font-weight: 800; color: var(--navy);">${fmt(rVal, 2)}</td>
        <td style="text-align: center;">${diffHtml}</td>
      </tr>
    `;
  }

  tbody.innerHTML = html;

  // Tornar linhas da tabela clicáveis para alternar o modelo ativo
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => {
      const mId = tr.dataset.model;
      if (mId && modelCatalog[mId]) {
        setActiveModelWithAlert(mId, `Modelo alterado para ${mId} via matriz de confronto.`);
      }
    });
  });
}

// Exportações científicas reproduzíveis
function exportJSON() {
  const raw = rawData.get(currentCode);
  const munName = raw?.municipio || 'Municipio';
  const res = computeSingleModel(raw, activeModel);

  const payload = {
    metis_version: '0.1.0',
    timestamp: new Date().toISOString(),
    diretriz: 'METIS-OPEN-001',
    ecossistema: 'SisTer',
    municipio: {
      codigo_ibge: currentCode,
      nome: munName,
      censo_ano: activeYear
    },
    bancada_epistemica: {
      modelo_ativo: activeModel,
      ano: activeYear,
      trajetoria: activeTrajectory,
      parametros: {
        k_produtiva_reais_ha: paramK,
        pesos_aditivos: { we: paramWe, wp: paramWp, ws: paramWs },
        sinergia_lambda: paramLambda,
        fator_estado_ecologico: paramEcoFactor,
        q10_ref: paramQ10,
        q90_ref: paramQ90
      }
    },
    dados_censitarios_originais: raw,
    escores_calculados: res,
    confronto_modelos: {
      'EPS-REF-001': computeSingleModel(raw, 'EPS-REF-001'),
      'EPS-EXP-002': computeSingleModel(raw, 'EPS-EXP-002'),
      'EPS-EXP-003': computeSingleModel(raw, 'EPS-EXP-003'),
      'EPS-EXP-004': computeSingleModel(raw, 'EPS-EXP-004')
    },
    postura_epistemica: 'O indicador R e uma deducao formal para investigacao cientifica e confronto de hipoteses, sem ranqueamento territorial.'
  };

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `METIS_manifesto_${currentCode}_${activeModel}_${activeYear}.json`;
  a.click();
}

function exportCSV() {
  const raw = rawData.get(currentCode);
  const munName = raw?.municipio || 'Municipio';
  const models = ['EPS-REF-001', 'EPS-EXP-002', 'EPS-EXP-003', 'EPS-EXP-004'];

  let csv = 'codigo_ibge,municipio,ano,modelo,ecologica_multiplicador,produtiva,social,resiliencia,param_k\n';
  for (const mId of models) {
    const r = computeSingleModel(raw, mId);
    csv += `${currentCode},"${munName}",${activeYear},${mId},${r?.ecologica_multiplicador ?? ''},${r?.produtiva ?? ''},${r?.social ?? ''},${r?.resiliencia ?? ''},${paramK}\n`;
  }

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `METIS_confronto_${currentCode}.csv`;
  a.click();
}

// Popular dropdown de municípios
function populateMunicipioDropdown() {
  const selMun = $('select-municipio');
  if (selMun && rawData.size > 0) {
    selMun.innerHTML = '';
    const list = [...rawData.entries()].map(([code, d]) => ({
      code,
      nome: d.municipio || scores.get(code)?.municipio || code
    })).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));

    for (const item of list) {
      const opt = document.createElement('option');
      opt.value = item.code;
      opt.textContent = `${item.nome} (${item.code})`;
      if (item.code === currentCode) opt.selected = true;
      selMun.appendChild(opt);
    }
  }
}

// Carregar dados de ano específico para o Dashboard
async function loadDashboardYear(year) {
  const scoresUrl = year === '2006' 
    ? '/results/RS_497_RESULTADOS_2006.csv'
    : '/results/RS_497_RESULTADOS.csv';
  const rawUrl = year === '2006'
    ? '/data/gerados/municipios_rs_2006_homologado.csv'
    : '/data/gerados/municipios_rs_2017_homologado.csv';

  try {
    const [rScores, rRaw] = await Promise.all([
      fetch(scoresUrl),
      fetch(rawUrl)
    ]);

    if (rScores.ok) scores = parseScores(await rScores.text());
    if (rRaw.ok) rawData = parseRaw(await rRaw.text());

    populateMunicipioDropdown();
    renderDashboard();
  } catch (err) {
    console.error('Erro ao carregar dados do ano no dashboard:', err);
  }
}

// Inicialização
async function initDashboard() {
  try {
    // 1. Carregar CSVs e APIs de evidências paralelamente
    const [rYear, rEvid, rEps] = await Promise.all([
      loadDashboardYear(activeYear),
      fetch('/api/public/evidencias_rs.json').catch(() => null),
      fetch('/api/public/episodios_rs.json').catch(() => null)
    ]);

    if (rEvid && rEvid.ok) {
      evidenciasData = await rEvid.json();
    }
    if (rEps && rEps.ok) {
      episodiosData = await rEps.json();
    }

    renderEvidenceSection(currentCode);

    // 2. Event listener do dropdown de municípios
    const selMun = $('select-municipio');
    if (selMun) {
      selMun.addEventListener('change', e => {
        if (e.target.value) {
          currentCode = e.target.value;
          renderDashboard();
        }
      });
    }

    // 3. Busca de municípios pelo input da topbar
    const searchInput = $('dash-search-input');
    if (searchInput) {
      searchInput.addEventListener('input', e => {
        const q = e.target.value.trim().toLowerCase();
        if (!q) return;
        for (const [code, d] of rawData) {
          const nome = (d.municipio || '').toLowerCase();
          if (nome.includes(q) || code.includes(q)) {
            currentCode = code;
            if (selMun) selMun.value = code;
            renderDashboard();
            break;
          }
        }
      });
    }

    // 4. Botões de atalho rápido
    document.querySelectorAll('.dash-quick-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const code = btn.dataset.code;
        if (code && rawData.has(code)) {
          currentCode = code;
          if (selMun) selMun.value = code;
          renderDashboard();
        }
      });
    });

    // 5. Controles da Bancada Triaxial
    $('dash-select-model')?.addEventListener('change', e => {
      activeModel = e.target.value;
      if ($('dash-model-hint')) $('dash-model-hint').textContent = modelCatalog[activeModel]?.hypothesis || '';
      updateModelTabs();
      updateTriaxialBadge();
      renderDashboard();
    });

    $('dash-select-year')?.addEventListener('change', async e => {
      activeYear = e.target.value;
      updateTriaxialBadge();
      await loadDashboardYear(activeYear);
    });

    $('dash-select-trajectory')?.addEventListener('change', e => {
      activeTrajectory = e.target.value;
      updateTriaxialBadge();
      renderDashboard();
    });

    // 6. Tabs de sincronização direta no card de calibração
    document.querySelectorAll('.calib-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetModel = btn.dataset.model;
        if (targetModel && modelCatalog[targetModel]) {
          activeModel = targetModel;
          updateModelTabs();
          updateTriaxialBadge();
          renderDashboard();
        }
      });
    });

    // 7. Modulação do Estado Ecológico (Transversal a todos os modelos)
    $('slider-eco')?.addEventListener('input', e => {
      paramEcoFactor = Number(e.target.value);
      const pct = Math.round(paramEcoFactor * 100);
      if ($('lbl-param-eco')) {
        $('lbl-param-eco').textContent = paramEcoFactor === 1.0 ? '1,00× (Censitário 100%)' : `${fmt(paramEcoFactor, 2)}× (${pct}%)`;
      }
      renderDashboard();
    });

    // 8. Escala Hill k (Produtividade)
    const onKChange = val => {
      const num = Number(val);
      if (num > 0 && Number.isFinite(num)) {
        paramK = num;
        if ($('slider-k')) $('slider-k').value = String(num);
        if ($('input-k')) $('input-k').value = String(num);
        if ($('lbl-param-k')) $('lbl-param-k').textContent = `${Math.round(paramK)} R$/ha`;
        if (activeModel === 'EPS-REF-001') {
          setActiveModelWithAlert('EPS-EXP-004', 'Modelo EPS-EXP-004 ativado para aplicar o parâmetro de escala Hill (k).');
        } else {
          renderDashboard();
        }
      }
    };
    $('slider-k')?.addEventListener('input', e => onKChange(e.target.value));
    $('input-k')?.addEventListener('input', e => onKChange(e.target.value));

    // 9. Pesos Aditivos (Modelo EPS-EXP-002)
    $('slider-we')?.addEventListener('input', e => {
      paramWe = Number(e.target.value);
      paramWs = Math.max(0.05, 1.0 - paramWe - paramWp);
      if ($('lbl-param-we')) $('lbl-param-we').textContent = fmt(paramWe, 2);
      if ($('lbl-param-ws')) $('lbl-param-ws').textContent = fmt(paramWs, 2);
      if (activeModel !== 'EPS-EXP-002') {
        setActiveModelWithAlert('EPS-EXP-002', 'Modelo EPS-EXP-002 ativado automaticamente para aplicar os pesos aditivos (we, wp, ws).');
      } else {
        renderDashboard();
      }
    });

    $('slider-wp')?.addEventListener('input', e => {
      paramWp = Number(e.target.value);
      paramWs = Math.max(0.05, 1.0 - paramWe - paramWp);
      if ($('lbl-param-wp')) $('lbl-param-wp').textContent = fmt(paramWp, 2);
      if ($('lbl-param-ws')) $('lbl-param-ws').textContent = fmt(paramWs, 2);
      if (activeModel !== 'EPS-EXP-002') {
        setActiveModelWithAlert('EPS-EXP-002', 'Modelo EPS-EXP-002 ativado automaticamente para aplicar os pesos aditivos (we, wp, ws).');
      } else {
        renderDashboard();
      }
    });

    // 10. Intensidade de Sinergia (Modelo EPS-EXP-003)
    $('slider-lambda')?.addEventListener('input', e => {
      paramLambda = Number(e.target.value);
      if ($('lbl-param-lambda')) $('lbl-param-lambda').textContent = fmt(paramLambda, 2);
      if (activeModel !== 'EPS-EXP-003') {
        setActiveModelWithAlert('EPS-EXP-003', 'Modelo EPS-EXP-003 ativado automaticamente para aplicar a intensidade de sinergia (λ).');
      } else {
        renderDashboard();
      }
    });

    // 11. Botão de restauração de padrões
    $('btn-reset-calib')?.addEventListener('click', () => {
      paramK = 1500.0;
      paramEcoFactor = 1.00;
      paramWe = 0.33;
      paramWp = 0.33;
      paramWs = 0.34;
      paramLambda = 0.50;

      if ($('slider-eco')) $('slider-eco').value = '1.00';
      if ($('lbl-param-eco')) $('lbl-param-eco').textContent = '1,00× (Censitário 100%)';
      if ($('slider-k')) $('slider-k').value = '1500';
      if ($('input-k')) $('input-k').value = '1500';
      if ($('lbl-param-k')) $('lbl-param-k').textContent = '1500 R$/ha';
      if ($('slider-we')) $('slider-we').value = '0.33';
      if ($('lbl-param-we')) $('lbl-param-we').textContent = '0,33';
      if ($('slider-wp')) $('slider-wp').value = '0.33';
      if ($('lbl-param-wp')) $('lbl-param-wp').textContent = '0,33';
      if ($('lbl-param-ws')) $('lbl-param-ws').textContent = '0,34';
      if ($('slider-lambda')) $('slider-lambda').value = '0.50';
      if ($('lbl-param-lambda')) $('lbl-param-lambda').textContent = '0,50';

      showCalibAlert('Parâmetros restaurados aos padrões originais do laboratório.');
      renderDashboard();
    });

    // 12. Botões de exportação
    $('btn-export-json')?.addEventListener('click', exportJSON);
    $('btn-export-csv')?.addEventListener('click', exportCSV);

    // 13. Renderização inicial
    updateModelTabs();
    updateTriaxialBadge();
    renderDashboard();

  } catch (err) {
    console.error('Erro na inicialização do dashboard analítico:', err);
  }
}

function updateModelTabs() {
  document.querySelectorAll('.calib-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.model === activeModel);
  });
  if ($('dash-select-model') && $('dash-select-model').value !== activeModel) {
    $('dash-select-model').value = activeModel;
  }
  if ($('dash-model-hint')) {
    $('dash-model-hint').textContent = modelCatalog[activeModel]?.hypothesis || '';
  }
  if ($('tag-calib-model')) {
    $('tag-calib-model').textContent = activeModel;
  }
}

function showCalibAlert(msg) {
  const banner = $('calib-alert-banner');
  if (!banner) return;
  banner.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg> <span>${msg}</span>`;
  banner.style.display = 'flex';
  clearTimeout(banner._timer);
  banner._timer = setTimeout(() => {
    banner.style.display = 'none';
  }, 4000);
}

function setActiveModelWithAlert(newModel, reason) {
  if (activeModel !== newModel) {
    activeModel = newModel;
    updateModelTabs();
    updateTriaxialBadge();
    if (reason) showCalibAlert(reason);
  }
  renderDashboard();
}

function updateTriaxialBadge() {
  const modelName = modelCatalog[activeModel]?.name.split('—')[0].trim() || activeModel;
  const trajText = activeTrajectory === 'experimental' ? 'Trajetória Experimental' : 'Trajetória Histórica';
  if ($('badge-dash-config')) {
    $('badge-dash-config').textContent = `${modelName} · ${activeYear} · ${trajText}`;
  }
}

document.addEventListener('DOMContentLoaded', initDashboard);
