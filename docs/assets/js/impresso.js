/* ==========================================================================
   Câmara nas Redes — Impresso (A4, 4 páginas) gerado a partir de dados_dashboard.json
   Uso: impresso.html?semana=46   (sem parâmetro: semana mais recente)
   Expõe window.impressoPronto (Promise) e window.baixarPdf() para o painel principal.
   ========================================================================== */
(function () {
  const fmtInt = new Intl.NumberFormat('pt-BR');
  const fmtCompact = new Intl.NumberFormat('pt-BR', { notation: 'compact', maximumFractionDigits: 1 });
  const MES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
  const ARTIGO = { PEC: 'a', MPV: 'a', EMC: 'a', INC: 'a', PL: 'o', PLP: 'o', PDL: 'o', PLN: 'o', PLV: 'o', PRC: 'o', RCP: 'o', REQ: 'o', RIC: 'o' };

  const INTRO = 'O Câmara nas Redes analisa, de forma clara e direta, como propostas legislativas em tramitação na Câmara dos Deputados repercutem no debate público. A partir de dados de redes sociais abertas, o relatório destaca os temas que mais mobilizam participação, as propostas com maior atenção e os argumentos mais citados, para apoiar uma leitura institucional rápida e útil do período.';
  const METODOLOGIA = [
    'Este resumo apresenta os principais sinais de participação pública sobre propostas legislativas em debate na Câmara dos Deputados, a partir de publicações abertas em redes sociais monitoradas no período.',
    'Os dados foram extraídos da plataforma Brandwatch e tratados com critérios de padronização, verificação de duplicidades, exclusão de conteúdos fora do tema e consolidação das métricas por proposta. A análise considera publicações com 5 pontos ou mais de engajamento e identifica volume de participação, temas de maior repercussão, argumentos recorrentes e posição predominante nas manifestações analisadas.',
    'A leitura dos dados contou com apoio de inteligência artificial e revisão técnica humana, para garantir clareza, consistência e fidelidade aos registros coletados. Os resultados indicam tendências do debate digital no período analisado e não representam pesquisa de opinião nem posição geral da sociedade.',
    'O relatório é produzido pela Coordenação de Relacionamento, Inteligência e Participação, responsável pela organização, análise e validação das informações apresentadas.<br>A versão digital traz o conteúdo completo, com dados detalhados, gráficos, evolução das propostas, argumentos mais citados e recortes por tema.'
  ];

  const esc = (v = '') => String(v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const int = v => (v == null ? '—' : fmtInt.format(v));
  const compact = v => (v == null ? '—' : fmtCompact.format(v));
  const pct = v => `${Number(v || 0).toLocaleString('pt-BR', { maximumFractionDigits: 1 })}%`;
  const pct1 = v => `${Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
  const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);

  /* "02/11 a 08/11/2026" -> "2 Nov a 8 Nov • 2026" */
  function periodoExtenso(period) {
    const m = String(period || '').match(/(\d{1,2})\/(\d{1,2})(?:\/\d{4})?\s*a\s*(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    return m ? `${+m[1]} ${MES[m[2] - 1]} a ${+m[3]} ${MES[m[4] - 1]} • ${m[5]}` : String(period || '');
  }
  /* 2.845.000 -> "2,8 milhões"; 425.139 -> "425 mil" */
  function emPalavras(v) {
    v = Number(v) || 0;
    if (v >= 1e9) { const n = v / 1e9; return `${n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ${n < 2 ? 'bilhão' : 'bilhões'}`; }
    if (v >= 999500) { const n = v / 1e6; return `${n.toLocaleString('pt-BR', { maximumFractionDigits: 1 })} ${n < 2 ? 'milhão' : 'milhões'}`; }
    if (v >= 1000) return `${Math.round(v / 1000)} mil`;
    return fmtInt.format(v);
  }
  /* 117.899.704 -> "117 milhões" (arredondado para baixo: "ultrapassou") */
  function piso(v) {
    v = Number(v) || 0;
    if (v >= 1e9) { const n = Math.floor(v / 1e8) / 10; return `${n.toLocaleString('pt-BR')} ${n < 2 ? 'bilhão' : 'bilhões'}`; }
    if (v >= 1e6) { const n = Math.floor(v / 1e6); return `${n} ${n < 2 ? 'milhão' : 'milhões'}`; }
    if (v >= 1000) return `${Math.floor(v / 1000)} mil`;
    return fmtInt.format(v);
  }
  const nomeComArtigo = id => { const t = String(id).split(' ')[0].toUpperCase(); return ARTIGO[t] ? `${ARTIGO[t]} ${id}` : `a proposição ${id}`; };
  const descMinuscula = d => { const s = String(d || '').trim().replace(/\.+$/, ''); return s ? s.charAt(0).toLowerCase() + s.slice(1) : ''; };
  const primeiraFrase = t => { const m = String(t || '').trim().match(/^.+?[.!?](\s|$)/); return m ? m[0].trim() : String(t || '').trim(); };
  const kpi = (r, prefixo) => (r.kpis || []).find(k => norm(k.label).startsWith(prefixo)) || {};

  /* ---------- textos gerados a partir dos dados ---------- */
  function textoEvolucao(r, payload, semana) {
    const eng = kpi(r, 'ENGAJAMENTO'), posts = kpi(r, 'POSTAGE'), reach = kpi(r, 'ALCANCE');
    if (eng.value == null) return esc(r.summary || '');
    const partes = [];
    if (eng.change != null) partes.push(eng.change === 0 ? 'resultado igual à semana anterior' : `resultado ${pct(Math.abs(eng.change))} ${eng.change < 0 ? 'inferior' : 'superior'} à semana anterior`);
    const mediana = r.median;
    if (mediana) partes.push(`${eng.value >= mediana ? 'superior' : 'inferior'} à mediana anual`);
    let t = `O engajamento total chegou a ${emPalavras(eng.value)}${partes.length ? ` — ${partes.join(' e ')}` : ''}`;
    const anual = (payload.evolucao_anual || []).filter(v => Number(v.week) <= Number(semana)).map(v => Number(v.value) || 0).sort((a, b) => b - a);
    if (anual.length >= 4 && eng.value >= anual[Math.max(0, Math.ceil(anual.length * 0.25) - 1)]) t += ', o que coloca este período entre os mais ativos do ano';
    t += '.';
    if (reach.value != null) t += ` O alcance estimado ${reach.value >= 1000 ? 'ultrapassou' : 'chegou a'} ${piso(reach.value)}${posts.value != null ? `, com ${int(posts.value)} postagens registradas` : ''}.`;
    return esc(t);
  }

  function textoPanorama(lista) {
    const frases = lista.map((p, i) => {
      const nome = nomeComArtigo(p.id), d = descMinuscula(p.description);
      const que = d ? `, que ${d},` : '';
      const n = `${emPalavras(p.engagement)} interações`;
      if (i === 0) {
        const extra = primeiraFrase(p.mobilization);
        return `${cap(nome)}${que} liderou o debate com ${n}.${extra && extra.length <= 240 ? ` ${extra}` : ''}`;
      }
      if (i === lista.length - 1 && lista.length > 2) return `Com menor repercussão entre as ${lista.length}, ${nome}${que} registrou ${n}.`;
      if (i === 1) return `Em seguida, ${nome}${que} reuniu ${n} (${pct(p.share)} do total da semana).`;
      if (i === 2) return `${cap(nome)}${que} somou ${n}.`;
      return `Já ${nome}${que} registrou ${n}.`;
    });
    return esc(frases.join(' '));
  }

  /* ---------- blocos de layout ---------- */
  const ARTE = `<svg class="pg-art" viewBox="0 0 794 113" preserveAspectRatio="none" aria-hidden="true">
    <defs>
      <linearGradient id="torre" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity=".05"/></linearGradient>
      <linearGradient id="cupula" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".02"/><stop offset=".55" stop-color="#fff" stop-opacity=".14"/><stop offset="1" stop-color="#fff" stop-opacity=".03"/></linearGradient>
    </defs>
    <rect x="420" y="0" width="22" height="104" fill="url(#torre)"/><rect x="442" y="6" width="4" height="98" fill="#000" opacity=".18"/>
    <rect x="452" y="0" width="38" height="104" fill="url(#torre)"/><rect x="452" y="0" width="7" height="104" fill="#fff" opacity=".07"/>
    <ellipse cx="455" cy="128" rx="168" ry="30" fill="url(#cupula)"/>
  </svg>`;

  function cabecalho(ctx) {
    return `<header class="pg-head">${ARTE}
      <div class="brand">
        <h1>CÂMARA NAS REDES</h1>
        <p class="brand-sem">${esc(ctx.semana)}ª Semana | ${esc(ctx.periodo)}</p>
        <p class="brand-ed">1ª Edição</p>
      </div>
      <div class="qr-area">
        <p>Acesse o relatório<br>completo pelo<br><b>QR Code</b> ao lado.</p>
        <span class="qr-seta"><svg viewBox="0 0 30 8" aria-hidden="true"><path d="M1 4h27M24.5 1 28 4l-3.5 3"/></svg></span>
      </div>
      <div class="qr" data-qr></div>
    </header>`;
  }
  const rodape = (n, total) => `<div class="pg-num">${n} de ${total}</div><footer class="pg-foot"><img src="assets/img/rodape-camara.png" alt="Coordenação de Relacionamento, Inteligência e Participação · Diretoria Executiva de Comunicação e Mídias Digitais · 200 anos da Câmara dos Deputados"></footer>`;
  const faixa = titulo => `<div class="faixa"><span>${titulo}</span></div>`;

  function seta(change) {
    if (change == null) return '';
    const sobe = change > 0, igual = change === 0;
    const icone = igual ? '' : `<span class="chg-ico ${sobe ? 'up' : 'down'}"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="${sobe ? 'M6 10V2.5M2.8 5.5 6 2.3l3.2 3.2' : 'M6 2v7.5M2.8 6.5 6 9.7l3.2-3.2'}"/></svg></span>`;
    return `<span class="k-foot">${icone}<b>${pct(Math.abs(change))}</b> ${igual ? 'igual' : (sobe ? 'superior' : 'inferior')} à semana anterior</span>`;
  }

  function paginaResumo(ctx, n, total) {
    const r = ctx.r, eng = kpi(r, 'ENGAJAMENTO'), posts = kpi(r, 'POSTAGE'), reach = kpi(r, 'ALCANCE');
    const cards = ctx.top.map((p, i) => {
      const [tipo, ...resto] = String(p.id).split(' ');
      return `<article class="card">
        <div class="card-top"><span class="card-n">${i + 1}</span><h3>${esc(tipo)}<br>${esc(resto.join(' '))}</h3></div>
        <p class="card-desc">${esc(p.description || '')}</p>
        <div class="card-met"><span>Engajamento</span><b class="pill">${int(p.engagement)}</b><span>(%) do total</span><b class="pill">${pct(p.share)}</b></div>
      </article>`;
    }).join('');
    return `<section class="page">${cabecalho(ctx)}
      <div class="pg-body">
        <p class="intro">${INTRO}</p>
        <div class="kpis kpis-3">
          <div class="kpi kpi-dark kpi-main"><span class="k-label">Engajamento</span><span class="k-val">${compact(eng.value)}</span>${seta(eng.change)}</div>
          <div class="kpi kpi-dark"><span class="k-label">Postagens</span><span class="k-val k-val-reg">${int(posts.value)}</span></div>
          <div class="kpi kpi-dark"><span class="k-label">Alcance estimado</span><span class="k-val k-val-reg">${int(reach.value)}</span></div>
        </div>
        ${faixa('Evolução')}
        <p class="texto texto-linha">${textoEvolucao(r, ctx.payload, ctx.semana)}</p>
        <div class="cards cards-${ctx.top.length}">${cards}</div>
        ${faixa('Panorama')}
        <p class="texto texto-linha">${textoPanorama(ctx.top)}</p>
      </div>${rodape(n, total)}</section>`;
  }

  function blocoProposta(p) {
    const a = p.analysis || {};
    const analisadas = a.comments ? `${int(a.posts || 0)} Posts e ${int(a.comments)} Comentários Analisados` : (a.posts ? `${int(a.posts)} Postagens Analisadas` : '');
    const args = [...(p.arguments || [])].sort((x, y) => (y.share || 0) - (x.share || 0)).slice(0, 3);
    const linhas = args.map(g => `<span class="arg-nome">${esc(g.name)}</span><span class="arg-barra"><i style="width:${Math.min(Math.max((g.share || 0) * 4.5, 3), 270).toFixed(1)}px"></i><em>${pct1(g.share)}</em></span>`).join('');
    return `<section class="prop">
      <div class="faixa faixa-prop"><span><b>${esc(p.id)}</b><i class="sep"></i>${esc(p.description || '')}</span></div>
      <div class="kpis kpis-4">
        <div class="kpi kpi-dark kpi-main"><span class="k-label">Engajamento</span><span class="k-val">${compact(p.engagement)}</span><span class="k-foot"><b>${pct(p.share)}</b>&nbsp;do total da semana</span></div>
        <div class="kpi kpi-light"><span class="k-label">Postagens</span><span class="k-val">${int(p.posts)}</span></div>
        <div class="kpi kpi-light"><span class="k-label">Autores das postagens</span><span class="k-val">${int(p.authors)}</span></div>
        <div class="kpi kpi-light"><span class="k-label">Alcance estimado</span><span class="k-val">${int(p.reach)}</span></div>
      </div>
      ${p.mobilization ? `<div class="aba">Contexto</div><p class="texto texto-linha texto-just">${esc(p.mobilization)}</p>` : ''}
      ${args.length ? `<div class="args"><div class="args-head"><b>Principais Argumentos</b><i class="sep"></i>${esc(analisadas)}</div><div class="args-body">${linhas}</div></div>` : ''}
    </section>`;
  }

  function paginaPropostas(ctx, lista, n, total, comMetodologia) {
    return `<section class="page">${cabecalho(ctx)}
      <div class="pg-body pg-body-props">
        ${lista.map(blocoProposta).join('')}
        ${comMetodologia ? blocoMetodologia() : ''}
      </div>${rodape(n, total)}</section>`;
  }
  const blocoMetodologia = () => `<section class="metodo">${faixa('Metodologia')}<div class="metodo-box">${METODOLOGIA.map(t => `<p>${t}</p>`).join('')}</div></section>`;

  /* ---------- montagem ---------- */
  async function montar() {
    const root = document.getElementById('impresso');
    const resp = await fetch(`dados/dados_dashboard.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!resp.ok) throw new Error('Não foi possível carregar os dados.');
    const payload = await resp.json();
    const multi = !!(payload.dados_semanas && payload.opcoes_semanas);
    const pedida = new URLSearchParams(location.search).get('semana');
    const semana = multi ? (payload.dados_semanas[pedida] ? pedida : String(payload.semana_padrao)) : (String(payload.edition || '').match(/\d+/) || [''])[0];
    const r = multi ? payload.dados_semanas[semana] : payload;
    if (!r?.proposals?.length) throw new Error('A semana selecionada não possui dados completos.');

    const ctx = { payload, r, semana, periodo: periodoExtenso(r.period), top: r.proposals.slice(0, 5) };
    document.title = `Câmara nas Redes — ${semana}ª Semana — Impresso`;

    const grupos = [];
    for (let i = 0; i < ctx.top.length; i += 2) grupos.push(ctx.top.slice(i, i + 2));
    const metodoSozinho = !grupos.length || grupos[grupos.length - 1].length === 2;
    const total = 1 + grupos.length + (metodoSozinho ? 1 : 0);
    let html = paginaResumo(ctx, 1, total);
    grupos.forEach((g, i) => { html += paginaPropostas(ctx, g, i + 2, total, !metodoSozinho && i === grupos.length - 1); });
    if (metodoSozinho) html += `<section class="page">${cabecalho(ctx)}<div class="pg-body pg-body-props">${blocoMetodologia()}</div>${rodape(total, total)}</section>`;
    root.innerHTML = html;

    // QR Code: abre o painel completo já na semana do impresso
    const alvo = new URL(`index.html?semana=${encodeURIComponent(semana)}`, location.href).href;
    root.querySelectorAll('[data-qr]').forEach(el => {
      if (window.QRCode) new QRCode(el, { text: alvo, width: 84, height: 84, colorDark: '#000000', colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.M });
    });

    await (document.fonts ? document.fonts.ready : Promise.resolve());
    await Promise.all([...root.querySelectorAll('img')].map(img => img.complete ? null : new Promise(ok => { img.onload = img.onerror = ok; })));
    window.impressoSemana = semana;
    return semana;
  }

  window.impressoPronto = montar().catch(err => {
    document.getElementById('impresso').innerHTML = `<p class="impresso-status">${esc(err.message || 'Falha ao montar o impresso.')}</p>`;
    throw err;
  });

  /* PDF A4 (uma imagem por página, 2x de resolução) */
  window.baixarPdf = async function () {
    const semana = await window.impressoPronto;
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait', compress: true });
    const paginas = [...document.querySelectorAll('.page')];
    document.body.classList.add('capturando');
    try {
      for (let i = 0; i < paginas.length; i++) {
        const canvas = await html2canvas(paginas[i], { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false });
        if (i) pdf.addPage();
        pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, 0, 210, 297);
      }
    } finally {
      document.body.classList.remove('capturando');
    }
    pdf.save(`Camara_nas_Redes_${semana}a_Semana.pdf`);
  };
})();
