// Luzia · painel local. Jogo (docs/luzia-ux.md): feixes valem lúmens; lúmens enchem os degraus de cada skill;
// os degraus formam a rota até Plena. Luz própria (laranja) = você demonstrou; luz refletida (lilás) = o agente aplicou.
// Dados: /api/estado e /api/sessao. Ícones próprios em SVG, sem emoji.
const I = {
  hoje: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  rota: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/>',
  feixes: '<path d="M4 20L20 4M9 20l11-11M4 15L15 4"/>',
  propria: '<path d="M12 2.5l2.2 6.8h7.1l-5.7 4.2 2.2 6.8L12 16.1l-5.8 4.2 2.2-6.8-5.7-4.2h7.1z"/>',
  ajustes: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  explicar: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/><path d="M9 11h6M9 14h4"/>',
  praticar: '<path d="M8 8l-5 4 5 4M16 8l5 4-5 4M14 5l-4 14"/>',
  estudar: '<path d="M4 5a2 2 0 0 1 2-2h5v17H6a2 2 0 0 0-2 2zM20 5a2 2 0 0 0-2-2h-5v17h5a2 2 0 0 1 2 2z"/>',
  explorar: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
  copiar: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  olho: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  raio: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  pacote: '<path d="M21 8l-9-5-9 5 9 5 9-5zM3 8v8l9 5 9-5V8M12 13v8"/>',
  alerta: '<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.01"/>',
  seta: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  enviar: '<path d="M4 12l16-8-6 16-3-7z"/>',
  fechar: '<path d="M6 6l12 12M18 6L6 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
  agente: '<rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 13h.01M15 13h.01"/>',
  subir: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  descartar: '<path d="M5 7h14M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  restaurar: '<path d="M4 12a8 8 0 1 0 2.3-5.7M4 4v4h4"/>',
  lumen: '<circle cx="12" cy="12" r="3.5"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2"/>',
};
const ic = (n, c = '') => `<svg class="ic ${c}" viewBox="0 0 24 24" aria-hidden="true">${I[n] || ''}</svg>`;

const TELAS = [['hoje', 'Hoje'], ['rota', 'Rota'], ['feixes', 'Feixes'], ['propria', 'Luz própria'], ['ajustes', 'Ajustes']];
const ESTADO = { sugerido: 'sugerido', na_fila: 'na fila', em_andamento: 'em andamento', conquistado: 'conquistado', descartado: 'descartado' };
const MODOS = {
  ativo: ['raio', 'Ativa e observando', 'Reconhece o que você aplica e avisa no chat.'],
  passivo: ['olho', 'Só observando', 'Reconhece e soma lúmens, sem interromper.'],
  sob_demanda: ['chat', 'Só quando chamada', 'Não observa a sessão.'],
};
const AGENTES = {
  'claude-code': ['Claude Code', 'Fila, comandos /luzia:*, sessão nova e observador automático.'],
  codex: ['Codex', 'Fila e comandos pelas regras do AGENTS.md.'],
  cursor: ['Cursor', 'Fila e comandos pelas User Rules.'],
  antigravity: ['Antigravity', 'Fila e comandos pelas regras do GEMINI.md.'],
  outro: ['Outro agente', 'Qualquer agente que rode comandos no terminal.'],
};
let E = null;
let filtro = 'abertos';

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const feixe = (id) => E.acoes.find((a) => a.id === id);
const nomeAgente = () => AGENTES[E.agente]?.[0] || 'seu agente';
const curto = (s) => esc(String(s || '').split('(')[0].trim());

async function api(caminho, dados) {
  const r = await fetch(caminho, dados ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) } : {});
  return r.json();
}

function toast(texto) {
  const el = $('#toast');
  el.innerHTML = ic('check') + esc(texto); el.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (el.hidden = true), 2800);
}

// ------------------------------------------------------------------ peças
function cartaoFeixe(a) {
  const tipoIc = a.estado === 'conquistado' ? 'check' : (I[a.tipo] ? a.tipo : 'feixes');
  const valor = a.estado === 'conquistado' ? `+${a.lm_ganho} lm` : `${a.valor_lm} lm`;
  return `<button class="acao ${a.estado}" data-feixe="${a.id}">
    <span class="tipo">${ic(tipoIc, 'p')}${esc(a.tipo)} · ${curto(a.skill_plano || a.skill)}<span class="lm valor">${ic('lumen', 'p')}${valor}</span></span>
    <b>${esc(a.titulo)}</b>
    <span class="pe">${ic('relogio', 'p')}${a.duracao_min || '?'} min · <span class="estado">${ESTADO[a.estado] || ''}</span>${a.tentativas && a.estado !== 'conquistado' ? ` · tentativa ${a.tentativas + 1}` : ''}<span class="seta">${ic('seta', 'p')}</span></span>
  </button>`;
}

function botoesFeixe(a) {
  if (a.estado === 'descartado') {
    return `<div class="acoes-bt"><button class="btn sec" data-restaurar="${a.id}">${ic('restaurar')}Restaurar</button></div>`;
  }
  if (a.estado === 'conquistado') {
    const pode = [2, 3].includes(a.nota) && !a.revisitas;
    return pode ? `<div class="acoes-bt"><button class="btn prim" data-enviar="${a.id}">${ic('enviar')}Revisitar com ${esc(nomeAgente())}</button></div>
      <p class="dica">Uma revisita para buscar o restante: você levou ${a.lm_ganho} de ${a.valor_lm} lm.</p>` : '';
  }
  const naFila = a.estado === 'na_fila';
  return `<div class="acoes-bt">
    <button class="btn prim" data-enviar="${a.id}" ${naFila ? 'disabled' : ''}>${ic(naFila ? 'check' : 'enviar')}${naFila ? 'Enviado ao ' + esc(nomeAgente()) : 'Enviar para ' + esc(nomeAgente())}</button>
    <button class="btn sec" data-copiar="${a.id}">${ic('copiar')}Copiar prompt</button>
  </div>
  <p class="dica">${naFila ? `Na próxima mensagem no ${esc(nomeAgente())}, a Luzia oferece abrir este feixe numa sessão nova ou ali mesmo.`
    : `Vai para a fila: na sua próxima mensagem no ${esc(nomeAgente())}, a Luzia oferece começar.${E.agente === 'claude-code' ? ` Ou digite <b>/luzia:fazer ${a.id}</b>.` : ''}`}</p>`;
}

function motivoValor(a) {
  const prio = (a.conta || []).find((c) => c[0] === 'prioridade');
  const lac = (a.conta || []).find((c) => c[0] === 'lacuna');
  const skill = curto(a.skill_plano || a.skill);
  if (prio && prio[2] === 10) return `Vale mais porque ${skill} é uma das suas maiores lacunas (${esc(lac?.[1] || '')}).`;
  if (prio && prio[2] === 0) return `Vale menos porque ${skill} já está na sua meta.`;
  return `Feixe de ${skill}, uma lacuna do seu plano (${esc(lac?.[1] || '')}).`;
}

function abrirFeixe(id) {
  const a = feixe(id);
  if (!a) return;
  const conta = (a.conta || []).map(([r, d, v]) => `<span>${esc(r)} <small>(${esc(d)})</small></span><b>+${v}</b>`).join('');
  const hist = (a.historico || []).slice(-5).reverse().map((h) => `<li>${esc(h.quando.slice(0, 10))} · ${esc(h.evento)}${h.nota != null ? ` · nota ${h.nota}/4` : ''}${h.lm ? ` · +${h.lm} lm` : ''}${h.motivo ? ` · ${esc(h.motivo)}` : ''}${h.onde ? ` · ${esc(h.onde)}` : ''}</li>`).join('');
  const motivos = Object.entries(E.regras.motivos).map(([k, v]) => `<button class="tag" data-descartar="${a.id}" data-motivo="${k}">${esc(v)}</button>`).join('');
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <div class="etiquetas"><span class="tag luz">${ic(I[a.tipo] ? a.tipo : 'feixes', 'p')}${esc(a.tipo)}</span><span class="tag">${curto(a.skill_plano || a.skill)}</span>
      <span class="tag">${ic('relogio', 'p')}${a.duracao_min} min</span><span class="tag">${esc(ESTADO[a.estado])}</span></div>
    <h3>${esc(a.titulo)}</h3>
    <p>${esc(a.por_que)}</p>
    ${a.entrega ? `<div class="risco">${ic('pacote', 'p')}${esc(a.entrega)}${a.dimensao ? ` · acende ${a.dimensao}` : ''}</div>` : ''}
    <h4>Vale ${a.valor_lm} lm</h4>
    <p class="lacuna">${motivoValor(a)} Explicando bem, você leva tudo; explicando em parte, leva uma parte.</p>
    <details class="calculo"><summary>${ic('info', 'p')} Como chegamos a ${a.valor_lm} lm</summary>
      <div class="conta">${conta}<span class="total">sua explicação: 4 = 100% · 3 = 75% · 2 = 50%</span><b class="total">${a.valor_lm} lm</b></div></details>
    <h4>Como</h4><ol>${(a.como || []).map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
    <h4>Conceitos</h4><div class="etiquetas">${(a.conceitos || []).map((c) => `<span class="tag">${esc(c)}</span>`).join('')}</div>
    <h4>Onde explorar no repositório</h4><p class="lacuna">${esc(a.onde_explorar)}</p>
    <h4>&nbsp;</h4>${botoesFeixe(a)}
    ${hist ? `<h4>Histórico</h4><ul class="lacuna" style="padding-left:18px;margin:0">${hist}</ul>` : ''}
    ${['conquistado', 'descartado'].includes(a.estado) ? '' : `<h4>Não faz sentido para você?</h4><div class="motivos">${motivos}</div>`}
    <h4>Prompt que vai para o seu agente</h4><pre class="prompt">${esc(a.prompt_completo)}</pre>`;
  $('#gaveta').hidden = false;
}

function abrirSkill(nome) {
  const s = E.skills.find((x) => x.nome === nome);
  if (!s) return;
  const d = E.perfil.diagnostico || {};
  const doSkill = E.acoes.filter((a) => (a.skill_plano || a.skill) === nome && a.estado !== 'descartado');
  const graus = (s.degraus || []).map((h) => `<li>${esc(h.quando.slice(0, 10))} · subiu para ${h.para} (${h.lm} lm, ${h.luz_propria}% luz própria)</li>`).join('');
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <span class="sobre">Skill</span><h3>${esc(nome)}</h3>
    <p>${escala(s, false)}</p>
    <p class="frase-nivel">${s.autoavaliada
      ? `Hoje você está no <b>nível ${s.nivel ?? s.voce}</b> de 5. Sua meta para Plena é o <b>nível ${s.alvo}</b>.`
      : `A Luzia estima o <b>nível ${s.nivel ?? s.voce}</b> de 5 pelo que viu na triagem. Sua meta para Plena é o <b>nível ${s.alvo}</b>. <button class="btn link" data-ir="ajustes">Declare o seu nível</button>: a rota parte dele, não da estimativa.`}
      ${s.autoavaliada && Number(s.sugere) !== Number(s.nivel ?? s.voce) ? `<br><small>Pelas evidências, a Luzia estimaria o nível ${s.sugere} (losango lilás). Quem decide é você.</small>` : ''}</p>
    <h4>Próximo degrau</h4>${barraDegrau(s)}
    <h4>O que a Luzia viu na triagem</h4><p class="lacuna">${esc(s.evidencia)}</p>
    ${d.conflito_curriculo_vs_realidade ? `<p class="lacuna"><b>Currículo × prática:</b> ${esc(d.conflito_curriculo_vs_realidade)}</p>` : ''}
    ${d.padrao_uso_ia_observado ? `<p class="lacuna"><b>Como você usa IA:</b> ${esc(d.padrao_uso_ia_observado)}</p>` : ''}
    ${graus ? `<h4>Degraus subidos</h4><ul class="lacuna" style="padding-left:18px">${graus}</ul>` : ''}
    <h4>Feixes desta skill</h4><div class="acoes">${doSkill.map(cartaoFeixe).join('') || '<span class="vazio">Nenhum feixe ainda.</span>'}</div>`;
  $('#gaveta').hidden = false;
}

function escala(s, legenda = true) {
  const nivel = Number(s.nivel ?? s.voce ?? 0), meta = Number(s.alvo ?? s.meta ?? 0), sug = Number(s.sugere ?? nivel);
  let dots = '';
  for (let k = 1; k <= 5; k++) dots += `<i class="${k <= nivel ? 'voce' : ''} ${k === meta ? 'meta' : ''} ${k === sug && sug !== nivel ? 'sug' : ''}" title="nível ${k}"></i>`;
  return `<span class="escala" aria-label="nível ${nivel} de 5, meta ${meta}">${dots}</span>${legenda ? `<span class="escala-legenda">nível ${nivel} de 5 · meta ${meta}</span>` : ''}`;
}

function barraDegrau(s) {
  if (s.na_meta) return `<div class="info"><span>${ic('check', 'p')} na meta</span></div>`;
  const lim = s.limiar || E.regras.limiar;
  const p = Math.min(100, (100 * (s.propria || 0)) / lim), r = Math.min(100 - p, (100 * (s.refletida || 0)) / lim);
  return `<div class="degrau"><span class="p" style="width:${p}%"></span><span class="r" style="width:${r}%"></span></div>
    <div class="info"><span>${s.lm || 0} / ${lim} lm · ${s.luz_propria || 0}% luz própria (mínimo ${E.regras.min_propria}%)</span><span>${s.nivel} → ${s.proximo}</span></div>`;
}

function rotaHero() {
  const r = E.rota;
  const marcos = r.marcos.map((m) => `<span class="marco ${r.degraus_feitos >= m ? 'ok' : ''}" style="left:${(100 * m) / Math.max(1, r.degraus_total)}%" title="marco: ${m} degraus"></span>`).join('');
  return `<div class="bloco rota-hero">
    <span class="sobre">Sua rota</span>
    <div class="rota-linha"><span class="luz" style="width:${Math.max(2, r.pct)}%"></span>${marcos}</div>
    <div class="rota-pontas"><span>Júnior 3</span><span>Plena</span></div>
    <div class="rota-nums">
      <div><b>${r.degraus_feitos}<small style="font-size:14px;color:var(--texto-3)"> / ${r.degraus_total}</small></b><span>degraus</span></div>
      <div><b class="lm">${r.lm_total}</b><span>lúmens</span></div>
      <div><b style="color:var(--luz-2)">${r.luz_propria}%</b><span>luz própria</span></div>
      <div><b>${E.feitas}</b><span>feixes conquistados</span></div>
    </div>
    ${prontos()}
  </div>`;
}

function prontos() {
  return E.skills.filter((s) => s.pronto && !s.na_meta).map((s) => `<div class="pronto-aviso">${ic('subir')}<span><b>${esc(s.nome)}</b> pronta para o nível ${s.proximo}: ${s.lm} lm, ${s.luz_propria}% luz própria.</span>
    <button class="btn prim mini" data-subir="${esc(s.nome)}">Subir para ${s.proximo}</button></div>`).join('');
}

// ------------------------------------------------------------------ telas
function cabecalho() {
  $('#nav').innerHTML = TELAS.map(([id, nome]) => `<button data-tela="${id}">${ic(id)}${nome}</button>`).join('');
  const ex = E.execucao || {};
  $('#telemetria').innerHTML = ex.tempo_total_s ? `${ex.tempo_total_s}s · ${ex.pico_memoria_mib} MiB<br>${ex.tokens_entrada}→${ex.tokens_saida} tok<br>${esc(ex.modelo)}<br>v ${esc(ex.versao)}` : '';
  $('#selo').innerHTML = `<span class="ponto ${E.modo}"></span>${esc(MODOS[E.modo]?.[1] || E.modo)} · ${esc(nomeAgente())}`;
}

function telaHoje() {
  const p = E.proxima;
  const outros = E.acoes.filter((a) => ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado) && (!p || a.id !== p.id)).slice(0, 6);
  $('#hoje').innerHTML = `
    ${E.autoavaliada ? '' : `<div class="aviso-topo">${ic('info')}<span>Declare seu nível em cada skill: a rota parte dele.</span><button data-ir="ajustes">Declarar agora</button></div>`}
    <div style="margin-top:var(--e5)">${rotaHero()}</div>
    <div class="hoje">
      ${p ? `<div class="bloco destaque">
        <span class="sobre">${p.estado === 'em_andamento' ? 'Feixe em andamento' : 'Próximo feixe'}</span>
        <h3>${esc(p.titulo)}</h3><p>${esc(p.por_que)}</p>
        <div class="etiquetas" style="margin-bottom:var(--e5)"><span class="tag luz">${ic('lumen', 'p')}${p.valor_lm} lm</span><span class="tag">${esc(p.tipo)}</span><span class="tag">${curto(p.skill_plano || p.skill)}</span><span class="tag">${ic('relogio', 'p')}${p.duracao_min} min</span></div>
        ${botoesFeixe(p)}
        <p style="margin:var(--e3) 0 0"><button class="btn link" data-feixe="${p.id}">Ver o feixe ${ic('seta', 'p')}</button></p>
      </div>` : `<div class="bloco destaque"><span class="sobre">Tudo em dia</span><h3>Nenhum feixe aberto.</h3><p>Peça novos com /luzia:next-level.</p></div>`}
      <div class="bloco vivo"><h4><span class="pulso"></span>Lúmens recentes</h4><div id="feed"></div></div>
    </div>
    <div class="titulo"><h2>Outros feixes abertos</h2><span>${E.ritmo.feixes_semana} por semana te leva até Plena em ~${E.ritmo.meses} meses</span></div>
    <div class="acoes">${outros.map(cartaoFeixe).join('')}</div>`;
}

function feed() {
  const el = $('#feed');
  if (!el) return;
  const fontes = { feixe: 'feixe conquistado', 'passivo-prompt': 'você dirigiu no prompt', 'passivo-refletida': 'o agente aplicou', 'passivo-conversao': 'você explicou o porquê' };
  el.innerHTML = (E.lumens || []).slice(0, 7).map((l) => `<div class="feed-lm"><span class="lm ${l.luz === 'refletida' ? 'refl' : ''}">+${l.lm}</span>
      <span>${curto(l.skill)}<br><small>${esc(fontes[l.fonte] || l.fonte)} · luz ${l.luz === 'refletida' ? 'refletida' : 'própria'}</small></span><small>${esc(l.quando.slice(11, 16))}</small></div>`).join('')
    || '<div class="vazio">Conquiste feixes ou trabalhe no seu repositório: a Luzia reconhece o que você aplica e os lúmens aparecem aqui.</div>';
}

function telaRota() {
  $('#rota').innerHTML = `
    <div class="titulo"><h2>Degraus por skill</h2><span>${E.regras.limiar} lm por degrau · mínimo ${E.regras.min_propria}% de luz própria · você confirma cada subida</span></div>
    <div class="legenda" style="margin-bottom:var(--e4)"><span><i style="background:var(--luz)"></i>luz própria (você demonstrou)</span><span><i style="background:var(--refletida)"></i>luz refletida (o agente aplicou)</span></div>
    <div class="skills">${E.skills.map((s) => `<button class="skill ${s.pronto && !s.na_meta ? 'pronta' : ''} ${s.na_meta ? 'meta-ok' : ''}" data-skill="${esc(s.nome)}">
      <span class="nome"><b>${esc(s.nome)}</b><small>${escala(s)}</small></span>
      <span>${barraDegrau(s)}</span>
      <span>${s.pronto && !s.na_meta ? `<span class="btn prim mini" data-subir="${esc(s.nome)}">${ic('subir', 'p')}Subir</span>` : ic('seta', 'p')}</span>
    </button>`).join('')}</div>
    <p class="dica">Clique numa skill para ver o que a Luzia leu na triagem, seus degraus e os feixes dela.</p>`;
}

function telaFeixes() {
  const grupos = {
    abertos: E.acoes.filter((a) => ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado)),
    conquistados: E.acoes.filter((a) => a.estado === 'conquistado'),
    descartados: E.acoes.filter((a) => a.estado === 'descartado'),
  };
  const nomes = { abertos: 'Abertos', conquistados: 'Conquistados', descartados: 'Descartados' };
  $('#feixes').innerHTML = `
    <div class="titulo"><h2>Seus feixes</h2><span>valor por esforço + lacuna + prioridade · você leva pela sua explicação</span></div>
    <div class="filtros">${Object.keys(grupos).map((k) => `<button data-filtro="${k}" class="${filtro === k ? 'ativo' : ''}">${nomes[k]} · ${grupos[k].length}</button>`).join('')}</div>
    <div class="acoes">${grupos[filtro].map(cartaoFeixe).join('') || '<span class="vazio">Nada aqui.</span>'}</div>`;
}

function telaPropria() {
  const nome = { P1: 'Direção no prompt', P2: 'Coesão do commit', P3: 'Aplicação conceitual', P4: 'Domínio arquitetural' };
  const cor = (v) => (v >= 80 ? 'var(--salvia)' : v >= 50 ? 'var(--luz)' : 'var(--terracota)');
  const anel = (v, t = 96) => {
    const r = t / 2 - 7, c = 2 * Math.PI * r, x = v ?? 0;
    return `<svg width="${t}" height="${t}"><circle cx="${t / 2}" cy="${t / 2}" r="${r}" fill="none" stroke="var(--refletida)" stroke-opacity=".25" stroke-width="6"/>
      <circle cx="${t / 2}" cy="${t / 2}" r="${r}" fill="none" stroke="var(--luz)" stroke-width="6" stroke-linecap="round" stroke-dasharray="${(c * x) / 100} ${c}"/></svg>`;
  };
  const entregas = E.entregas.map((e) => {
    const dims = Object.entries(e.dimensoes).map(([k, d]) => d
      ? `<div class="dim"><div class="cab"><span>${k} · ${nome[k]}</span><span>${esc(d.tipo)}</span></div><div class="v">${d.nota}</div>
          <div class="b"><i style="width:${d.nota}%;background:${cor(d.nota)}"></i></div><div class="base">${esc(d.base)}</div></div>`
      : `<div class="dim sem"><div class="cab"><span>${k} · ${nome[k]}</span></div><div class="v">—</div><div class="base">Ainda luz refletida. O feixe abaixo acende.</div></div>`).join('');
    return `<div class="bloco entrega">
      <div class="anel">${anel(e.indice)}<div><b>${e.indice ?? '—'}${e.indice == null ? '' : '%'}</b><small>${esc(e.base)}</small></div></div>
      <div><h3>${esc(e.tarefa)}</h3>${e.risco ? `<div class="risco">${ic('alerta', 'p')}${esc(e.risco)}</div>` : ''}
        <div class="dims">${dims}</div><div class="acoes">${e.acoes.map(feixe).filter(Boolean).map(cartaoFeixe).join('')}</div></div></div>`;
  }).join('');
  $('#propria').innerHTML = `
    <div class="titulo"><h2>Luz própria nas suas entregas</h2><span>laranja: o que é seu · lilás: o que ainda é do agente</span></div>
    <details class="medida bloco"><summary>${ic('info')}Como isso é medido</summary><ul>${E.como_e_medido.map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>
    ${entregas || '<div class="bloco vazio">Rode /luzia:feedback-progress para a Luzia ler suas entregas recentes.</div>'}`;
}

let provEscolhido = null;
function secaoModelo() {
  const m = E.modelo; const prov = provEscolhido || m.provedor; const info = m.provedores[prov];
  const atual = prov === m.provedor;
  return `<div class="titulo"><h2>Modelo da Luzia</h2><span>agora: ${esc(m.nome_provedor)} · ${esc(m.modelo)}</span></div>
    <div class="opcoes">${Object.entries(m.provedores).map(([k, v]) => `<button class="opcao ${prov === k ? 'ativo' : ''}" data-provedor="${k}">${ic('agente')}<span><b>${esc(v.nome)}</b><small>${v.chave_configurada ? 'chave configurada' : 'sem chave'}</small></span></button>`).join('')}</div>
    <div class="bloco" style="margin-top:var(--e3)">
      <div class="campos">
        <label>Modelo<input id="m-modelo" list="m-sugestoes" value="${esc(atual ? m.modelo : (info.sugestoes[0] || ''))}" placeholder="nome do modelo"></label>
        <datalist id="m-sugestoes">${info.sugestoes.map((s) => `<option value="${esc(s)}">`).join('')}</datalist>
        ${info.base_url ? `<label>Endereço da API (base_url)<input id="m-base" value="${esc(atual ? m.base_url : '')}" placeholder="ex.: https://openrouter.ai/api/v1 ou http://localhost:11434/v1"></label>` : ''}
        <label>API key<input id="m-chave" type="password" autocomplete="off" placeholder="${info.chave_configurada ? 'já configurada — deixe em branco para manter' : 'cole aqui a sua chave'}"></label>
      </div>
      <p class="dica">A chave fica só no arquivo .env desta máquina (fora do git) e nunca volta para a tela.${atual && !m.sdk_instalado ? ` Falta o SDK deste provedor: <b>pip install ${esc(m.pip)}</b>.` : ''}</p>
      <div class="acoes-bt"><button class="btn prim" id="m-salvar">${ic('check')}Salvar modelo</button><button class="btn sec" id="m-testar">${ic('raio')}Testar</button></div>
    </div>`;
}

function telaAjustes() {
  const opcao = (grupo, chave, [icone, titulo, desc], ativo) =>
    `<button class="opcao ${ativo ? 'ativo' : ''}" data-${grupo}="${chave}">${ic(icone)}<span><b>${titulo}</b><small>${desc}</small></span></button>`;
  $('#ajustes').innerHTML = `
    <div class="titulo"><h2>Seu nível hoje</h2><span>0 a 5 · a rota parte daqui e só sobe quando você confirma</span></div>
    <div class="niveis">${E.skills.map((s, i) => `<div class="bloco nivel">
      <div class="cab"><b>${esc(s.nome)}</b><span id="n${i}">${s.voce}</span></div>
      <input type="range" min="0" max="5" value="${s.voce}" data-skill-nivel="${esc(s.nome)}" data-i="${i}" aria-label="${esc(s.nome)}">
      <small>meta ${s.alvo} · Luzia sugere ${s.sugere}</small></div>`).join('')}</div>
    <p style="margin-top:var(--e4)"><button class="btn prim" id="salvar-niveis">${ic('check')}Salvar meu nível</button></p>
    ${secaoModelo()}
    <div class="titulo"><h2>Seu agente</h2><span>a Luzia funciona em qualquer um</span></div>
    <div class="opcoes">${Object.entries(AGENTES).map(([k, [t, d]]) => opcao('agente', k, ['agente', t, d], E.agente === k)).join('')}</div>
    <div class="titulo"><h2>Como a Luzia acompanha você</h2><span>o reconhecimento automático vale no Claude Code</span></div>
    <div class="opcoes">${Object.entries(MODOS).map(([k, v]) => opcao('modo', k, v, E.modo === k)).join('')}</div>`;
}

async function carregar() {
  const tela = document.querySelector('.tela.ativa')?.id || 'hoje';
  E = await api('/api/estado');
  if (E.vazio) {
    $('main').innerHTML = '<div class="bloco destaque"><span class="sobre">Olá</span><h3>Eu sou a Luzia.</h3><p>Rode a triagem no seu agente (/luzia:triage no Claude Code) para começarmos.</p></div>';
    return;
  }
  $('#jornada').innerHTML = '';
  cabecalho(); telaHoje(); telaRota(); telaFeixes(); telaPropria(); telaAjustes(); feed();
  irPara(TELAS.some(([id]) => id === tela) ? tela : 'hoje');
}

function irPara(tela) {
  document.querySelectorAll('nav button').forEach((b) => b.classList.toggle('ativo', b.dataset.tela === tela));
  document.querySelectorAll('.tela').forEach((s) => s.classList.toggle('ativa', s.id === tela));
}

// ------------------------------------------------------------------ eventos
document.addEventListener('click', async (ev) => {
  const t = ev.target.closest('[data-provedor],#m-salvar,#m-testar,[data-subir],[data-tela],[data-ir],[data-feixe],[data-skill],[data-enviar],[data-copiar],[data-descartar],[data-restaurar],[data-fechar],[data-modo],[data-agente],[data-filtro],#salvar-niveis');
  if (!t) return;
  const ds = t.dataset;
  if (ds.provedor) { provEscolhido = ds.provedor; telaAjustes(); return; }
  if (t.id === 'm-salvar') {
    const r = await api('/api/modelo', { provedor: provEscolhido || E.modelo.provedor, modelo: $('#m-modelo').value,
      base_url: $('#m-base')?.value || '', chave: $('#m-chave').value });
    toast(r.erro ? `Não salvou: ${r.erro}` : 'Modelo salvo. As próximas chamadas da Luzia usam este modelo.');
    if (!r.erro) { provEscolhido = null; carregar(); }
    return;
  }
  if (t.id === 'm-testar') {
    toast('Testando o modelo…');
    const r = await api('/api/modelo/testar', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.aviso ? `Atenção: ${r.aviso}` : `Funcionou: ${r.modelo} respondeu em ${r.segundos} s`));
    return;
  }
  if (ds.subir) {
    ev.stopPropagation();
    const r = await api('/api/subir', { skill: ds.subir });
    toast(r.erro ? r.erro : `${ds.subir.split('(')[0].trim()} subiu para o nível ${r.para}${r.marco ? ' · marco alcançado, dossiê gerado' : ''}`);
    carregar();
  } else if (ds.tela || ds.ir) { irPara(ds.tela || ds.ir); $('#gaveta').hidden = true; }
  else if (ds.feixe) abrirFeixe(ds.feixe);
  else if (ds.skill) abrirSkill(ds.skill);
  else if (ds.enviar) {
    await api('/api/enviar', { id: ds.enviar });
    toast(`Enviado. Mande qualquer mensagem no ${nomeAgente()} e a Luzia oferece começar.`);
    await carregar(); if (!$('#gaveta').hidden) abrirFeixe(ds.enviar);
  } else if (ds.copiar) {
    await navigator.clipboard.writeText(feixe(ds.copiar).prompt_completo);
    api('/api/iniciar', { id: ds.copiar }); toast(`Prompt copiado. Cole no ${nomeAgente()}.`);
  } else if (ds.descartar) {
    await api('/api/descartar', { id: ds.descartar, motivo: ds.motivo }); $('#gaveta').hidden = true;
    toast('Feixe descartado. A Luzia leva o motivo em conta.'); carregar();
  } else if (ds.restaurar) {
    await api('/api/restaurar', { id: ds.restaurar }); $('#gaveta').hidden = true; toast('Feixe restaurado.'); carregar();
  } else if (ds.fechar !== undefined) $('#gaveta').hidden = true;
  else if (ds.filtro) { filtro = ds.filtro; telaFeixes(); }
  else if (ds.modo) { await api('/api/modo', { modo: ds.modo }); toast('Modo salvo'); carregar(); }
  else if (ds.agente) { await api('/api/agente', { agente: ds.agente }); toast('Agente salvo'); carregar(); }
  else if (t.id === 'salvar-niveis') {
    const niveis = {};
    document.querySelectorAll('[data-skill-nivel]').forEach((i) => (niveis[i.dataset.skillNivel] = Number(i.value)));
    await api('/api/autoavaliacao', niveis); toast('Seu nível foi salvo'); carregar();
  }
});
document.addEventListener('input', (ev) => { if (ev.target.matches('[data-skill-nivel]')) $('#n' + ev.target.dataset.i).textContent = ev.target.value; });
document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') $('#gaveta').hidden = true; });

carregar();
setInterval(async () => { if ($('#gaveta').hidden) { E = await api('/api/estado'); if (!E.vazio) feed(); } }, 5000);
