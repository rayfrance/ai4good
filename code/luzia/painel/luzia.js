// Luzia · painel local. Jogo (docs/luzia-ux.md): avanços valem lúmens; lúmens preenchem os níveis de cada prisma (skill);
// os níveis formam a trajetória até Plena. Luz própria (laranja) = você demonstrou; luz refletida (lilás) = o agente aplicou.
// Dados: /api/estado, /api/entrega, /api/avancos e /api/pedido. Ícones próprios em SVG, sem emoji.
const I = {
  hoje: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  trajetoria: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h7a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h7"/>',
  avancos: '<path d="M4 20L20 4M9 20l11-11M4 15L15 4"/>',
  entregas: '<path d="M12 2.5l2.2 6.8h7.1l-5.7 4.2 2.2 6.8L12 16.1l-5.8 4.2 2.2-6.8-5.7-4.2h7.1z"/>',
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

const TELAS = [
  ['hoje', 'Hoje'],
  ['trajetoria', 'Trajetória'],
  ['avancos', 'Avanços'],
  ['entregas', 'Entregas'],
  ['ajustes', 'Ajustes'],
];
const ESTADO = {
  sugerido: 'sugerido',
  na_fila: 'na fila',
  em_andamento: 'em andamento',
  conquistado: 'conquistado',
  descartado: 'descartado',
};
const MODOS = {
  ativo: ['raio', 'Em foco, com lampejos', 'Observa a sessão, soma lúmens e mostra lampejos no chat quando um conceito aparece.'],
  passivo: ['olho', 'Em foco, em silêncio', 'Observa a sessão e soma lúmens em silêncio, sem interromper no chat.'],
  sob_demanda: ['chat', 'Fora de foco', 'Não observa a sessão; só age quando você chama um comando.'],
};
const AGENTES = {
  'claude-code': ['Claude Code', 'Fila, comandos /luzia:*, sessão nova e foco automático.'],
  codex: ['Codex', 'Fila e comandos pelas regras do AGENTS.md.'],
  cursor: ['Cursor', 'Fila e comandos pelas User Rules.'],
  antigravity: ['Antigravity', 'Fila e comandos pelas regras do GEMINI.md.'],
  outro: ['Outro agente', 'Qualquer agente que rode comandos no terminal.'],
};
const TIPO_PEDIDO_NOME = {
  incluir: 'Incluir prisma',
  mudar_meta: 'Mudar meta',
  arquivar: 'Arquivar prisma',
  reativar: 'Reativar prisma',
};

let E = null;
let filtroEstado = 'abertos';
let filtroPrisma = 'todos';
let filtroTipo = 'todos';
let mostrarFormPedido = false;
let tipoPedidoForm = 'incluir';

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const listaAvancos = () => (E?.avancos || E?.acoes || []);
const listaPrismas = () => (E?.prismas || E?.skills || []);
const prismasAtivos = () => (E?.skills || listaPrismas().filter((p) => p.estado !== 'arquivado'));
const avancoPorId = (id) => listaAvancos().find((a) => a.id === id);
const nomeAgente = () => AGENTES[E?.agente]?.[0] || 'seu agente';
const curto = (s) => esc(String(s || '').split('(')[0].trim());
const rotuloPrisma = (s) => `Prisma ${curto(s)}`;

async function api(caminho, dados) {
  try {
    const r = await fetch(caminho, dados ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dados) } : {});
    const j = await r.json().catch(() => ({}));
    return r.ok ? j : { erro: j.erro || `erro ${r.status}` };
  } catch {
    return { erro: 'a Luzia está desligada. Rode /luzia:career-map no seu agente para ligar o painel.', offline: true };
  }
}

function toast(texto, classe = '') {
  const el = $('#toast');
  el.className = 'toast ' + classe;
  el.innerHTML = ic(classe === 'celebra' ? 'lumen' : 'check') + esc(texto);
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), classe === 'celebra' ? 4200 : 2800);
}

// ------------------------------------------------------------------ ao vivo: o painel acompanha o que acontece no agente
const FONTES = {
  avanco: 'avanço conquistado',
  'passivo-prompt': 'você dirigiu no prompt',
  'passivo-refletida': 'o agente aplicou',
  'passivo-conversao': 'lampejo convertido em luz própria',
  conversao: 'lampejo convertido em luz própria',
};
const legFonte = (f) => FONTES[f] || (f && f.startsWith('avanc') ? 'avanço conquistado' : 'avanço conquistado');
const chaveLm = (l) => `${l.quando}|${l.skill}|${l.lm}|${l.fonte}`;
const assinatura = (e) => JSON.stringify([
  (e.lumens || []).map(chaveLm),
  (e.avancos || e.acoes || []).map((a) => a.id + a.estado),
  (e.pedidos || []).map((p) => `${p.id}:${p.estado}:${(p.historico || []).length}`),
  e.trajetoria?.versao_atual,
  e.fila,
  e.modo,
  e.agente,
]);

function celebrar(novos) {
  if (!novos.length) return;
  const total = novos.reduce((s, l) => s + l.lm, 0);
  const l = novos[0];
  const propria = novos.some((x) => x.luz !== 'refletida');
  toast(`+${total} lm · Prisma ${String(l.skill).split('(')[0].trim()} · ${novos.length > 1 ? `${novos.length} reconhecimentos` : legFonte(l.fonte)}${propria ? '' : ' (luz refletida)'}`, 'celebra');
  document.querySelectorAll('.trajetoria-linha .luz, .barra-nivel .p, .barra-nivel .r').forEach((b) => {
    b.classList.remove('brilho');
    void b.offsetWidth;
    b.classList.add('brilho');
  });
}

function maiorLacuna() {
  const abertos = new Set(listaAvancos().filter((a) => ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado)).map((a) => a.skill_plano || a.skill));
  return prismasAtivos().filter((s) => !s.na_meta).sort((a, b) => (abertos.has(a.nome) - abertos.has(b.nome)) || ((b.alvo - b.nivel) - (a.alvo - a.nivel)))[0];
}

function botaoAcender(s) {
  return s ? `<button class="btn sec" data-acender="${esc(s.nome)}">${ic('raio')}Acender 3 avanços novos de Prisma ${curto(s.nome)}</button>` : '';
}

// ------------------------------------------------------------------ espectro de 5 faixas e leitura com base
function espectroPrisma(s, legenda = true) {
  const nivel = Number(s.nivel ?? s.voce ?? 0);
  const meta = Number(s.meta ?? s.alvo ?? 0);
  const sug = Number(s.sugere ?? nivel);
  let faixas = '';
  for (let k = 1; k <= 5; k++) {
    const classes = [
      'faixa',
      `f${k}`,
      k <= nivel ? 'acesa' : '',
      k === meta ? 'meta' : '',
      k === sug && sug !== nivel ? 'sug' : '',
    ].filter(Boolean).join(' ');
    faixas += `<i class="${classes}" title="faixa ${k}${k === meta ? ' (meta)' : ''}"></i>`;
  }
  return `<span class="espectro-wrap"><span class="espectro" aria-label="nível ${nivel} de 5, meta ${meta}">${faixas}</span>${legenda ? `<span class="espectro-legenda">nível ${nivel} de 5 · meta ${meta}</span>` : ''}</span>`;
}

function resumoBaseLeitura(leitura, fallbackFatos = '') {
  // Os mesmos fatos que a CLI mostra depois de "com base em" (cli.base_resumo), lidos da base guardada.
  if (leitura && leitura.base && typeof leitura.base === 'object') {
    const b = leitura.base;
    const alvo = leitura.alvo_tipo;
    if (alvo === 'prisma') {
      const lm = b.lumens || {};
      return `nível ${b.nivel ?? '?'}/${b.meta ?? '?'} · ${lm.total ?? 0} lm (${lm.propria ?? 0} de luz própria) · ${(b.avancos_conquistados || []).length} avanço(s) conquistado(s) · ${b.entregas_total ?? 0} entrega(s)`;
    }
    if (alvo === 'entrega') {
      const f = b.fatos || {};
      return `${f.commits ?? 0} commit(s) · ${f.arquivos ?? 0} arquivo(s) · ${f.linhas ?? 0} linhas · ${(b.prismas || []).length} prisma(s)`;
    }
    if (alvo === 'pedido') {
      return `pedido (${TIPO_PEDIDO_NOME[b.tipo] || b.tipo || ''} · Prisma ${b.prisma || ''}) e a trajetória atual`;
    }
  }
  return fallbackFatos || 'fatos determinísticos registrados';
}

function motivoSemLeitura(indisponivel = '') {
  if (indisponivel) return indisponivel;
  return E && E.modelo_pronto
    ? 'A Luzia ainda não tem base para uma leitura.'
    : 'Leitura indisponível: configure o modelo em Ajustes.';
}

function blocoLeitura(leitura, fallbackFatos = '', compacto = false, indisponivel = '') {
  if (!leitura || !leitura.texto || !leitura.modelo) {
    const gerar = E && E.modelo_pronto && !indisponivel
      ? `<button class="btn link mini" data-gerar-leituras="1">${ic('raio', 'p')}Gerar leituras</button>` : '';
    return `<div class="leitura-assinada indisponivel">
      <div class="leitura-cab">
        <span><b>Leitura da Luzia</b> · fatos: ${esc(fallbackFatos || 'os medidos acima')}</span>
        ${gerar}
      </div>
      <p class="leitura-texto">${esc(motivoSemLeitura(indisponivel))} Os fatos medidos continuam visíveis.</p>
    </div>`;
  }
  const resumo = esc(resumoBaseLeitura(leitura, fallbackFatos));
  const data = esc(String(leitura.criado_em || '').slice(0, 10) || 'data desconhecida');
  const modelo = esc(leitura.modelo);
  const vencida = leitura.vencida ? ` · <span class="tag luz">base mudou</span>` : '';
  const detalhesBase = !compacto && leitura.base
    ? `<details><summary>Ver fatos usados na base</summary><pre>${esc(JSON.stringify(leitura.base, null, 2))}</pre></details>`
    : '';
  return `<div class="leitura-assinada">
    <div class="leitura-cab">
      <span><b>Leitura da Luzia</b> · com base em: ${resumo} · ${modelo} · ${data}${vencida}</span>
      ${leitura.vencida ? `<button class="btn link mini" data-gerar-leituras="1">${ic('raio', 'p')}Renovar</button>` : ''}
    </div>
    <p class="leitura-texto">${esc(leitura.texto)}</p>
    ${detalhesBase}
  </div>`;
}

// ------------------------------------------------------------------ peças de avanço e prisma
function classeTipo(tipo) {
  const t = String(tipo || 'praticar').toLowerCase();
  if (['praticar', 'explicar', 'estudar', 'explorar'].includes(t)) return `tipo-${t}`;
  return 'tipo-praticar';
}

function cartaoAvanco(a) {
  const t = String(a.tipo || 'praticar').toLowerCase();
  const tipoIc = a.estado === 'conquistado' ? 'check' : (I[t] ? t : 'avancos');
  const valor = a.estado === 'conquistado' ? `+${a.lm_ganho} lm` : `${a.valor_lm} lm`;
  return `<button class="acao ${a.estado}" data-avanco="${esc(a.id)}">
    <span class="tipo">
      <span class="tipo-chip ${classeTipo(t)}">${ic(tipoIc, 'p')}${esc(t)}</span>
      <span>${rotuloPrisma(a.skill_plano || a.skill)}</span>
      <span class="lm valor">${ic('lumen', 'p')}${valor}</span>
    </span>
    <b>${esc(a.titulo)}</b>
    <span class="pe">${ic('relogio', 'p')}${a.duracao_min || '?'} min · <span class="estado">${ESTADO[a.estado] || ''}</span>${a.tentativas && a.estado !== 'conquistado' ? ` · tentativa ${a.tentativas + 1}` : ''}<span class="seta">${ic('seta', 'p')}</span></span>
  </button>`;
}

function botoesAvanco(a) {
  if (a.estado === 'descartado') {
    return `<div class="acoes-bt"><button class="btn sec" data-restaurar="${esc(a.id)}">${ic('restaurar')}Restaurar</button></div>`;
  }
  const naFila = (E.fila || []).includes(a.id);
  if (a.estado === 'conquistado') {
    const pode = [2, 3].includes(a.nota) && !a.revisitas;
    return pode ? `<div class="acoes-bt"><button class="btn prim" data-enviar="${esc(a.id)}" ${naFila ? 'disabled' : ''}>${ic(naFila ? 'check' : 'enviar')}${naFila ? 'Revisita enviada ao ' : 'Revisitar com '}${esc(nomeAgente())}</button></div>
      <p class="dica">Uma revisita para buscar o restante: você levou ${a.lm_ganho} de ${a.valor_lm} lm. O que já ganhou não conta de novo.</p>` : '';
  }
  return `<div class="acoes-bt">
    <button class="btn prim" data-enviar="${esc(a.id)}" ${naFila ? 'disabled' : ''}>${ic(naFila ? 'check' : 'enviar')}${naFila ? 'Enviado ao ' + esc(nomeAgente()) : (a.estado === 'em_andamento' ? 'Continuar no ' : 'Enviar para ') + esc(nomeAgente())}</button>
    <button class="btn sec" data-copiar="${esc(a.id)}">${ic('copiar')}Copiar prompt</button>
  </div>
  <p class="dica">${naFila ? `Na próxima mensagem no ${esc(nomeAgente())}, a Luzia oferece abrir este avanço numa sessão nova ou ali mesmo.`
    : `Vai para a fila: na sua próxima mensagem no ${esc(nomeAgente())}, a Luzia oferece começar.${E.agente === 'claude-code' ? ` Ou digite <b>/luzia:fazer ${esc(a.id)}</b>.` : ''}`}</p>`;
}

function motivoValor(a) {
  const prio = (a.conta || []).find((c) => c[0] === 'prioridade');
  const lac = (a.conta || []).find((c) => c[0] === 'lacuna');
  const nomeP = rotuloPrisma(a.skill_plano || a.skill);
  if (prio && prio[2] === 10) return `Vale mais porque ${nomeP} é uma das suas maiores lacunas (${esc(lac?.[1] || '')}).`;
  if (prio && prio[2] === 0) return `Vale menos porque ${nomeP} já está na sua meta.`;
  return `Avanço de ${nomeP}, uma lacuna da sua trajetória (${esc(lac?.[1] || '')}).`;
}

function abrirAvanco(id) {
  const a = avancoPorId(id);
  if (!a) return;
  const t = String(a.tipo || 'praticar').toLowerCase();
  const conta = (a.conta || []).map(([r, d, v]) => `<span>${esc(r)} <small>(${esc(d)})</small></span><b>+${v}</b>`).join('');
  const hist = (a.historico || []).slice(-5).reverse().map((h) => `<li>${esc(h.quando.slice(0, 10))} · ${esc(h.evento)}${h.nota != null ? ` · nota ${h.nota}/4` : ''}${h.lm ? ` · +${h.lm} lm` : ''}${h.motivo ? ` · ${esc(h.motivo)}` : ''}${h.onde ? ` · ${esc(h.onde)}` : ''}</li>`).join('');
  const motivos = Object.entries(E.regras.motivos || {}).map(([k, v]) => `<button class="tag" data-descartar="${esc(a.id)}" data-motivo="${esc(k)}">${esc(v)}</button>`).join('');
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <div class="etiquetas">
      <span class="tipo-chip ${classeTipo(t)}">${ic(I[t] ? t : 'avancos', 'p')}${esc(t)}</span>
      <span class="tag">${rotuloPrisma(a.skill_plano || a.skill)}</span>
      <span class="tag">${ic('relogio', 'p')}${a.duracao_min} min</span>
      <span class="tag">${esc(ESTADO[a.estado])}</span>
    </div>
    <h3>${esc(a.titulo)}</h3>
    <p>${esc(a.por_que)}</p>
    ${a.da_triagem ? `<div class="etiquetas"><span class="tag">da triagem</span></div>` : a.entrega ? `<div class="etiquetas"><span class="tag">${ic('pacote', 'p')}${esc(a.entrega)}${a.dimensao ? ` · acende ${esc(a.dimensao)}` : ''}</span></div>` : ''}
    <h4>Vale ${a.valor_lm} lm</h4>
    <p class="lacuna">${motivoValor(a)} Explicando bem, você leva tudo; explicando em parte, leva uma parte.</p>
    <details class="calculo"><summary>${ic('info', 'p')} Como chegamos a ${a.valor_lm} lm</summary>
      <div class="conta">${conta}<span class="total">sua explicação: 4 = 100% · 3 = 75% · 2 = 50%</span><b class="total">${a.valor_lm} lm</b></div></details>
    <h4>Como</h4><ol>${(a.como || []).map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
    <h4>Conceitos</h4><div class="etiquetas">${(a.conceitos || []).map((c) => `<span class="tag">${esc(c)}</span>`).join('')}</div>
    <h4>Onde explorar no repositório</h4><p class="lacuna">${esc(a.onde_explorar)}</p>
    <h4>&nbsp;</h4>${botoesAvanco(a)}
    ${hist ? `<h4>Histórico</h4><ul class="lacuna" style="padding-left:18px;margin:0">${hist}</ul>` : ''}
    ${['conquistado', 'descartado'].includes(a.estado) ? '' : `<h4>Não faz sentido para você?</h4><div class="motivos">${motivos}</div>`}
    <h4>Prompt que vai para o seu agente</h4><pre class="prompt">${esc(a.prompt_completo)}</pre>`;
  $('#gaveta').hidden = false;
}

function abrirPrisma(nome) {
  const s = listaPrismas().find((x) => x.nome === nome);
  if (!s) return;
  const doPrisma = listaAvancos().filter((a) => (a.skill_plano || a.skill) === nome && a.estado !== 'descartado');
  const subidas = (s.niveis_conquistados || []).map((h) => `<li>${esc(h.quando.slice(0, 10))} · subiu para o nível ${h.para} (${h.lm} lm, ${h.luz_propria}% luz própria)</li>`).join('');
  const fatosPrisma = `nível ${s.nivel}/${s.meta ?? s.alvo} · ${s.lm || 0} lm no nível atual (${s.luz_propria || 0}% luz própria) · ${doPrisma.length} avanço(s)`;
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <span class="sobre">Prisma (skill) · ${s.estado === 'arquivado' ? 'arquivado' : 'ativo na trajetória'}</span>
    <h3>Prisma ${esc(nome)}</h3>
    <p>${espectroPrisma(s, false)}</p>
    <p class="frase-nivel">${s.autoavaliada
      ? `Hoje você está no <b>nível ${s.nivel ?? s.voce}</b> de 5. Sua meta para Plena é o <b>nível ${s.meta ?? s.alvo}</b>.`
      : `A Luzia estima o <b>nível ${s.nivel ?? s.voce}</b> de 5 pelo que viu na triagem. Sua meta para Plena é o <b>nível ${s.meta ?? s.alvo}</b>. <button class="btn link" data-ir="ajustes">Declare o seu nível</button>: a trajetória parte dele, não da estimativa.`}
      ${s.autoavaliada && Number(s.sugere) !== Number(s.nivel ?? s.voce) ? `<br><small>Pelas evidências, a Luzia estimaria o nível ${s.sugere} (losango lilás). Quem decide é você.</small>` : ''}</p>
    <h4>Progresso até o próximo nível</h4>${barraNivel(s)}
    <h4>Leitura personalizada deste prisma</h4>
    ${blocoLeitura(s.leitura, fatosPrisma, false)}
    ${s.evidencia ? `<h4>Evidência inicial da triagem</h4>${blocoLeitura({ texto: s.evidencia, alvo_tipo: 'triagem', modelo: E.triagem_modelo?.modelo || 'modelo desconhecido', criado_em: E.triagem_modelo?.quando || '' }, 'triagem: currículo, commits e histórico autorizados (anonimizados)', true)}` : ''}
    ${subidas ? `<h4>Níveis conquistados</h4><ul class="lacuna" style="padding-left:18px">${subidas}</ul>` : ''}
    <h4>Avanços deste prisma</h4><div class="acoes">${doPrisma.map(cartaoAvanco).join('') || '<span class="vazio">Nenhum avanço aberto ainda.</span>'}</div>
    ${s.na_meta || s.estado === 'arquivado' ? '' : `<p style="margin-top:var(--e4)">${botaoAcender(s)}</p>`}`;
  $('#gaveta').hidden = false;
}

async function abrirEntregaDetalhe(id) {
  const det = await api(`/api/entrega?id=${encodeURIComponent(id)}`);
  if (det.erro) {
    toast(det.erro);
    return;
  }
  const f = det.fatos || {};
  const prismasTags = (det.prismas || []).map((p) => {
    const termos = (p.termos || []).length ? ` (${p.termos.map(esc).join(', ')})` : '';
    return `<span class="tag refl">Prisma ${curto(p.prisma)}${termos}</span>`;
  }).join('') || '<span class="vazio">Nenhum prisma detectado nos caminhos ou mensagens.</span>';
  const lms = (det.lumens_ligados || []).map((l) =>
    `<li><b>+${l.lm} lm</b> (${l.luz === 'refletida' ? 'luz refletida' : 'luz própria'}) · Prisma ${curto(l.prisma || l.skill)} · ${esc(legFonte(l.fonte))} · ${esc(String(l.quando || '').slice(0, 10))}</li>`
  ).join('');
  const feitos = (det.avancos_feitos || []).map(cartaoAvanco).join('');
  const uteis = (det.avancos_uteis || []).map(cartaoAvanco).join('');
  const resumoFatos = `${f.commits ?? 1} commit(s) · ${f.arquivos ?? 0} arquivo(s) · +${f.linhas ?? 0} linhas · ${f.duracao_dias ?? 1} dia(s)`;

  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <span class="sobre">Entrega detectada (${esc(det.fonte || 'git')})</span>
    <h3>${esc(det.titulo)}</h3>
    <div class="fatos-entrega">
      <span class="tag">${esc(String(f.inicio || '').slice(0, 10) || '—')} → ${esc(String(f.fim || '').slice(0, 10) || '—')} (${f.duracao_dias || 1}d)</span>
      <span class="tag">${f.commits || 1} commit(s)</span>
      <span class="tag">${f.arquivos || 0} arquivo(s)</span>
      <span class="tag">+${f.linhas || 0} linhas</span>
      ${(f.areas || []).map((ar) => `<span class="tag">${esc(ar)}</span>`).join('')}
    </div>
    <h4>Prismas (skills) atravessados</h4>
    <div class="prismas-entrega">${prismasTags}</div>
    ${botaoAcenderEntrega(det.id, (det.propriedade || {}).dimensoes, det.avancos_feitos)}
    <h4>Leitura da Luzia sobre esta entrega</h4>
    ${blocoLeitura(det.leitura, resumoFatos, false)}
    <h4>Lúmens ligados no período (${(det.lumens_ligados || []).length})</h4>
    ${lms ? `<ul class="lacuna" style="padding-left:18px">${lms}</ul>` : '<p class="vazio">Nenhum lúmen registrado na janela desta entrega.</p>'}
    ${feitos ? `<h4>Avanços concluídos para esta entrega</h4><div class="acoes">${feitos}</div>` : ''}
    <h4>Avanços úteis dos mesmos prismas</h4>
    <div class="acoes">${uteis || '<span class="vazio">Nenhum avanço aberto para os prismas desta entrega.</span>'}</div>`;
  $('#gaveta').hidden = false;
}

// P3/P4 sem evidência e sem avanço aberto que as acenda: oferece acender 2 avanços ligados a esta entrega.
function botaoAcenderEntrega(id, dimensoes, feitos) {
  const lacunas = ['P3', 'P4'].filter((d) => !(dimensoes || {})[d]);
  const abertas = new Set((feitos || []).filter((a) => a && ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado))
    .map((a) => a.dimensao));
  if (!id || !lacunas.length || lacunas.every((d) => abertas.has(d))) return '';
  return `<button class="btn prim mini" data-acender-entrega="${id}">${ic('raio', 'p')}Acender avanços para esta entrega (${lacunas.join(' e ')})</button>`;
}

function barraNivel(s) {
  if (s.na_meta) return `<div class="info"><span>${ic('check', 'p')} na meta (nível ${s.nivel} de ${s.meta ?? s.alvo})</span></div>`;
  const lim = s.limiar || E.regras.limiar;
  const p = Math.min(100, (100 * (s.propria || 0)) / lim);
  const r = Math.min(100 - p, (100 * (s.refletida || 0)) / lim);
  const qtdAvancos = s.avancos_conquistados ?? 0;
  const minAvancos = E.regras.min_avancos || 1;
  const avancoOk = qtdAvancos >= minAvancos;
  return `<div class="barra-nivel"><span class="p" style="width:${p}%"></span><span class="r" style="width:${r}%"></span></div>
    <div class="info"><span>${s.lm || 0} / ${lim} lm · ${s.luz_propria || 0}% luz própria (mínimo ${E.regras.min_propria}%) · ${avancoOk ? `${qtdAvancos} avanço${qtdAvancos > 1 ? 's' : ''} conquistado${qtdAvancos > 1 ? 's' : ''}` : 'falta conquistar 1 avanço'}</span><span>nível ${s.nivel} → ${s.proximo}</span></div>`;
}

function trajetoriaHero() {
  const r = E.trajetoria?.resumo || E.rota || {};
  const total = r.niveis_total ?? 0;
  const feitos = r.niveis_feitos ?? 0;
  const versao = E.trajetoria?.versao_atual || 1;
  const marcos = (r.marcos || []).map((m) => `<span class="marco ${feitos >= m ? 'ok' : ''}" style="left:${(100 * m) / Math.max(1, total)}%" title="marco: ${m} níveis"></span>`).join('');
  return `<div class="bloco trajetoria-hero">
    <span class="sobre">Sua trajetória · versão v${versao}</span>
    <div class="trajetoria-linha"><span class="luz" style="width:${Math.max(2, r.pct || 0)}%"></span>${marcos}</div>
    <div class="trajetoria-pontas"><span>${esc(E.perfil.rotulos?.[0] || 'Hoje')}</span><span>${esc(E.perfil.rotulos?.[1] || 'Meta')}</span></div>
    <div class="trajetoria-nums">
      <div><b>${feitos}<small style="font-size:14px;color:var(--texto-3)"> / ${total}</small></b><span>níveis</span></div>
      <div><b class="lm">${r.lm_total || 0}</b><span>lúmens</span></div>
      <div><b style="color:var(--luz-2)">${r.luz_propria || 0}%</b><span>luz própria</span></div>
      <div><b>${E.feitas || 0}</b><span>avanços conquistados</span></div>
    </div>
    ${prontos()}
  </div>`;
}

function prontos() {
  return prismasAtivos().filter((s) => s.pronto && !s.na_meta).map((s) => `<div class="pronto-aviso">${ic('subir')}<span><b>Prisma ${esc(s.nome)}</b> pronto para o nível ${s.proximo}: ${s.lm} lm, ${s.luz_propria}% luz própria.</span>
    <button class="btn prim mini" data-subir="${esc(s.nome)}">Subir para ${s.proximo}</button></div>`).join('');
}

// ------------------------------------------------------------------ telas
function cabecalho() {
  $('#nav').innerHTML = TELAS.map(([id, nome]) => `<button data-tela="${id}">${ic(id)}${nome}</button>`).join('');
  const ex = E.execucao || {};
  $('#telemetria').innerHTML = ex.tempo_total_s ? `${ex.tempo_total_s}s · ${ex.pico_memoria_mib} MiB<br>${ex.tokens_entrada}→${ex.tokens_saida} tok<br>${esc(ex.modelo)}<br>v ${esc(ex.versao)}` : '';
  const nomeFoco = E.modo_nome || MODOS[E.modo]?.[1] || E.modo;
  $('#selo').innerHTML = `<span class="ponto ${esc(E.modo)}"></span>${esc(nomeFoco)} · ${esc(nomeAgente())}`;
}

function telaHoje() {
  const p = E.proxima;
  const outros = listaAvancos().filter((a) => ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado) && (!p || a.id !== p.id)).slice(0, 6);
  const t = p ? String(p.tipo || 'praticar').toLowerCase() : 'praticar';
  const ritmoSem = E.ritmo?.avancos_semana || 1;
  $('#hoje').innerHTML = `
    ${E.autoavaliada ? '' : `<div class="aviso-topo">${ic('info')}<span>Declare seu nível em cada prisma (skill): a trajetória parte dele.</span><button data-ir="ajustes">Declarar agora</button></div>`}
    <div style="margin-top:var(--e5)">${trajetoriaHero()}</div>
    <div class="hoje">
      ${p ? `<div class="bloco destaque">
        <span class="sobre">${p.estado === 'em_andamento' ? 'Avanço em andamento' : 'Próximo avanço'}</span>
        <h3>${esc(p.titulo)}</h3><p>${esc(p.por_que)}</p>
        <div class="etiquetas" style="margin-bottom:var(--e5)">
          <span class="tag luz">${ic('lumen', 'p')}${p.valor_lm} lm</span>
          <span class="tipo-chip ${classeTipo(t)}">${ic(I[t] ? t : 'avancos', 'p')}${esc(t)}</span>
          <span class="tag">${rotuloPrisma(p.skill_plano || p.skill)}</span>
          <span class="tag">${ic('relogio', 'p')}${p.duracao_min} min</span>
        </div>
        ${botoesAvanco(p)}
        <p style="margin:var(--e3) 0 0"><button class="btn link" data-avanco="${esc(p.id)}">Ver o avanço ${ic('seta', 'p')}</button></p>
      </div>` : `<div class="bloco destaque"><span class="sobre">Tudo em dia</span><h3>Nenhum avanço aberto.</h3><p>A Luzia acende 3 avanços novos para a sua maior lacuna.</p>${botaoAcender(maiorLacuna())}</div>`}
      <div class="bloco vivo"><h4><span class="pulso"></span>Lúmens recentes</h4><div id="feed"></div></div>
    </div>
    <div class="titulo"><h2>Outros avanços abertos</h2><span>${ritmoSem} por semana te leva até Plena em ~${E.ritmo?.meses || 12} meses</span></div>
    <div class="acoes">${outros.map(cartaoAvanco).join('')}</div>`;
}

function feed() {
  const el = $('#feed');
  if (!el) return;
  el.innerHTML = (E.lumens || []).slice(0, 7).map((l) => `<div class="feed-lm"><span class="lm ${l.luz === 'refletida' ? 'refl' : ''}">+${l.lm}</span>
      <span>Prisma ${curto(l.skill)}<br><small>${esc(legFonte(l.fonte))} · luz ${l.luz === 'refletida' ? 'refletida' : 'própria'}</small></span><small>${esc(String(l.quando || '').slice(11, 16))}</small></div>`).join('')
    || '<div class="vazio">Conquiste avanços ou trabalhe no seu repositório: a Luzia em foco reconhece o que você aplica e os lúmens aparecem aqui.</div>';
}

function renderFormPedido() {
  if (!mostrarFormPedido) return '';
  const todosNomes = listaPrismas().map((p) => p.nome);
  const seletorExistente = ['mudar_meta', 'arquivar', 'reativar'].includes(tipoPedidoForm);
  const opcoesPrisma = todosNomes.map((n) => `<option value="${esc(n)}">Prisma ${esc(n)}</option>`).join('');
  return `<div class="bloco" style="margin-bottom:var(--e4);border-color:var(--refletida)">
    <div class="pedido-cab">
      <b>Pedir mudança formal na trajetória</b>
      <button class="btn link mini" data-abrir-pedido-form="0">${ic('fechar', 'p')}Fechar</button>
    </div>
    <div class="campos">
      <label>Tipo de mudança
        <select id="ped-tipo">
          <option value="incluir" ${tipoPedidoForm === 'incluir' ? 'selected' : ''}>Incluir novo prisma (skill)</option>
          <option value="mudar_meta" ${tipoPedidoForm === 'mudar_meta' ? 'selected' : ''}>Mudar meta de um prisma</option>
          <option value="arquivar" ${tipoPedidoForm === 'arquivar' ? 'selected' : ''}>Arquivar um prisma</option>
          <option value="reativar" ${tipoPedidoForm === 'reativar' ? 'selected' : ''}>Reativar um prisma arquivado</option>
        </select>
      </label>
      ${seletorExistente
        ? `<label>Prisma (skill)<select id="ped-prisma">${opcoesPrisma}</select></label>`
        : `<label>Nome do novo prisma (skill)<input id="ped-prisma" placeholder="ex.: Mensageria e Eventos Assíncronos"></label>`}
      <label>Seu motivo para a mudança<input id="ped-motivo" placeholder="por que este ajuste faz sentido agora na sua carreira?"></label>
      ${['incluir', 'mudar_meta'].includes(tipoPedidoForm)
        ? `<label>Meta desejada (1 a 5, opcional)<input id="ped-meta" type="number" min="1" max="5" placeholder="ex.: 4"></label>`
        : ''}
    </div>
    <p class="dica">A Luzia analisa o impacto na sua trajetória e devolve uma proposta com base antes de criar nova versão. Nada do seu progresso é perdido.</p>
    <div class="acoes-bt" style="margin-top:var(--e3)">
      <button class="btn prim" id="ped-enviar">${ic('enviar')}Analisar e abrir pedido</button>
    </div>
  </div>`;
}

function renderCardPedido(p) {
  const prop = p.proposta || {};
  const aberto = ['aberto', 'proposto'].includes(p.estado);
  const nvSug = prop.nivel_partida ?? 1;
  const metaSug = prop.meta ?? 4;
  // A leitura guardada do pedido (texto, modelo e data de quando foi gerada), nunca o modelo configurado agora.
  const comAnalise = ['incluir', 'mudar_meta'].includes(p.tipo) && (prop.nivel_partida != null || prop.meta != null);

  return `<div class="pedido-card ${esc(p.estado)}">
    <div class="pedido-cab">
      <span>
        <span class="tag ${aberto ? 'refl' : p.estado === 'aceito' ? 'ok' : ''}">${esc(p.estado)}</span>
        <b>#${p.id} · ${esc(TIPO_PEDIDO_NOME[p.tipo] || p.tipo)} · Prisma ${esc(p.prisma)}</b>
      </span>
      <small style="color:var(--texto-3)">${esc(String(p.criado_em || '').slice(0, 10))}</small>
    </div>
    ${p.motivo ? `<p class="lacuna" style="margin:4px 0"><b>Seu motivo:</b> ${esc(p.motivo)}</p>` : ''}
    ${prop && (prop.nivel_partida != null || prop.meta != null) ? `
      <div class="etiquetas" style="margin:var(--e2) 0">
        <span class="tag luz">Proposta: nível ${nvSug} → meta ${metaSug}</span>
        ${(prop.palavras_chave || []).map((w) => `<span class="tag">${esc(w)}</span>`).join('')}
        ${(prop.acoes || []).length ? `<span class="tag">${prop.acoes.length} avanço(s) inicial(is)</span>` : ''}
      </div>` : ''}
    ${comAnalise ? blocoLeitura(p.leitura, `pedido #${p.id} · Prisma ${p.prisma}`, true, prop.leitura_indisponivel) : ''}
    ${aberto ? `<div class="pedido-ajuste">
      <button class="btn prim mini" data-pedido-aceitar="${p.id}">${ic('check', 'p')}Aceitar proposta</button>
      ${['incluir', 'mudar_meta'].includes(p.tipo) ? `
        <label>Nível <input type="number" min="0" max="5" value="${nvSug}" id="aj-nv-${p.id}"></label>
        <label>Meta <input type="number" min="1" max="5" value="${metaSug}" id="aj-mt-${p.id}"></label>
        <button class="btn sec mini" data-pedido-ajustar="${p.id}">Ajustar proposta</button>
      ` : ''}
      <button class="btn link mini" data-pedido-recusar="${p.id}">Recusar</button>
    </div>` : ''}
  </div>`;
}

function telaTrajetoria() {
  const versao = E.trajetoria?.versao_atual || 1;
  const versoes = (E.trajetoria?.versoes || []).slice().reverse();
  const ativos = prismasAtivos();
  const arquivados = listaPrismas().filter((p) => p.estado === 'arquivado');
  const pedidos = E.pedidos || [];

  $('#trajetoria').innerHTML = `
    <div class="titulo">
      <div>
        <h2>Prismas (skills) da sua trajetória · versão v${versao}</h2>
        <span>${E.regras.limiar} lm por nível · mínimo ${E.regras.min_propria}% de luz própria · ao menos ${E.regras.min_avancos || 1} avanço conquistado · você confirma cada subida</span>
      </div>
      <div class="acoes-bt">
        <button class="btn sec mini" data-gerar-leituras="1">${ic('raio', 'p')}Atualizar leituras</button>
        <button class="btn prim mini" data-abrir-pedido-form="1">${ic('enviar', 'p')}Pedir mudança</button>
      </div>
    </div>
    ${renderFormPedido()}
    <div class="legenda" style="margin-bottom:var(--e4)">
      <span><i style="background:var(--luz)"></i>luz própria (você demonstrou)</span>
      <span><i style="background:var(--refletida)"></i>luz refletida (o agente aplicou)</span>
      <span><i style="background:var(--areia)"></i>borda na faixa = meta do prisma</span>
    </div>
    <div class="prismas-lista">
      ${ativos.map((s) => {
        const resumoFatos = `nível ${s.nivel}/${s.meta ?? s.alvo} · ${s.lm || 0} lm (${s.luz_propria || 0}% própria)`;
        return `<div class="prisma-card ${s.pronto && !s.na_meta ? 'pronta' : ''} ${s.na_meta ? 'meta-ok' : ''}">
          <button class="prisma-topo" data-prisma="${esc(s.nome)}">
            <span class="nome"><b>Prisma ${esc(s.nome)}</b><small>${espectroPrisma(s)}</small></span>
            <span>${barraNivel(s)}</span>
            <span>${s.pronto && !s.na_meta ? `<span class="btn prim mini" data-subir="${esc(s.nome)}">${ic('subir', 'p')}Subir</span>` : ic('seta', 'p')}</span>
          </button>
          ${blocoLeitura(s.leitura, resumoFatos, true)}
        </div>`;
      }).join('')}
    </div>
    <p class="dica">Clique num prisma para ver a leitura completa com a base de fatos, níveis conquistados e avanços ligados.</p>

    <div class="titulo"><h2>Pedidos de mudança na trajetória</h2><span>incluir, mudar meta, arquivar ou reativar prismas sem perder progresso</span></div>
    <div class="pedidos-lista">
      ${pedidos.map(renderCardPedido).join('') || '<div class="bloco vazio">Nenhum pedido de mudança registrado ainda. Use o botão "Pedir mudança" acima ou <b>/luzia:trajetoria</b> no seu agente.</div>'}
    </div>

    ${arquivados.length ? `
      <div class="titulo"><h2>Prismas arquivados</h2><span>fora da contagem de níveis atual, mas com todos os lúmens e avanços preservados</span></div>
      <div class="prismas-lista">
        ${arquivados.map((s) => `<div class="prisma-card">
          <div class="prisma-topo">
            <span class="nome"><b>Prisma ${esc(s.nome)}</b><small>${espectroPrisma(s)}</small></span>
            <span class="lacuna">${s.lm || 0} lm preservados</span>
            <button class="btn sec mini" data-reativar-prisma="${esc(s.nome)}">Reativar</button>
          </div>
        </div>`).join('')}
      </div>
    ` : ''}

    <div class="titulo"><h2>Histórico de versões da trajetória</h2><span>registro imutável de cada versão</span></div>
    <div class="versoes-lista">
      ${versoes.map((v) => `<div class="versao-item">
        <span><b>Versão v${v.numero}</b> · origem: ${esc(v.origem)}</span>
        <span>${(v.prismas || []).filter((p) => p.estado !== 'arquivado').length} prisma(s) ativo(s) · ${esc(String(v.criada_em || '').slice(0, 10))}</span>
      </div>`).join('')}
    </div>`;
}

function passaEstado(a, est) {
  if (est === 'todos') return true;
  if (est === 'abertos') return ['sugerido', 'na_fila', 'em_andamento'].includes(a.estado);
  return a.estado === est;
}

function passaPrisma(a, pri) {
  if (pri === 'todos') return true;
  return (a.skill_plano || a.skill) === pri;
}

function passaTipo(a, tip) {
  if (tip === 'todos') return true;
  return String(a.tipo || '').toLowerCase() === tip;
}

function telaAvancos() {
  const todos = listaAvancos();
  const estadosOpcoes = [
    ['abertos', 'Abertos'],
    ['todos', 'Todos'],
    ['em_andamento', 'Em andamento'],
    ['na_fila', 'Na fila'],
    ['sugerido', 'Sugeridos'],
    ['conquistado', 'Conquistados'],
    ['descartado', 'Descartados'],
  ];
  const prismasNomes = listaPrismas().map((p) => p.nome);
  const tiposOpcoes = ['todos', 'praticar', 'explicar', 'estudar', 'explorar'];

  const contEstado = (k) => todos.filter((a) => passaEstado(a, k) && passaPrisma(a, filtroPrisma) && passaTipo(a, filtroTipo)).length;
  const contPrisma = (p) => todos.filter((a) => passaEstado(a, filtroEstado) && passaPrisma(a, p) && passaTipo(a, filtroTipo)).length;
  const contTipo = (t) => todos.filter((a) => passaEstado(a, filtroEstado) && passaPrisma(a, filtroPrisma) && passaTipo(a, t)).length;

  const filtrados = todos.filter((a) => passaEstado(a, filtroEstado) && passaPrisma(a, filtroPrisma) && passaTipo(a, filtroTipo));

  $('#avancos').innerHTML = `
    <div class="titulo">
      <h2>Seus avanços por prisma (skill)</h2>
      <span>valor por esforço + lacuna + prioridade · filtros combináveis por estado, prisma e tipo</span>
    </div>
    <div class="filtros-grupo">
      <div class="filtros-linha">
        <span class="filtros-rotulo">Estado</span>
        <div class="filtros">
          ${estadosOpcoes.map(([k, rot]) => `<button data-filtro-estado="${k}" class="${filtroEstado === k ? 'ativo' : ''}">${rot} · ${contEstado(k)}</button>`).join('')}
        </div>
      </div>
      <div class="filtros-linha">
        <span class="filtros-rotulo">Prisma</span>
        <div class="filtros">
          <button data-filtro-prisma="todos" class="${filtroPrisma === 'todos' ? 'ativo' : ''}">Todos os prismas · ${contPrisma('todos')}</button>
          ${prismasNomes.map((n) => `<button data-filtro-prisma="${esc(n)}" class="${filtroPrisma === n ? 'ativo' : ''}">Prisma ${curto(n)} · ${contPrisma(n)}</button>`).join('')}
        </div>
      </div>
      <div class="filtros-linha">
        <span class="filtros-rotulo">Tipo</span>
        <div class="filtros">
          ${tiposOpcoes.map((t) => `<button data-filtro-tipo="${t}" class="${filtroTipo === t ? 'ativo' : ''}">${t === 'todos' ? 'Todos os tipos' : t} · ${contTipo(t)}</button>`).join('')}
        </div>
      </div>
    </div>
    <div class="acoes">${filtrados.map(cartaoAvanco).join('') || '<span class="vazio">Nenhum avanço corresponde a esta combinação de filtros.</span>'}</div>`;
}

function telaEntregas() {
  const nomeDim = { P1: 'Direção no prompt', P2: 'Coesão da entrega', P3: 'Aplicação conceitual', P4: 'Domínio arquitetural' };
  const cor = (v) => (v >= 80 ? 'var(--salvia)' : v >= 50 ? 'var(--luz)' : 'var(--terracota)');
  const anel = (v, t = 120) => {
    const r = t / 2 - 8, c = 2 * Math.PI * r, x = v ?? 0;
    return `<svg width="${t}" height="${t}" aria-hidden="true"><circle cx="${t / 2}" cy="${t / 2}" r="${r}" fill="none" stroke="var(--refletida)" stroke-opacity=".55" stroke-width="8"/>
      <circle cx="${t / 2}" cy="${t / 2}" r="${r}" fill="none" stroke="var(--luz)" stroke-width="8" stroke-linecap="round" stroke-dasharray="${(c * x) / 100} ${c}"/></svg>`;
  };
  const entregas = (E.entregas || []).map((e) => {
    const f = e.fatos || {};
    const dims = Object.entries(e.dimensoes || {}).map(([k, d]) => d
      ? `<div class="dim"><div class="cab"><span>${k} · ${nomeDim[k]}</span><span>${esc(d.tipo)}</span></div><div class="v">${d.nota}</div>
          <div class="b"><i style="width:${d.nota}%;background:${cor(d.nota)}"></i></div><div class="base">${esc(d.base)}</div></div>`
      : `<div class="dim sem"><div class="cab"><span>${k} · ${nomeDim[k]}</span></div><div class="v">—</div>
          <div class="b"><i style="width:100%;background:var(--refletida);opacity:.55"></i></div><div class="base">Ainda luz refletida (do agente). O avanço abaixo acende.</div></div>`).join('');

    const prismasTags = (e.prismas || []).map((p) => {
      const nomeP = typeof p === 'string' ? p : p.prisma;
      const termos = (p.termos || []).length ? ` · termos: ${p.termos.map(esc).join(', ')}` : '';
      return `<span class="tag refl">Prisma ${curto(nomeP)}${termos}</span>`;
    }).join('');

    const lms = e.lumens_ligados || [];
    const feitosIds = e.avancos_feitos || [];
    const uteisIds = e.avancos_uteis || e.acoes || [];
    const feitosCards = feitosIds.map(avancoPorId).filter(Boolean).map(cartaoAvanco).join('');
    const uteisCards = uteisIds.map(avancoPorId).filter(Boolean).map(cartaoAvanco).join('');
    const resumoFatos = `${f.commits ?? 1} commit(s) · ${f.arquivos ?? 0} arquivo(s) · +${f.linhas ?? 0} linhas · ${f.duracao_dias ?? 1} dia(s)`;

    return `<div class="bloco entrega">
      <div class="anel-col">
        <div class="anel">${anel(e.indice)}<div><b>${e.indice ?? '—'}${e.indice == null ? '' : '%'}</b></div></div>
        ${e.indice == null ? '' : `<div class="anel-leg"><span><i style="background:var(--luz)"></i>sua ${e.indice}%</span><span><i style="background:var(--refletida)"></i>do agente ${100 - e.indice}%</span></div>`}
        <small class="anel-base">medido em ${esc(e.base || 'P1, P2')}</small>
        ${e.id ? `<button class="btn sec mini" data-entrega-detalhe="${e.id}">Detalhe completo</button>` : ''}
        ${botaoAcenderEntrega(e.id, e.dimensoes, feitosIds.map(avancoPorId))}
      </div>
      <div>
        <h3>${esc(e.titulo || e.tarefa)}</h3>
        <div class="fatos-entrega">
          <span class="tag">${esc(e.fonte || 'git')}</span>
          ${f.inicio ? `<span class="tag">${esc(String(f.inicio).slice(0, 10))} → ${esc(String(f.fim || f.inicio).slice(0, 10))} (${f.duracao_dias || 1}d)</span>` : ''}
          <span class="tag">${f.commits ?? 1} commit(s)</span>
          <span class="tag">${f.arquivos ?? 0} arquivo(s)</span>
          <span class="tag">+${f.linhas ?? 0} linhas</span>
          ${(f.areas || []).map((ar) => `<span class="tag">${esc(ar)}</span>`).join('')}
        </div>
        ${prismasTags ? `<div class="prismas-entrega">${prismasTags}</div>` : ''}
        ${blocoLeitura(e.leitura, resumoFatos, true)}
        <div class="dims">${dims}</div>
        ${lms.length ? `<div class="entrega-secao"><h4>Lúmens ligados na janela (${lms.length})</h4>
          <div class="etiquetas">${lms.slice(0, 6).map((l) => `<span class="tag ${l.luz === 'refletida' ? 'refl' : 'luz'}">+${l.lm} lm · Prisma ${curto(l.prisma || l.skill)} · ${esc(legFonte(l.fonte))}</span>`).join('')}</div>
        </div>` : ''}
        ${feitosCards ? `<div class="entrega-secao"><h4>Avanços feitos nesta entrega</h4><div class="acoes">${feitosCards}</div></div>` : ''}
        ${uteisCards ? `<div class="entrega-secao"><h4>Avanços úteis dos mesmos prismas</h4><div class="acoes">${uteisCards}</div></div>` : ''}
      </div>
    </div>`;
  }).join('');

  $('#entregas').innerHTML = `
    <div class="titulo">
      <div>
        <h2>Entregas e propriedade intelectual</h2>
        <span>fatos do git · prismas (skills) atravessados · lúmens e avanços ligados · P1 a P4</span>
      </div>
      <div class="acoes-bt">
        <button class="btn sec mini" data-gerar-leituras="1">${ic('raio', 'p')}Atualizar leituras</button>
        <button class="btn sec mini" data-ampliar-entregas="180">${ic('relogio', 'p')}Ampliar janela (180 dias)</button>
      </div>
    </div>
    <details class="medida bloco"><summary>${ic('info')}Como isso é medido</summary><ul>${(E.como_e_medido || []).map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>
    ${entregas || semEntregas()}`;
}

// Sem entrega no git: só fatos (repositório, identidades, janela) e o que a pessoa pode fazer. Nunca as tarefas da IA.
function semEntregas() {
  const d = E.entregas_diagnostico || {};
  const ids = (d.identidades || []).map(esc).join(', ') || 'nenhuma';
  const janela = d.janela_desde
    ? `desde ${esc(d.janela_desde)} · última leitura ${esc(d.ultima_leitura)} · ${d.commits_seus ?? 0} commit(s) seu(s) encontrado(s)`
    : 'ainda não lida (rode /luzia:entregas no seu agente)';
  return `<div class="bloco vazio entregas-diagnostico">
    <h3>Nenhuma entrega detectada no git</h3>
    <ul class="lacuna" style="padding-left:18px">
      <li><b>Repositório autorizado:</b> ${d.repo_configurado ? 'configurado' : 'não configurado (campo repo em private/entrada.json)'}</li>
      <li><b>Identidades do git:</b> ${ids}</li>
      <li><b>Janela:</b> ${janela}</li>
    </ul>
    <div class="pedido-ajuste">
      <button class="btn sec mini" data-ampliar-entregas="180">${ic('relogio', 'p')}Ampliar janela (180 dias)</button>
      <label>Nome ou e-mail do git <input type="text" id="ent-identidade" maxlength="120" autocomplete="off"></label>
      <button class="btn prim mini" id="ent-identidade-salvar">${ic('check', 'p')}Acrescentar identidade</button>
    </div>
    <p class="dica">No chat: <b>identidade</b> confere e <b>identidade adicionar "&lt;nome ou e-mail&gt;"</b> acrescenta.</p>
  </div>`;
}

let provEscolhido = null;
function secaoModelo() {
  const m = E.modelo;
  const prov = provEscolhido || m.provedor;
  const info = m.provedores[prov];
  const atual = prov === m.provedor;
  return `<div class="titulo"><h2>Modelo da Luzia</h2><span>agora: ${esc(m.nome_provedor)} · ${esc(m.modelo)}</span></div>
    <div class="opcoes">${Object.entries(m.provedores).map(([k, v]) => `<button class="opcao ${prov === k ? 'ativo' : ''}" data-provedor="${k}">${ic('agente')}<span><b>${esc(v.nome)}</b><small>${v.chave_configurada ? 'chave configurada' : 'sem chave'}</small></span></button>`).join('')}</div>
    <div class="bloco" style="margin-top:var(--e3)">
      <div class="campos">
        ${(() => {
          const valor = atual ? m.modelo : (info.sugestoes[0] || '');
          const conhecido = info.sugestoes.includes(valor);
          const opcoes = info.sugestoes.map((s) => `<option value="${esc(s)}" ${s === valor ? 'selected' : ''}>${esc(s)}</option>`).join('');
          return `<label>Modelo<select id="m-select">${opcoes}<option value="__outro" ${conhecido ? '' : 'selected'}>outro modelo…</option></select></label>
            <label ${conhecido ? 'hidden' : ''} id="m-outro-l">Nome do modelo<input id="m-outro" value="${conhecido ? '' : esc(valor)}" placeholder="nome exato do modelo"></label>`;
        })()}
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
    <div class="titulo"><h2>Seu nível hoje em cada prisma (skill)</h2><span>0 a 5 · a trajetória parte daqui e só sobe quando você confirma</span></div>
    <div class="niveis">${prismasAtivos().map((s, i) => `<div class="bloco nivel">
      <div class="cab"><b>Prisma ${esc(s.nome)}</b><span id="n${i}">${s.voce}</span></div>
      <input type="range" min="0" max="5" value="${s.voce}" data-prisma-nivel="${esc(s.nome)}" data-i="${i}" aria-label="Prisma ${esc(s.nome)}">
      <small>meta ${s.meta ?? s.alvo} · Luzia sugere ${s.sugere}</small></div>`).join('')}</div>
    <p style="margin-top:var(--e4)"><button class="btn prim" id="salvar-niveis">${ic('check')}Salvar meu nível</button></p>
    ${secaoModelo()}
    <div class="titulo"><h2>Seu agente</h2><span>a Luzia funciona em qualquer um</span></div>
    <div class="opcoes">${Object.entries(AGENTES).map(([k, [t, d]]) => opcao('agente', k, ['agente', t, d], E.agente === k)).join('')}</div>
    <div class="titulo"><h2>Foco da Luzia na sessão</h2><span>como a Luzia acompanha seu trabalho em tempo real</span></div>
    <div class="opcoes">${Object.entries(MODOS).map(([k, v]) => opcao('modo', k, v, E.modo === k)).join('')}</div>`;
}

// Leituras vencidas com modelo configurado: o painel pede sozinho, em segundo plano, uma vez por carregamento
// da página (o servidor ainda segura no máximo uma rodada a cada 10 min). A tela não espera: avisa quando terminar.
let leiturasAutoPedidas = false;
function leiturasAutomaticas() {
  if (leiturasAutoPedidas || !E || !E.modelo_pronto || !(E.leituras_vencidas > 0)) return;
  leiturasAutoPedidas = true;
  api('/api/leituras', { auto: true }).then(async (r) => {
    if (r.erro || !r.geradas) return;
    toast(`${r.geradas} leitura(s) da Luzia gerada(s) com base nos fatos.`);
    await carregar();
  });
}

async function carregar() {
  const tela = document.querySelector('.tela.ativa')?.id || 'hoje';
  const novo = await api('/api/estado');
  if (novo.erro) {
    toast(novo.erro);
    if (E) return;
    $('#hoje').innerHTML = `<div class="bloco destaque"><span class="sobre">Luzia</span><h3>Não consegui carregar.</h3><p>${esc(novo.erro)}</p></div>`;
    return;
  }
  E = novo;
  if (E.vazio) {
    $('main').innerHTML = '<div class="bloco destaque"><span class="sobre">Olá</span><h3>Eu sou a Luzia.</h3><p>Rode a triagem no seu agente (/luzia:triage no Claude Code) para começarmos.</p></div>';
    return;
  }
  $('#jornada').innerHTML = '';
  render(tela);
  leiturasAutomaticas();
}

function render(tela = document.querySelector('.tela.ativa')?.id || 'hoje') {
  cabecalho();
  telaHoje();
  telaTrajetoria();
  telaAvancos();
  telaEntregas();
  telaAjustes();
  feed();
  irPara(TELAS.some(([id]) => id === tela) ? tela : 'hoje');
}

function irPara(tela) {
  const mapaApelidos = { rota: 'trajetoria', feixes: 'avancos', propria: 'entregas' };
  const destino = mapaApelidos[tela] || tela;
  document.querySelectorAll('nav button').forEach((b) => b.classList.toggle('ativo', b.dataset.tela === destino));
  document.querySelectorAll('.tela').forEach((s) => s.classList.toggle('ativa', s.id === destino));
}

// ------------------------------------------------------------------ eventos
document.addEventListener('click', async (ev) => {
  const seletor = [
    '[data-acender]', '[data-provedor]', '#m-salvar', '#m-testar', '[data-subir]',
    '[data-tela]', '[data-ir]', '[data-avanco]', '[data-prisma]', '[data-enviar]',
    '[data-copiar]', '[data-descartar]', '[data-restaurar]', '[data-fechar]',
    '[data-modo]', '[data-agente]', '[data-filtro-estado]', '[data-filtro-prisma]',
    '[data-filtro-tipo]', '#salvar-niveis', '[data-abrir-pedido-form]', '#ped-enviar',
    '[data-pedido-aceitar]', '[data-pedido-ajustar]', '[data-pedido-recusar]',
    '[data-reativar-prisma]', '[data-gerar-leituras]', '[data-ampliar-entregas]',
    '[data-entrega-detalhe]', '#ent-identidade-salvar', '[data-acender-entrega]',
  ].join(',');
  const t = ev.target.closest(seletor);
  if (!t) return;
  const ds = t.dataset;

  if (t.id === 'ent-identidade-salvar') {
    const identidade = ($('#ent-identidade')?.value || '').trim();
    if (!identidade) {
      toast('Informe um nome ou e-mail que você usa nos commits.');
      return;
    }
    t.disabled = true;
    const r = await api('/api/identidade', { identidade });
    if (r.erro) {
      toast(`Não acrescentou: ${r.erro}`);
      t.disabled = false;
      return;
    }
    toast('Identidade acrescentada. Lendo as entregas da janela inteira de novo…');
    const amp = await api('/api/entregas/ampliar', { dias: 90 });
    toast(amp.erro ? `Falhou: ${amp.erro}` : `${amp.atualizacao?.novas ?? 0} entrega(s) nova(s) encontrada(s).`);
    await carregar();
    return;
  }

  if (ds.acender) {
    ev.stopPropagation();
    t.disabled = true;
    toast(`Acendendo 3 avanços de Prisma ${ds.acender.split('(')[0].trim()}…`);
    const r = await api('/api/acender', { prisma: ds.acender });
    const qtd = (r.avancos || []).length;
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${qtd} avanços novos de Prisma ${ds.acender.split('(')[0].trim()}`, r.erro ? '' : 'celebra');
    await carregar();
    if (!$('#gaveta').hidden && !r.erro) abrirPrisma(r.prisma || r.skill);
    return;
  }
  if (ds.gerarLeituras) {
    ev.stopPropagation();
    t.disabled = true;
    toast('Gerando leituras com base nos fatos…');
    const r = await api('/api/leituras', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.geradas ? `${r.geradas} leitura(s) atualizada(s) com base.`
      : (E && E.modelo_pronto ? 'Nenhuma leitura gravada: já estavam em dia ou o modelo não respondeu.' : 'Leitura indisponível: configure o modelo em Ajustes.')));
    await carregar();
    return;
  }
  if (ds.ampliarEntregas) {
    t.disabled = true;
    const dias = Number(ds.ampliarEntregas) || 180;
    toast(`Ampliando janela de entregas para ${dias} dias…`);
    const r = await api('/api/entregas/ampliar', { dias });
    toast(r.erro ? `Falhou: ${r.erro}` : `Janela ampliada (${r.atualizacao?.novas ?? 0} nova(s), ${r.atualizacao?.atualizadas ?? 0} atualizada(s)).`);
    await carregar();
    return;
  }
  if (ds.acenderEntrega) {
    ev.stopPropagation();
    t.disabled = true;
    toast('Acendendo 2 avanços para esta entrega (P3 e P4)…');
    const r = await api('/api/entrega/acender', { id: Number(ds.acenderEntrega) });
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${(r.avancos || []).length} avanços ligados a esta entrega`, r.erro ? '' : 'celebra');
    await carregar();
    if (!$('#gaveta').hidden && !r.erro) abrirEntregaDetalhe(ds.acenderEntrega);
    return;
  }
  if (ds.entregaDetalhe) {
    abrirEntregaDetalhe(ds.entregaDetalhe);
    return;
  }
  if (ds.abrirPedidoForm !== undefined) {
    mostrarFormPedido = ds.abrirPedidoForm === '1';
    telaTrajetoria();
    return;
  }
  if (t.id === 'ped-enviar') {
    const tipo = $('#ped-tipo')?.value || 'incluir';
    const prisma = ($('#ped-prisma')?.value || '').trim();
    const motivo = ($('#ped-motivo')?.value || '').trim();
    const metaVal = $('#ped-meta')?.value;
    if (!prisma) {
      toast('Informe o nome do prisma.');
      return;
    }
    t.disabled = true;
    toast('Analisando pedido de mudança na trajetória…');
    const payload = { acao: 'abrir', tipo, prisma, motivo };
    if (metaVal) payload.meta = Number(metaVal);
    const r = await api('/api/pedido', payload);
    if (r.erro) {
      toast(`Aviso: ${r.erro}`);
    } else {
      mostrarFormPedido = false;
      toast('Pedido registrado na trajetória.');
    }
    await carregar();
    return;
  }
  if (ds.pedidoAceitar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'aceitar', id: Number(ds.pedidoAceitar) });
    toast(r.erro ? `Erro: ${r.erro}` : 'Pedido aceito! Nova versão da trajetória criada.', r.erro ? '' : 'celebra');
    await carregar();
    return;
  }
  if (ds.pedidoAjustar) {
    t.disabled = true;
    const pid = Number(ds.pedidoAjustar);
    const nivel = Number($(`#aj-nv-${pid}`)?.value ?? 1);
    const meta = Number($(`#aj-mt-${pid}`)?.value ?? 4);
    toast('Recalculando proposta para o pedido…');
    const r = await api('/api/pedido', { acao: 'ajustar', id: pid, nivel, meta });
    toast(r.erro ? `Erro: ${r.erro}` : 'Proposta ajustada e registrada no histórico do pedido.');
    await carregar();
    return;
  }
  if (ds.pedidoRecusar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'recusar', id: Number(ds.pedidoRecusar) });
    toast(r.erro ? `Erro: ${r.erro}` : 'Pedido recusado. A trajetória atual foi mantida.');
    await carregar();
    return;
  }
  if (ds.reativarPrisma) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'abrir', tipo: 'reativar', prisma: ds.reativarPrisma, motivo: 'Reativado pelo painel' });
    // Como todo pedido: abre, a Luzia propõe e a pessoa aceita no card do pedido (nada muda sozinho).
    toast(r.erro ? (r.erro || 'Não foi possível reativar.')
      : `Pedido de reativar o Prisma ${ds.reativarPrisma} aberto: confira a proposta e aceite.`);
    await carregar();
    return;
  }
  if (ds.provedor) { provEscolhido = ds.provedor; telaAjustes(); return; }
  if (t.id === 'm-salvar') {
    const sel = $('#m-select').value;
    const r = await api('/api/modelo', {
      provedor: provEscolhido || E.modelo.provedor,
      modelo: sel === '__outro' ? $('#m-outro').value : sel,
      base_url: $('#m-base')?.value || '',
      chave: $('#m-chave').value,
    });
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
    const r = await api('/api/subir', { prisma: ds.subir });
    toast(r.erro ? r.erro : `Prisma ${ds.subir.split('(')[0].trim()} subiu para o nível ${r.para}${r.marco ? ' · marco alcançado, dossiê gerado' : ''}`, r.erro ? '' : 'celebra');
    carregar();
  } else if (ds.tela || ds.ir) {
    irPara(ds.tela || ds.ir);
    $('#gaveta').hidden = true;
  } else if (ds.avanco) {
    abrirAvanco(ds.avanco);
  } else if (ds.prisma) {
    abrirPrisma(ds.prisma);
  } else if (ds.enviar) {
    const r = await api('/api/enviar', { id: ds.enviar });
    toast(r.erro ? `Não enviou: ${r.erro}` : `Enviado. Mande qualquer mensagem no ${nomeAgente()} e a Luzia oferece começar.`);
    await carregar();
    if (!$('#gaveta').hidden) abrirAvanco(ds.enviar);
  } else if (ds.copiar) {
    await navigator.clipboard.writeText(avancoPorId(ds.copiar).prompt_completo);
    const r = await api('/api/iniciar', { id: ds.copiar });
    toast(r.erro ? `Copiado, mas: ${r.erro}` : `Prompt copiado e avanço em andamento. Cole no ${nomeAgente()}.`);
    await carregar();
    if (!$('#gaveta').hidden) abrirAvanco(ds.copiar);
  } else if (ds.descartar) {
    await api('/api/descartar', { id: ds.descartar, motivo: ds.motivo });
    $('#gaveta').hidden = true;
    toast('Avanço descartado. A Luzia leva o motivo em conta.');
    carregar();
  } else if (ds.restaurar) {
    await api('/api/restaurar', { id: ds.restaurar });
    $('#gaveta').hidden = true;
    toast('Avanço restaurado.');
    carregar();
  } else if (ds.fechar !== undefined) {
    $('#gaveta').hidden = true;
  } else if (ds.filtroEstado) {
    filtroEstado = ds.filtroEstado;
    telaAvancos();
  } else if (ds.filtroPrisma) {
    filtroPrisma = ds.filtroPrisma;
    telaAvancos();
  } else if (ds.filtroTipo) {
    filtroTipo = ds.filtroTipo;
    telaAvancos();
  } else if (ds.modo) {
    const r = await api('/api/modo', { modo: ds.modo });
    toast(`Foco salvo: ${r.modo_nome || ds.modo}`);
    carregar();
  } else if (ds.agente) {
    await api('/api/agente', { agente: ds.agente });
    toast('Agente salvo');
    carregar();
  } else if (t.id === 'salvar-niveis') {
    const niveis = {};
    document.querySelectorAll('[data-prisma-nivel]').forEach((i) => (niveis[i.dataset.prismaNivel] = Number(i.value)));
    await api('/api/nivel', { niveis });
    toast('Seu nível foi salvo');
    carregar();
  }
});

document.addEventListener('change', (ev) => {
  if (ev.target.id === 'm-select') $('#m-outro-l').hidden = ev.target.value !== '__outro';
  if (ev.target.id === 'ped-tipo') {
    tipoPedidoForm = ev.target.value;
    telaTrajetoria();
  }
});
document.addEventListener('input', (ev) => {
  if (ev.target.matches('[data-prisma-nivel]')) $('#n' + ev.target.dataset.i).textContent = ev.target.value;
});
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') $('#gaveta').hidden = true;
});

carregar();
setInterval(async () => {
  if (!$('#gaveta').hidden || mostrarFormPedido) return;
  const novo = await api('/api/estado');
  if (novo.erro || novo.vazio || !E) return;
  const vistos = new Set((E.lumens || []).map(chaveLm));
  const novos = (novo.lumens || []).filter((l) => !vistos.has(chaveLm(l)));
  const mudou = assinatura(novo) !== assinatura(E);
  E = novo;
  const editando = document.activeElement && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
  if (mudou && !editando) render();
  else feed();
  celebrar(novos);
}, 4000);
