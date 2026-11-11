const fmtInt = new Intl.NumberFormat('pt-BR');
const fmtCompact = new Intl.NumberFormat('pt-BR',{notation:'compact',maximumFractionDigits:1});
let rawPayload = null;
let report = null;
let selectedProposal = 0;
let activeMethod = 'gerais';
let activeWeekId = null;
let proposalSearchQuery = '';
let forceProposalIdx = null;

function esc(value='') { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function formatNumber(value,compact=false) { return value == null ? '—' : (compact ? fmtCompact.format(value) : fmtInt.format(value)); }
function percentage(value) { return `${Number(value).toLocaleString('pt-BR',{maximumFractionDigits:1})}%`; }
function showToast(message) { const node=document.getElementById('toast'); node.textContent=message; node.classList.add('show'); clearTimeout(showToast.timer); showToast.timer=setTimeout(()=>node.classList.remove('show'),2800); }

const normText = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

async function fetchDashboardData() {
  const resp = await fetch(`dados/dados_dashboard.json?t=${Date.now()}`, { cache: 'no-store' });
  if (!resp.ok) throw new Error('Não foi possível carregar os dados do painel.');
  return resp.json();
}

async function loadReport() {
  try {
    rawPayload = await fetchDashboardData();
    weekOptions = weekOptionsFromPayload();
    const wanted = new URLSearchParams(location.search).get('semana');
    const fallback = isMultiWeek() ? String(rawPayload.semana_padrao) : 'padrao';
    activeWeekId = weekOptions.some(o => o.id === wanted) ? wanted : fallback;
    initSlicer();
    initProposalSearch();
    initAnnualToggle();
    renderCurrentWeek();
    syncUrl();
  } catch (error) {
    showToast(error.message);
  }
}

/* ===== Busca de Texto Global ===== */
function initProposalSearch() {
  const wrapper = document.getElementById('proposta-busca-wrapper');
  const input = document.getElementById('busca-proposta-global');
  const clearBtn = document.getElementById('limpar-busca-proposta');
  const list = document.getElementById('lista-sugestoes-proposta');
  if (!wrapper || !input) return;

  input.addEventListener('focus', () => {
    renderProposalSuggestions(input.value);
    wrapper.classList.add('aberto');
  });

  input.addEventListener('input', () => {
    proposalSearchQuery = input.value;
    clearBtn.classList.toggle('visivel', Boolean(proposalSearchQuery.trim()));
    renderProposalSuggestions(proposalSearchQuery);
    wrapper.classList.add('aberto');
    renderCards();
  });

  clearBtn.addEventListener('click', () => {
    input.value = '';
    proposalSearchQuery = '';
    clearBtn.classList.remove('visivel');
    renderProposalSuggestions('');
    renderCards();
    input.focus();
  });

  list.addEventListener('click', e => {
    const item = e.target.closest('.proposta-sugestao-item');
    if (!item) return;
    
    const idx = Number(item.dataset.index);
    const weekId = item.dataset.week;
    
    input.value = '';
    proposalSearchQuery = '';
    clearBtn.classList.remove('visivel');
    wrapper.classList.remove('aberto');
    
    if (activeWeekId !== weekId) {
      activeWeekId = weekId;
      forceProposalIdx = idx;
      renderCurrentWeek();
      syncUrl();
    } else {
      forceProposalIdx = idx;
      renderCurrentWeek();
    }
    
    navigateToPage('propostas');
  });

  document.addEventListener('pointerdown', e => {
    if (!wrapper.contains(e.target)) wrapper.classList.remove('aberto');
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') wrapper.classList.remove('aberto');
  });
}

function renderProposalSuggestions(query = '') {
  const list = document.getElementById('lista-sugestoes-proposta');
  if (!list || !rawPayload || !rawPayload.dados_semanas) return;
  
  const q = normText(query).trim();
  const allProposals = [];
  
  Object.entries(rawPayload.dados_semanas).sort((a, b) => Number(b[0]) - Number(a[0])).forEach(([weekId, weekData]) => {
    if(weekData.proposals) {
       weekData.proposals.forEach((p, index) => {
         allProposals.push({ 
           p, 
           index, 
           weekId, 
           weekLabel: weekData.edition || `${weekId}ª semana`,
           weekPeriod: weekData.period || ''
         });
       });
    }
  });

  const matches = allProposals.filter(({ p, weekLabel, weekPeriod }) =>
    !q || normText(`${p.id} ${p.description} ${p.status || ''} ${weekLabel} ${weekPeriod}`).includes(q)
  );

  if (!matches.length) {
    list.innerHTML = '<li class="proposta-sugestao-vazio">Nenhuma proposta encontrada</li>';
    return;
  }

  list.innerHTML = matches.slice(0, 50).map(({ p, index, weekId, weekLabel }) => `
    <li class="proposta-sugestao-item" role="option" data-index="${index}" data-week="${weekId}">
      <div class="proposta-sugestao-info">
        <b>${esc(p.id)}</b>
        <small>${esc(p.description || '')}</small>
        <small class="week-badge">${esc(weekLabel)}</small>
      </div>
    </li>
  `).join('');
}

let weekOptions = [];
let slicerItems = [];
let slicerActive = 0;
let lastPointer = { x: -1, y: -1 };

function isMultiWeek() { return !!(rawPayload && rawPayload.dados_semanas && rawPayload.opcoes_semanas); }
function getWeekReport(id) { return isMultiWeek() ? rawPayload.dados_semanas[id] : rawPayload; }

function weekOptionsFromPayload() {
  const lastLabel = r => { const h = r?.history; return h && h.length ? (h[h.length - 1].label || '') : ''; };
  if (isMultiWeek()) {
    return rawPayload.opcoes_semanas.map(o => {
      const r = rawPayload.dados_semanas[o.id] || {};
      return { id: String(o.id), title: `${o.id}ª semana`, range: r.period || o.rotulo, short: lastLabel(r) };
    });
  }
  return [{ id: 'padrao', title: String(rawPayload.edition || 'Relatório').split(' · ')[0], range: rawPayload.period || '', short: lastLabel(rawPayload) }];
}

function syncUrl() {
  if (!isMultiWeek()) return;
  try {
    const url = new URL(location.href);
    if (activeWeekId === String(rawPayload.semana_padrao)) url.searchParams.delete('semana');
    else url.searchParams.set('semana', activeWeekId);
    history.replaceState(history.state, '', url);
  } catch (_) {}
}

function initSlicer() {
  const root = document.getElementById('filtro-semana');
  if (!root) return;
  const btn = document.getElementById('btn-semana-atual');
  const search = document.getElementById('busca-semana');
  const list = document.getElementById('lista-semanas');
  const panel = document.getElementById('painel-semana');
  const reset = document.getElementById('limpar-semana');

  const single = weekOptions.length < 2;
  btn.disabled = single;
  search.closest('.periodo-busca').hidden = weekOptions.length < 8;
  list.tabIndex = 0;

  btn.addEventListener('click', () => root.classList.contains('aberto') ? closeSlicer(true) : openSlicer());
  btn.addEventListener('keydown', e => { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); openSlicer(); } });
  search.addEventListener('input', () => renderSlicerList(search.value));
  panel.addEventListener('keydown', onSlicerKey);
  list.addEventListener('click', e => { const li = e.target.closest('.periodo-item'); if (li) selectWeek(li.dataset.id); });
  list.addEventListener('pointermove', e => {
    if (e.clientX === lastPointer.x && e.clientY === lastPointer.y) return;
    lastPointer = { x: e.clientX, y: e.clientY };
    const li = e.target.closest('.periodo-item');
    if (li) setSlicerActive(Number(li.dataset.idx), false);
  });
  reset.addEventListener('click', () => selectWeek(weekOptions[0].id));
  document.addEventListener('pointerdown', e => { if (!root.contains(e.target)) closeSlicer(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && root.classList.contains('aberto')) closeSlicer(true); });
  renderSlicerList('');
}

function openSlicer() {
  const root = document.getElementById('filtro-semana');
  if (!root || weekOptions.length < 2) return;
  const search = document.getElementById('busca-semana');
  search.value = '';
  root.classList.add('aberto');
  document.getElementById('btn-semana-atual').setAttribute('aria-expanded', 'true');
  renderSlicerList('');
  (search.closest('.periodo-busca').hidden ? document.getElementById('lista-semanas') : search).focus({ preventScroll: true });
  setSlicerActive(Math.max(0, slicerItems.findIndex(o => o.id === activeWeekId)), true);
}

function closeSlicer(returnFocus) {
  const root = document.getElementById('filtro-semana');
  if (!root || !root.classList.contains('aberto')) return;
  root.classList.remove('aberto');
  const btn = document.getElementById('btn-semana-atual');
  btn.setAttribute('aria-expanded', 'false');
  if (returnFocus) btn.focus({ preventScroll: true });
}

function renderSlicerList(query = '') {
  const q = normText(query).trim();
  const list = document.getElementById('lista-semanas');
  slicerItems = weekOptions.filter(o => !q || normText(`${o.title} ${o.range}`).includes(q));
  const latest = weekOptions[0] && weekOptions[0].id;
  if (!slicerItems.length) {
    list.innerHTML = '<li class="periodo-vazio" role="presentation">Nenhuma semana encontrada</li>';
  } else {
    list.innerHTML = slicerItems.map((o, i) => {
      const selected = o.id === activeWeekId;
      return `<li class="periodo-item${selected ? ' selecionado' : ''}" role="option" id="semana-opt-${esc(o.id)}" data-id="${esc(o.id)}" data-idx="${i}" aria-selected="${selected}"><span class="periodo-check" aria-hidden="true"></span><span class="periodo-item-texto"><b>${esc(o.title)}</b><small>${esc(o.range)}</small></span>${o.id === latest && weekOptions.length > 1 ? '<span class="periodo-tag">Mais recente</span>' : ''}</li>`;
    }).join('');
    const sel = slicerItems.findIndex(o => o.id === activeWeekId);
    setSlicerActive(sel >= 0 ? sel : 0, true);
  }
  document.getElementById('contagem-semanas').textContent = slicerItems.length === weekOptions.length
    ? `${weekOptions.length} ${weekOptions.length === 1 ? 'semana' : 'semanas'}`
    : `${slicerItems.length} de ${weekOptions.length} semanas`;
}

function setSlicerActive(idx, scroll = true) {
  const list = document.getElementById('lista-semanas');
  const items = [...list.querySelectorAll('.periodo-item')];
  const search = document.getElementById('busca-semana');
  if (!items.length) { search.removeAttribute('aria-activedescendant'); list.removeAttribute('aria-activedescendant'); return; }
  slicerActive = Math.max(0, Math.min(items.length - 1, idx));
  items.forEach((el, i) => el.classList.toggle('ativo', i === slicerActive));
  const el = items[slicerActive];
  search.setAttribute('aria-activedescendant', el.id);
  list.setAttribute('aria-activedescendant', el.id);
  if (scroll) {
    const top = el.offsetTop, bottom = top + el.offsetHeight;
    if (top < list.scrollTop) list.scrollTop = top - 4;
    else if (bottom > list.scrollTop + list.clientHeight) list.scrollTop = bottom - list.clientHeight + 4;
  }
}

function onSlicerKey(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); setSlicerActive(slicerActive + 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); setSlicerActive(slicerActive - 1); }
  else if (e.key === 'PageDown') { e.preventDefault(); setSlicerActive(slicerActive + 5); }
  else if (e.key === 'PageUp') { e.preventDefault(); setSlicerActive(slicerActive - 5); }
  else if (e.key === 'Enter') { e.preventDefault(); const o = slicerItems[slicerActive]; if (o) selectWeek(o.id); }
}

function selectWeek(id, { closeMenu = true } = {}) {
  if (id !== activeWeekId) {
    const previous = activeWeekId;
    activeWeekId = id;
    if (!renderCurrentWeek()) activeWeekId = previous;
    syncUrl();
  }
  if (closeMenu) closeSlicer(true);
}

function updateSlicerUI() {
  const opt = weekOptions.find(o => o.id === activeWeekId) || weekOptions[0];
  if (!opt) return;
  document.getElementById('texto-semana-ativa').textContent = opt.short ? `${opt.title} · ${opt.short}` : opt.title;
  document.getElementById('btn-semana-atual').title = `${opt.title} · ${opt.range}`;
  document.getElementById('limpar-semana').disabled = weekOptions.length < 2 || activeWeekId === weekOptions[0].id;
  renderSlicerList(document.getElementById('busca-semana').value);
}

function renderCurrentWeek() {
  const candidate = getWeekReport(activeWeekId);
  if (!candidate?.proposals?.length || !candidate?.kpis?.length) {
    showToast('A semana selecionada não possui dados completos.');
    return false;
  }
  
  const previousProposalId = report?.proposals?.[selectedProposal]?.id;
  report = candidate;

  // --- SUBTÍTULO DINÂMICO (ao lado do cartão "Engajamento Geral"; trechos-chave em negrito) ---
  let dynSummary = esc(report.summary || '');
  if (report.history && report.history.length > 0 && report.proposals && report.proposals.length > 0) {
    const vals = report.history;
    const curr = vals[vals.length - 1];
    const prev = vals.length > 1 ? vals[vals.length - 2] : null;
    
    // Variação em relação à semana anterior
    const repChange = report.kpis?.[0]?.change;
    let changeVal = repChange != null ? repChange : (prev && prev.value ? ((curr.value - prev.value) / prev.value) * 100 : null);
    let changeText = changeVal != null ? `${changeVal >= 0 ? 'aumentou' : 'caiu'} ${percentage(Math.abs(changeVal))}` : 'teve variação desconhecida';
    
    // Variação em relação à mediana
    let medianDelta = report.median ? ((curr.value - report.median) / report.median) * 100 : null;
    let medianText = medianDelta != null ? `ficou <strong>${esc(percentage(Math.abs(medianDelta)))} ${medianDelta >= 0 ? 'acima' : 'abaixo'}</strong> da mediana do ano` : 'sem dados de mediana do ano';
    
    // Proposta destaque
    const topP = report.proposals[0];
    const topPName = topP.id;
    const topPShare = percentage(topP.share || 0);
    
    dynSummary = `O engajamento <strong>${esc(changeText)}</strong> em relação à semana anterior e ${medianText}. O destaque fica para <strong>${esc(topPName)}</strong>, que concentrou <strong>${esc(topPShare)}</strong> dos pontos de engajamento da semana.`;
  }
  document.getElementById('cover-summary').innerHTML = dynSummary;
  // -------------------------

  document.title = `Câmara nas Redes — ${String(report.edition || 'Relatório semanal').split(' · ')[0]}`;

  // Destaques: só o cartão de Engajamento Geral, em formato compacto e com a comparação no rodapé
  const engKpi = report.kpis.find(k => String(k.label).toUpperCase() === 'ENGAJAMENTO GERAL');
  if (engKpi) {
    const ch = engKpi.change;
    const foot = ch == null ? 'Sem comparativo com a semana anterior' : (ch < 0 ? 'Inferior à semana anterior' : (ch > 0 ? 'Superior à semana anterior' : 'Igual à semana anterior'));
    renderKpis([{ ...engKpi, foot, format: 'compact' }], 'kpi-grid');
  }
  if (forceProposalIdx !== null) {
    selectedProposal = forceProposalIdx;
    forceProposalIdx = null;
  } else {
    const foundIdx = report.proposals.findIndex(p => p.id === previousProposalId);
    selectedProposal = foundIdx >= 0 ? foundIdx : 0;
  }
  

  renderTrend();
  renderCards();
  renderProposalSuggestions(proposalSearchQuery);
  renderAnalyticOverview();
  renderAnnualTrend();
  renderAnalyticCards();
  renderProposalTabs();
  renderProposalDetail();
  renderMethod();
  updateSlicerUI();
  return true;
}

function renderKpis(items,target) {
  const node=document.getElementById(target);
  node.innerHTML=items.map(k=>{
    const isUp = Number(k.change) >= 0;
    const isPostsOrReach = ['POSTAGENS', 'POSTAGEM', 'ALCANCE ESTIMADO'].includes(String(k.label).toUpperCase());
    const showBadge = k.change != null && !(target === 'kpi-grid' && isPostsOrReach);
    const changeBadge = showBadge
      ? `<span class="kpi-change ${isUp ? 'up' : 'down'}">${isUp ? '↑' : '↓'} ${percentage(Math.abs(k.change))}</span>`
      : '';
    return `<article class="kpi-card"><span class="kpi-label">${esc(k.label)}</span><strong class="kpi-value">${formatNumber(k.value,k.format==='compact')}</strong><div class="kpi-foot">${changeBadge}<span>${esc(k.foot||'')}</span></div></article>`;
  }).join('');
}

/* Rótulo da mediana na margem direita do gráfico (fora das colunas), em duas linhas. */
const MEDIAN_GUTTER = 96;
const ANNUAL_GUTTER = 118; // margem direita do gráfico anual (rótulo da mediana afastado da linha)
const ANNUAL_MAX = 35e6;  // teto fixo do eixo Y do gráfico anual (35 mi)
function medianLabel(x, y, title, value, dx = 8) {
  return `<text class="axis-label median-label" x="${x + dx}" y="${y - 3}" text-anchor="start"><tspan x="${x + dx}">${esc(title)}</tspan><tspan x="${x + dx}" dy="13">${esc(formatNumber(value, true))}</tspan></text>`;
}

function svgWrap(viewBox,content,label) { return `<svg viewBox="0 0 ${viewBox}" role="img" aria-label="${esc(label)}" xmlns="http://www.w3.org/2000/svg">${content}</svg>`; }

/* ===== Gráfico de Evolução (Colunas) ===== */
function renderTrend() {
  const chartNode=document.getElementById('trend-chart');
  if(!chartNode) return;
  const W=Math.max(320,Math.round(chartNode.clientWidth||900)), H=260, left=56, right=report.median?MEDIAN_GUTTER:20, top=32, bottom=46;
  const values=report.history||[];
  if(!values.length){chartNode.innerHTML='<div class="empty-state">Ainda não há histórico semanal na base.</div>';return;}

  const rawMax = Math.max(...values.map(x=>x.value||0), report.median||0);
  const order = Math.pow(10, Math.floor(Math.log10(rawMax || 1)));
  let ceilMax = Math.ceil(rawMax / order) * order;
  if (ceilMax === rawMax) ceilMax += order; 
  
  let stepVal = ceilMax / 4;
  if (String(stepVal).charAt(0) === '2' && String(stepVal).includes('.5')) {
      ceilMax = Math.ceil(rawMax / (order/2)) * (order/2);
  }
  
  const y = v => top + (H - bottom - top) * (1 - (v / ceilMax));
  const plotW = W - left - right;
  const colStep = plotW / values.length;
  const barW = Math.min(180, colStep * 0.8);
  const x = i => left + colStep * i + (colStep / 2);

  let parts='';
  
  [0, 0.25, 0.5, 0.75, 1].forEach(p => {
    const yy = top + (H - bottom - top) * p;
    const val = ceilMax * (1 - p);
    parts += `<text class="axis-label" x="${left-12}" y="${yy+4}" text-anchor="end" fill="#000">${formatNumber(val, true)}</text>`;
  });
  
  values.forEach((d,i) => {
    const yy = y(d.value);
    const bh = (H - bottom) - yy;
    const xx = x(i) - barW/2;

    parts += `<rect class="bar-trend" style="fill:#134e5e" x="${xx}" y="${yy}" width="${barW}" height="${Math.max(0, bh)}" rx="4"><title>Semana ${d.week}: ${esc(d.display||formatNumber(d.value))}</title></rect>
    <text class="value-label" x="${x(i)}" y="${yy-8}" text-anchor="middle" fill="#000">${esc(d.display||formatNumber(d.value,true))}</text>
    ${W<480?'':`<text class="axis-label" x="${x(i)}" y="${H-24}" text-anchor="middle" font-weight="700" fill="#000">${esc(d.label)}</text>`}
    <text class="axis-label" x="${x(i)}" y="${H-10}" text-anchor="middle" fill="#000">Semana ${d.week}</text>`;
  });

  if (report.median) {
    const yy = y(report.median);
    parts += `<line class="median" x1="${left}" y1="${yy}" x2="${W-right}" y2="${yy}"/>
              ${medianLabel(W-right, yy, 'Mediana anual', report.median)}`;
  }

  chartNode.innerHTML=svgWrap(`${W} ${H}`,parts,'Evolução semanal do engajamento.');
}

function buildFallbackSummary(p, withStatus = true) {
  if (p.summary) return p.summary;
  const parts = [];
  if (p.posts != null && p.authors != null) {
    parts.push(`Reuniu ${formatNumber(p.posts)} publicações de ${formatNumber(p.authors)} autores únicos na semana`);
  } else if (p.posts != null) {
    parts.push(`Reuniu ${formatNumber(p.posts)} publicações monitoradas na semana`);
  }
  if (p.reach != null) {
    parts.push(`com alcance estimado de ${formatNumber(p.reach, true)}`);
  }
  const sentence1 = parts.length ? parts.join(', ') + '.' : '';
  const sentence2 = (withStatus && p.status) ? `Situação atual: ${p.status}.` : '';
  return [sentence1, sentence2].filter(Boolean).join(' ') || 'Consulte os dados disponíveis para esta proposta no detalhamento.';
}

function proposalCardMarkup(p, idx) {
  return `
    <article class="proposal-card" data-open="${idx}" tabindex="0" role="button" aria-label="Ver detalhes de ${esc(p.id)}">
      <div class="proposal-card-left">
        <div class="proposal-title-row">
          <span class="rank-badge">${idx + 1}º</span>
          <h3>${esc(p.id)}</h3>
        </div>
        <div class="card-metrics">
          <div class="metric-mini">
            <label>ENGAJAMENTO</label>
            <b>${formatNumber(p.engagement)}</b>
          </div>
          <div class="metric-mini">
            <label>(%) DO TOTAL</label>
            <b>${percentage(p.share || 0)}</b>
          </div>
        </div>
      </div>
      <div class="proposal-card-right">
        <div class="proposal-summary">${esc(p.description)}</div>
        <p class="card-copy">${esc(p.mobilization || buildFallbackSummary(p, false))}</p>
        <span class="saiba-mais" aria-hidden="true">Saiba mais <svg viewBox="0 0 12 12"><path d="M3 9 9 3M4.5 3H9v4.5"/></svg></span>
      </div>
    </article>`;
}

function wireProposalCards(container) {
  container.querySelectorAll('[data-open]').forEach(n => {
    n.addEventListener('click', e => {
      e.stopPropagation();
      openProposal(Number(n.dataset.open));
    });
    n.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openProposal(Number(n.dataset.open));
      }
    });
  });
}

function renderCards() {
  const container = document.getElementById('highlight-cards');
  if (!container || !report?.proposals) return;

  const q = normText(proposalSearchQuery).trim();
  const indexedProposals = report.proposals.map((p, idx) => ({ p, idx }));

  const filtered = q
    ? indexedProposals.filter(({ p }) =>
        normText(`${p.id} ${p.description} ${p.status || ''} ${buildFallbackSummary(p)}`).includes(q)
      )
    : indexedProposals.slice(0, 5);

  if (!filtered.length) {
    container.innerHTML = `<div class="empty-state">Nenhuma proposta encontrada para "<strong>${esc(proposalSearchQuery)}</strong>".</div>`;
    return;
  }

  container.innerHTML = filtered.map(({ p, idx }) => proposalCardMarkup(p, idx)).join('');
  wireProposalCards(container);
}

/* Analítico: linha com as 5 propostas em destaque da semana selecionada (abaixo do gráfico anual). */
function renderAnalyticCards() {
  const container = document.getElementById('analytic-cards');
  if (!container || !report?.proposals) return;
  const opt = weekOptions.find(o => o.id === activeWeekId);
  const label = document.getElementById('analytic-cards-week');
  if (label) label.textContent = opt ? `${opt.title} · ${opt.range}` : '';
  // linha no mesmo padrão do menu da aba Propostas; clicar abre a proposta
  container.innerHTML = report.proposals.slice(0, 5).map((p, idx) => `<button type="button" class="proposal-tab" data-open="${idx}" aria-label="Abrir ${esc(p.id)} na aba Propostas"><span class="proposal-tab-rank">${String(idx + 1).padStart(2, '0')}</span><span>${esc(p.id)}</span></button>`).join('');
  container.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => openProposal(Number(b.dataset.open))));
}

function chartLabelLines(value,maxChars){
  const words=String(value).split(/\s+/),lines=[];let line='';
  words.forEach(word=>{const next=line?`${line} ${word}`:word;if(line&&next.length>maxChars){lines.push(line);line=word}else line=next;});
  if(line)lines.push(line);return lines;
}

/* Barras horizontais. Em colunas estreitas: nome acima da barra. Em largura total: nome à esquerda. */
/* Teto de eixo com passos redondos: `divisions` intervalos iguais cobrindo o maior valor. */
function niceMax(value, divisions) {
  const raw = Math.max(value, 1) * 1.04 / divisions;
  const order = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = ([1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map(m => m * order).find(v => v >= raw)) || raw;
  return step * divisions;
}
function renderBarChart(target, data, {max=null, compact=true, colorMap=null, tickFormat=null}={}) {
  const node=document.getElementById(target);
  if(!node) return;
  if(!data.length){node.innerHTML='<div class="empty-state">Ainda não há dados suficientes para este gráfico.</div>';return;}
  const W=Math.max(220,Math.round(node.clientWidth||320)), wide=W>=560;
  const right=wide?70:58, top=4, bottom=24, rowH=wide?36:44, barH=wide?18:14;
  const left=wide?Math.min(270,Math.round(W*.3)):2;
  const H=data.length*rowH+top+bottom, plotW=W-left-right;
  const maxVal=max||niceMax(Math.max(...data.map(d=>d.value||0)),wide?4:2);
  const fmtTick=tickFormat||(v=>formatNumber(v,compact));
  const maxChars=wide?Math.floor((left-12)/6.0):Math.max(14,Math.floor(W/6.9));
  let out='';
  (wide?[0,.25,.5,.75,1]:[0,.5,1]).forEach(t=>{const xx=left+plotW*t;out+=`<line class="gridline" x1="${xx}" y1="${top}" x2="${xx}" y2="${H-bottom}"/><text class="axis-label" x="${xx}" y="${H-6}" text-anchor="${t===0&&!wide?'start':(t===1?'end':'middle')}">${esc(fmtTick(maxVal*t))}</text>`;});
  data.forEach((d,i)=>{
    const y0=top+rowH*i, name=String(d.name);
    const shown=name.length>maxChars?name.slice(0,maxChars-1).trimEnd()+'…':name;
    const bw=Math.max(1.5,plotW*Math.max(d.value||0,0)/maxVal);
    const fill=(colorMap&&colorMap[d.name])?`style="fill:${colorMap[d.name]}"`:'';
    const label=d.display||formatNumber(d.value,compact);
    const by=wide?y0+(rowH-barH)/2:y0+19;
    const nameEl=wide
      ?`<text class="axis-label chart-category" x="${left-10}" y="${by+barH*.72}" text-anchor="end">${esc(shown)}<title>${esc(name)}</title></text>`
      :`<text class="axis-label chart-category" x="${left}" y="${y0+13}">${esc(shown)}<title>${esc(name)}</title></text>`;
    out+=`${nameEl}
      <rect class="bar" x="${left}" y="${by}" width="${bw}" height="${barH}" rx="3" ${fill}><title>${esc(name)}: ${esc(d.display||formatNumber(d.value))}</title></rect>
      <text class="value-label" x="${left+bw+6}" y="${by+barH*.75}">${esc(label)}</text>`;
  });
  node.innerHTML=svgWrap(`${W} ${H}`,out,'Gráfico de barras: '+data.map(d=>`${d.name}, ${d.display||formatNumber(d.value)}`).join('; '));
}

/* ===== Analítico: interruptor "Total Anual" =====
   Ligado: cartões, canais, propostas (top 5) e categorias passam a somar todas as semanas do ano.
   Sem base do ano anterior, os cartões perdem a variação % e a legenda. */
let annualMode = false;

function annualWeekReports() {
  const weeks = (rawPayload?.evolucao_anual || []).map(v => String(v.week));
  const ids = weeks.length ? weeks : Object.keys(rawPayload?.dados_semanas || {});
  return ids.map(id => rawPayload?.dados_semanas?.[id]).filter(Boolean);
}

function sumByName(lists) {
  const acc = new Map();
  lists.flat().forEach(d => { if (d && d.name != null) acc.set(d.name, (acc.get(d.name) || 0) + (Number(d.value) || 0)); });
  return [...acc].map(([name, value]) => ({ name, value }));
}

function annualAggregate() {
  const weeks = annualWeekReports();
  const kpis = (report.kpis || []).map(k => ({
    label: k.label,
    value: weeks.reduce((s, w) => s + (Number(w.kpis?.find(x => x.label === k.label)?.value) || 0), 0),
    change: null,
    foot: '',
  }));
  const engTotal = kpis.find(k => String(k.label).toUpperCase() === 'ENGAJAMENTO GERAL')?.value || 0;
  const byProposal = new Map();
  weeks.forEach(w => (w.proposals || []).forEach(p => byProposal.set(p.id, (byProposal.get(p.id) || 0) + (Number(p.engagement) || 0))));
  const proposals = [...byProposal].map(([id, engagement]) => ({ id, engagement, share: engTotal ? engagement / engTotal * 100 : 0 }))
    .sort((a, b) => b.engagement - a.engagement);
  return {
    kpis,
    channels: sumByName(weeks.map(w => w.channels || [])),
    topics: sumByName(weeks.map(w => w.topics || [])).sort((a, b) => b.value - a.value),
    proposals,
  };
}

function renderAnalyticOverview() {
  const src = annualMode && isMultiWeek() ? annualAggregate() : report;
  document.getElementById('analitico')?.classList.toggle('is-annual', annualMode);
  renderKpis(src.kpis, 'analytic-kpis');
  renderChannelChart(src.channels);
  renderShareChart(src.proposals);
  renderTopics(src.topics);
}

function initAnnualToggle() {
  const input = document.getElementById('toggle-total-anual');
  if (!input) return;
  if (!isMultiWeek()) { input.closest('.annual-toggle').hidden = true; return; }
  input.addEventListener('change', () => {
    annualMode = input.checked;
    input.setAttribute('aria-checked', String(annualMode));
    renderAnalyticOverview();
  });
}

function renderChannelChart(channels = report.channels){
  const sortedChannels = [...(channels || [])].sort((a, b) => b.value - a.value);
  
  renderBarChart('channel-chart', sortedChannels, {
    labels: true, 
    compact: true,
    colorMap: {
      'Instagram': '#C13584',
      'X (Twitter)': '#101010',
      'Facebook': '#1877F2',
      'Bluesky': '#1185FE'
    }
  });
}
function renderTopics(topics = report.topics){renderBarChart('topic-chart',topics||[],{labels:true,compact:true});}

/* ===== Evolução anual (linhas): todas as semanas do ano na base; semana selecionada em destaque ===== */
function renderAnnualTrend() {
  const node = document.getElementById('annual-chart');
  if (!node) return;
  const values = rawPayload?.evolucao_anual || [];
  const yearNode = document.getElementById('annual-year');
  if (yearNode) yearNode.textContent = rawPayload?.ano ? `Semanas de ${rawPayload.ano}` : '';
  if (values.length < 2) { node.innerHTML = '<div class="empty-state">Ainda não há semanas suficientes para a evolução anual.</div>'; return; }
  const median = report?.median || null;
  const W = Math.max(320, Math.round(node.clientWidth || 900)), H = 400;
  const left = 56, right = median ? ANNUAL_GUTTER : 20, top = 30, bottom = 40;
  // eixo Y fixo em 35 mi (cresce só se algum valor passar disso)
  const dataMax = Math.max(...values.map(v => v.value), median || 0);
  const max = dataMax <= ANNUAL_MAX ? ANNUAL_MAX : niceCeil(dataMax);
  const plotW = W - left - right, base = H - bottom;
  const x = i => left + plotW * i / (values.length - 1);
  const y = v => top + (base - top) * (1 - v / max);
  const step = Math.max(1, Math.ceil(values.length / Math.max(4, Math.floor(plotW / 60))));
  const current = values.findIndex(v => String(v.week) === String(activeWeekId));
  let out = '';
  for (let v = 0; v <= max + 1; v += max <= ANNUAL_MAX ? 5e6 : max / 4) {
    out += `<line class="gridline" x1="${left}" y1="${y(v)}" x2="${W - right}" y2="${y(v)}"/><text class="axis-label" x="${left - 10}" y="${y(v) + 4}" text-anchor="end">${formatNumber(v, true)}</text>`;
  }
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v.value).toFixed(1)}`);
  out += `<path class="annual-area" d="M${x(0)},${base} L${pts.join(' L')} L${x(values.length - 1)},${base} Z"/>`;
  out += `<path class="annual-line" d="M${pts.join(' L')}"/>`;
  if (median) {
    out += `<line class="median" x1="${left}" y1="${y(median)}" x2="${W - right}" y2="${y(median)}"/>${medianLabel(W - right, y(median), 'Mediana anual', median, 22)}`;
  }
  // rótulos do eixo X: de step em step, mais a semana atual e a última (sem encostar uns nos outros)
  const keep = new Set([...values.keys()].filter(i => i === current || i === values.length - 1));
  values.forEach((_, i) => {
    if (i % step === 0 && [...keep].every(k => Math.abs(x(i) - x(k)) >= 40)) keep.add(i);
  });
  values.forEach((v, i) => {
    const isCur = i === current;
    if (keep.has(i)) {
      out += `<text class="axis-label${isCur ? ' annual-cur-label' : ''}" x="${x(i)}" y="${H - 14}" text-anchor="middle">${v.week}ª</text>`;
    }
    out += `<circle class="annual-dot${isCur ? ' current' : ''}" cx="${x(i)}" cy="${y(v.value)}" r="${isCur ? 6 : 3.5}"/>`;
  });
  // áreas de captura (maiores que os pontos): tooltip ao passar o mouse e seleção da semana ao clicar
  values.forEach((v, i) => {
    out += `<circle class="annual-hit" data-week="${v.week}" data-label="${esc(v.label)}" data-value="${v.value}" cx="${x(i)}" cy="${y(v.value)}" r="11"/>`;
  });
  if (current >= 0) {
    const v = values[current];
    const anchor = current === 0 ? 'start' : (current === values.length - 1 ? 'end' : 'middle');
    out += `<text class="value-label" x="${x(current)}" y="${y(v.value) - 12}" text-anchor="${anchor}">${esc(formatNumber(v.value, true))}</text>`;
  }
  node.innerHTML = svgWrap(`${W} ${H}`, out, `Evolução anual do engajamento: ${values.length} semanas, de ${values[0].week}ª a ${values[values.length - 1].week}ª.`);
  wireAnnualInteractions(node);
}

/* Tooltip e clique dos pontos do gráfico anual (listeners delegados: registrados uma única vez). */
function wireAnnualInteractions(node) {
  let tip = node.querySelector('.annual-tip');
  if (!tip) { tip = document.createElement('div'); tip.className = 'annual-tip'; tip.setAttribute('role', 'tooltip'); }
  node.appendChild(tip); // innerHTML recria o SVG; o tooltip é reanexado
  tip.classList.remove('show');
  if (node.dataset.wired) return;
  node.dataset.wired = '1';
  const hitOf = e => e.target.closest?.('.annual-hit');
  const show = hit => {
    const nodeBox = node.getBoundingClientRect(), box = hit.getBoundingClientRect();
    const week = hit.dataset.week, isActive = String(week) === String(activeWeekId);
    const t = node.querySelector('.annual-tip');
    t.innerHTML = `<strong>${esc(week)}ª semana</strong><span>${esc(hit.dataset.label)}</span><span>${esc(formatNumber(Number(hit.dataset.value)))} pontos</span><em>${isActive ? 'Semana selecionada' : 'Clique para ver esta semana'}</em>`;
    const cx = box.left + box.width / 2 - nodeBox.left, cy = box.top + box.height / 2 - nodeBox.top;
    const below = cy < 110; // perto do topo: mostra abaixo do ponto
    t.style.left = `${Math.min(Math.max(cx, 90), nodeBox.width - 90)}px`;
    t.style.top = `${cy + (below ? 16 : -16)}px`;
    t.classList.toggle('below', below);
    t.classList.add('show');
  };
  node.addEventListener('pointerover', e => { const h = hitOf(e); if (h) show(h); });
  node.addEventListener('pointerout', e => { if (hitOf(e)) node.querySelector('.annual-tip')?.classList.remove('show'); });
  node.addEventListener('click', e => {
    const h = hitOf(e);
    if (!h) return;
    selectWeek(String(h.dataset.week));
    document.getElementById('analytic-cards-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function renderShareChart(proposals = report.proposals) {
  const data=(proposals||[]).slice(0,5).map(p=>({name:p.id,value:p.share||0,display:percentage(p.share||0)}));
  renderBarChart('share-chart',data,{max:100,tickFormat:v=>percentage(v)});
}

/* ===== Aba "Propostas" (layout do wireframe) ===== */
function percentage1(value) { return `${Number(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})}%`; }
function countLabel(n, singular, plural) { return `${formatNumber(n)} ${n === 1 ? singular : plural}`; }
function shortChannelName(name) { return String(name).replace(/\s*\(.*\)\s*$/, ''); }

function renderProposalTabs() {
  const limit = Math.max(5, selectedProposal + 1);
  const list = report.proposals.slice(0, limit);
  document.getElementById('proposal-tabs').innerHTML=list.map((p,i)=>`<button class="proposal-tab ${i===selectedProposal?'active':''}" role="tab" aria-selected="${i===selectedProposal}" data-index="${i}"><span class="proposal-tab-rank">${String(i+1).padStart(2,'0')}</span><span>${esc(p.id)}</span></button>`).join('');
  // só as abas do menu da aba Propostas (a linha do Analítico usa a mesma classe e tem seu próprio clique)
  document.querySelectorAll('#proposal-tabs .proposal-tab').forEach(n=>n.addEventListener('click',()=>{selectedProposal=Number(n.dataset.index);renderProposalTabs();renderProposalDetail();}));
}

function buildProposalKpis(p) {
  const ch = p.changes || {};
  // changes_week = última semana em que a proposta apareceu (pode não ser a imediatamente anterior)
  const currentWeek = Number(activeWeekId);
  const refWeek = p.changes_week;
  const ref = refWeek == null || refWeek === currentWeek - 1 ? 'à semana anterior' : `à ${refWeek}ª semana`;
  const make = (label, value, change) => {
    const hasChange = change != null;
    const foot = !hasChange
      ? (refWeek == null ? 'Sem registros anteriores' : `Sem base de comparação na ${refWeek}ª semana`)
      : (change < 0 ? `Inferior ${ref}` : (change > 0 ? `Superior ${ref}` : `Igual ${ref}`));
    return { label, value, change: hasChange ? change : null, foot, format: value >= 1e9 ? 'compact' : '' };
  };
  return [
    make('ENGAJAMENTO GERAL', p.engagement, ch.engagement),
    make('POSTAGEM', p.posts, ch.posts),
    make('AUTORES', p.authors, ch.authors),
    make('ALCANCE ESTIMADO', p.reach, ch.reach)
  ];
}

/* Texto do bloco "Engajamento por Canal", gerado a partir dos pontos de cada rede. */
function channelNarrative(list) {
  const total = list.reduce((sum, c) => sum + c.value, 0) || 1;
  const pct = c => percentage1(c.value / total * 100);
  const name = c => shortChannelName(c.name);
  const [first, second, ...rest] = list;
  const out = [`O ${name(first)} teve destaque com ${formatNumber(first.value)} pontos (${pct(first)}).`];
  if (second) out.push(`O ${name(second)} também teve participação relevante, com ${formatNumber(second.value)} (${pct(second)}).`);
  if (rest.length === 1) {
    out.push(`${name(rest[0])} somou ${formatNumber(rest[0].value)} (${pct(rest[0])}).`);
  } else if (rest.length > 1) {
    const last = rest[rest.length - 1];
    const init = rest.slice(0, -1).map(c => `${name(c)} somou ${formatNumber(c.value)} (${pct(c)})`);
    out.push(`${init.join(', ')} e ${name(last)}, ${formatNumber(last.value)} pontos.`);
  }
  return out.join(' ');
}

/* Mesmas cores do gráfico "Engajamento por canal" da aba Analítico. */
const CHANNEL_COLORS = {
  'Instagram': '#C13584',
  'X (Twitter)': '#101010',
  'Facebook': '#1877F2',
  'Bluesky': '#1185FE',
  'YouTube': '#FF0000'
};
const DASH_BAR_COLOR = '#134e5e'; /* cor das colunas de evolução do dashboard */

function niceCeil(value) {
  const raw = Math.max(value, 1) * 1.05;
  const order = Math.pow(10, Math.floor(Math.log10(raw)));
  return ([1, 1.2, 1.6, 2, 2.4, 3, 4, 5, 6, 8, 10].map(m => m * order).find(v => v >= raw)) || raw;
}

/* Gráfico de colunas responsivo (Canais de Destaque / O que Dizem).
   items: [{name, value, label, title}]; o rótulo fica dentro da coluna quando cabe. */
function renderColumnChart(nodeId, items, { max, ticks, tickFormat, colorFor, ariaLabel, height = 250 }) {
  const node = document.getElementById(nodeId);
  if (!node) return;
  if (!items.length) { node.innerHTML = '<div class="empty-state">Ainda não há dados para este gráfico.</div>'; return; }
  const W = Math.max(300, Math.round(node.clientWidth || 640)), left = 50, right = 12, top = 22;
  const slot = (W - left - right) / items.length;
  const barW = Math.min(118, slot * 0.72);
  const maxChars = Math.max(8, Math.floor(slot / 6.6));
  const labelLines = items.map(d => chartLabelLines(d.name, maxChars));
  const bottom = 14 + Math.max(...labelLines.map(l => l.length)) * 13;
  const H = height + bottom - 30, base = H - bottom;
  const y = v => top + (base - top) * (1 - v / max);
  let out = '';
  ticks.forEach(t => {
    out += `<line class="gridline" x1="${left}" y1="${y(t)}" x2="${W - right}" y2="${y(t)}"/><text class="axis-label" x="${left - 8}" y="${y(t) + 4}" text-anchor="end">${esc(tickFormat(t))}</text>`;
  });
  out += `<line class="mini-base" x1="${left}" y1="${base}" x2="${W - right}" y2="${base}"/>`;
  items.forEach((d, i) => {
    const cx = left + slot * i + slot / 2;
    const h = Math.max(2, base - y(Math.min(d.value, max)));
    const color = colorFor(d, i);
    // número sempre acima da coluna, na cor da própria coluna
    out += `<rect x="${cx - barW / 2}" y="${base - h}" width="${barW}" height="${h}" rx="2" style="fill:${color}"><title>${esc(d.title || `${d.name}: ${d.label}`)}</title></rect>
      <text class="col-value" x="${cx}" y="${base - h - 7}" text-anchor="middle" style="fill:${color}">${esc(d.label)}</text>
      <text class="axis-label col-category" x="${cx}" y="${base + 16}" text-anchor="middle">${labelLines[i].map((l, j) => `<tspan x="${cx}" dy="${j ? 13 : 0}">${esc(l)}</tspan>`).join('')}</text>`;
  });
  node.innerHTML = svgWrap(`${W} ${H}`, out, ariaLabel);
}

function renderProposalCharts(p) {
  if (!p) return;
  const channels = (p.channels || []).filter(c => c.value > 0).sort((a, b) => b.value - a.value);
  if (channels.length) {
    const max = niceCeil(channels[0].value);
    renderColumnChart('proposal-channel-chart', channels.map(c => ({
      name: c.name,
      value: c.value,
      label: formatNumber(c.value, true),
      title: `${c.name}: ${formatNumber(c.value)} pontos`,
      color: CHANNEL_COLORS[c.name]
    })), {
      max, ticks: [0, .25, .5, .75, 1].map(t => max * t), tickFormat: v => formatNumber(v, true),
      colorFor: d => d.color || DASH_BAR_COLOR,
      ariaLabel: 'Canais de destaque: ' + channels.map(c => `${c.name}, ${formatNumber(c.value)} pontos`).join('; ')
    });
  }
  const args = p.arguments || [];
  if (args.length) {
    renderColumnChart('proposal-args-chart', args.map(a => ({
      name: a.name,
      value: a.share || 0,
      label: percentage1(a.share || 0),
      title: `${a.name}: ${percentage1(a.share || 0)} (${countLabel(a.count, 'ocorrência', 'ocorrências')})`
    })), {
      max: 100, ticks: [0, 20, 40, 60, 80, 100], tickFormat: v => `${v}%`,
      colorFor: () => DASH_BAR_COLOR,
      ariaLabel: 'Argumentos mais citados: ' + args.map(a => `${a.name}, ${percentage1(a.share || 0)}`).join('; ')
    });
  }
}

/* Gráfico "Evolução nas últimas 4 semanas" da proposta selecionada. */
function renderProposalTrend(p) {
  const node = document.getElementById('proposal-trend-chart');
  if (!node || !p) return;
  const values = p.history || [];
  if (!values.some(v => v.value != null)) { node.innerHTML = '<div class="empty-state">Ainda não há histórico semanal para esta proposta.</div>'; return; }
  // mediana anual do engajamento das propostas que ficaram no top 5 de cada semana
  const median = report.proposal_median || null;
  const W = Math.max(320, Math.round(node.clientWidth || 900)), H = 260, left = 56, right = median ? MEDIAN_GUTTER : 20, top = 32, bottom = 46;
  const rawMax = Math.max(...values.map(v => v.value || 0), median || 0, 1) * 1.05;
  const order = Math.pow(10, Math.floor(Math.log10(rawMax)));
  const ceilMax = ([1, 1.2, 1.6, 2, 2.4, 2.8, 3.2, 4, 6, 8, 10].map(m => m * order).find(v => v >= rawMax)) || rawMax;
  const y = v => top + (H - bottom - top) * (1 - v / ceilMax);
  const plotW = W - left - right, colStep = plotW / values.length, barW = Math.min(64, colStep * 0.55);
  const x = i => left + colStep * i + colStep / 2;
  let parts = '';
  [0, 0.25, 0.5, 0.75, 1].forEach(t => {
    const yy = top + (H - bottom - top) * t;
    parts += `<line class="gridline" x1="${left}" y1="${yy}" x2="${W - right}" y2="${yy}"/><text class="axis-label" x="${left - 12}" y="${yy + 4}" text-anchor="end">${formatNumber(ceilMax * (1 - t), true)}</text>`;
  });
  values.forEach((d, i) => {
    const current = i === values.length - 1;
    const weekLabel = `<text class="axis-label" x="${x(i)}" y="${H - 10}" text-anchor="middle">Semana ${d.week}</text>${W < 480 ? '' : `<text class="axis-label" x="${x(i)}" y="${H - 24}" text-anchor="middle" font-weight="700">${esc(d.label)}</text>`}`;
    if (d.value == null) {
      parts += `<text class="axis-label muted" x="${x(i)}" y="${H - bottom - 8}" text-anchor="middle"><title>Fora das propostas mais engajadas desta semana</title>${W < 480 ? '—' : 'sem dados'}</text>${weekLabel}`;
      return;
    }
    const yy = y(d.value);
    parts += `<rect class="bar-trend" style="fill:#134e5e;opacity:${current ? 1 : 0.55}" x="${x(i) - barW / 2}" y="${yy}" width="${barW}" height="${Math.max(0, H - bottom - yy)}" rx="4"><title>Semana ${d.week}: ${esc(formatNumber(d.value))}</title></rect>
      <text class="value-label" x="${x(i)}" y="${yy - 8}" text-anchor="middle">${esc(formatNumber(d.value, true))}</text>${weekLabel}`;
  });
  if (median) {
    const yy = y(median);
    parts += `<line class="median" x1="${left}" y1="${yy}" x2="${W - right}" y2="${yy}"/>
      ${medianLabel(W - right, yy, 'Mediana top 5', median)}`;
  }
  node.innerHTML = svgWrap(`${W} ${H}`, parts, `Evolução do engajamento de ${p.id} nas últimas semanas.`);
}

function renderProposalDetail() {
  const host = document.getElementById('proposal-detail');
  const p = report.proposals[selectedProposal];
  if (!p) { host.innerHTML = '<div class="empty-state">Selecione uma proposta para ver o detalhamento.</div>'; return; }

  const channels = (p.channels || []).filter(c => c.value > 0).sort((a, b) => b.value - a.value);
  const args = p.arguments || [];

  const channelBlock = channels.length ? `
    <article class="panel prop-block">
      <h3>Canais de Destaque</h3>
      <p class="block-copy">${esc(channelNarrative(channels))}</p>
      <div id="proposal-channel-chart" class="chart col-chart" aria-label="Gráfico de engajamento por canal da proposta"></div>
    </article>` : '';

  const mobilizationBlock = p.mobilization ? `
    <article class="panel prop-block"><h3>O que Mobilizou</h3><p class="block-copy">${esc(p.mobilization)}</p></article>` : '';

  let sayBlock = '';
  if (args.length) {
    const a = p.analysis || {};
    const counts = [];
    if (a.posts) counts.push(countLabel(a.posts, 'post', 'posts'));
    if (a.comments) counts.push(countLabel(a.comments, 'comentário', 'comentários'));
    const chip = [counts.join(' + '), 'Análise das postagens por IA com supervisão humana'].filter(Boolean).join(' | ');
    sayBlock = `
    <article class="panel prop-block">
      <div class="say-head"><h3>O que Dizem</h3><span class="say-chip">${esc(chip)}</span></div>
      <div id="proposal-args-chart" class="chart col-chart" aria-label="Gráfico dos argumentos mais citados"></div>
      ${args.map((arg, i) => `
        <section class="say-item">
          <h4>${i + 1} - ${esc(String(arg.name).toLocaleUpperCase('pt-BR'))} | ${countLabel(arg.count, 'ocorrência', 'ocorrências')} (${percentage1(arg.share)})</h4>
          ${arg.description ? `<p>${esc(arg.description)}</p>` : ''}
          ${arg.sample ? `<p class="say-label">Postagem representativa:</p><p>${esc(arg.sample)}</p>` : ''}
        </section>`).join('')}
    </article>`;
  }

  const emptyNote = (!channelBlock && !mobilizationBlock && !sayBlock)
    ? '<article class="panel prop-block"><p class="empty-state">A análise qualitativa e o engajamento por canal ainda não foram coletados para esta proposta.</p></article>' : '';

  host.innerHTML = `
    <div class="proposal-title-block heading-rule">
      <h3 class="proposal-title">${esc(p.id)}${p.link ? `<a class="proposal-ext-link" href="${esc(p.link)}" target="_blank" rel="noopener noreferrer" title="Abrir a página da proposta no site da Câmara" aria-label="Abrir a página de ${esc(p.id)} no site da Câmara (nova aba)"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 12 12 4M5.5 4H12v6.5"/></svg></a>` : ''}</h3>
    </div>
    ${p.description && p.description !== p.id ? `<p class="proposal-title-desc">${esc(p.description)}</p>` : ''}
    <div class="kpi-grid kpi-grid-compact" id="proposal-kpis"></div>
    <article class="panel prop-block">
      <div class="panel-heading"><h2 class="panel-title-sm">EVOLUÇÃO NAS ÚLTIMAS 4 SEMANAS</h2><span class="panel-note">Semana ${esc(String(report.edition || '').split('ª')[0])} em destaque</span></div>
      <div id="proposal-trend-chart" class="chart chart-trend" aria-label="Gráfico de evolução semanal da proposta"></div>
    </article>
    ${channelBlock}${mobilizationBlock}${sayBlock}${emptyNote}`;

  renderKpis(buildProposalKpis(p), 'proposal-kpis');
  renderProposalTrend(p);
  renderProposalCharts(p);
}

function openProposal(index){selectedProposal=index;renderProposalTabs();renderProposalDetail();navigateToPage('propostas');}

function renderMethod() {
  const items=(report.methodology||rawPayload?.methodology)?.[activeMethod]||[];
  document.getElementById('method-content').innerHTML=items.map(m=>`<article class="method-card"><h3>${esc(m.title)}</h3><p>${esc(m.text)}</p></article>`).join('');
}

document.querySelectorAll('.method-tab').forEach(b=>b.addEventListener('click',()=>{activeMethod=b.dataset.method;document.querySelectorAll('.method-tab').forEach(x=>x.classList.toggle('active',x===b));renderMethod();}));
const pageIds=['destaques','analitico','propostas','metodologia'];

function renderVisibleCharts(page){
  if(!report)return;
  if(page==='destaques')renderTrend();
  if(page==='propostas'){const p=report.proposals[selectedProposal];renderProposalTrend(p);renderProposalCharts(p);}
  if(page==='analitico'){renderAnalyticOverview();renderAnnualTrend();}
}

function navigateToPage(page,updateHistory=true) {
  if(!pageIds.includes(page))page='destaques';
  document.querySelectorAll('main .section').forEach(section=>section.classList.toggle('active',section.id===page));
  document.querySelectorAll('.nav-link[data-section]').forEach(link=>{const selected=link.dataset.section===page;link.classList.toggle('active',selected);if(selected)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
  document.body.classList.toggle('page-cover',page==='destaques');
  if(updateHistory&&location.hash!==`#${page}`)history.pushState({page},'',`#${page}`);
  requestAnimationFrame(()=>renderVisibleCharts(page));
  
  // ao trocar de aba, sobe apenas até o menu de paginação (a capa fica de fora)
  const navTop = document.querySelector('.cover')?.offsetHeight || 0;
  if (updateHistory && window.scrollY > navTop) window.scrollTo({ top: navTop, behavior: 'smooth' });
  requestAnimationFrame(() => updateNavStuck());
}

document.querySelectorAll('a[href^="#"]').forEach(link=>link.addEventListener('click',event=>{const page=link.getAttribute('href').slice(1);if(pageIds.includes(page)){event.preventDefault();navigateToPage(page);}}));
window.addEventListener('popstate',()=>navigateToPage(location.hash.slice(1),false));
let chartResizeFrame=0;
window.addEventListener('resize',()=>{if(chartResizeFrame)return;chartResizeFrame=requestAnimationFrame(()=>{chartResizeFrame=0;renderVisibleCharts(document.querySelector('main .section.active')?.id);});});

const navEl=document.querySelector('.main-nav');
const setNavH=()=>document.documentElement.style.setProperty('--nav-h',`${navEl.offsetHeight}px`);
// barra de navegação escura enquanto fixa no topo (página rolada)
const subNavEl=document.querySelector('.proposal-subnav');
const updateNavStuck=()=>{
  navEl.classList.toggle('is-stuck',navEl.getBoundingClientRect().top<=0.5&&window.scrollY>0);
  // submenu de propostas: escuro (igual ao menu principal) quando está fixo sob ele
  if(subNavEl)subNavEl.classList.toggle('is-stuck',subNavEl.offsetParent!==null&&window.scrollY>0&&subNavEl.getBoundingClientRect().top<=navEl.offsetHeight+1);
};
window.addEventListener('scroll',updateNavStuck,{passive:true});
updateNavStuck();
setNavH();
if(window.ResizeObserver)new ResizeObserver(setNavH).observe(navEl);else window.addEventListener('resize',setNavH);

loadReport();
navigateToPage(location.hash.slice(1)||'destaques',false);