// Luzia · painel local. Jogo (docs/luzia-ux.md): centelhas (`avanco` no código e na API) valem lúmens; lúmens preenchem os níveis de cada prisma (skill);
// os níveis formam a trajetória até Plena. Luz própria (laranja) = você demonstrou; luz refletida (lilás) = o agente aplicou.
// Dados: /api/estado, /api/entrega, /api/avancos e /api/pedido. Ícones próprios em SVG, sem emoji.
// Hierarquia (ux/auditoria.md): cada cartão tem 1 título, 1 linha de números e 1 ação; o resto fica em "Ver detalhe".
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
  baixo: '<path d="M6 9l6 6 6-6"/>',
  cima: '<path d="M6 15l6-6 6 6"/>',
};
const ic = (n, c = '') => `<svg class="ic ${c}" viewBox="0 0 24 24" aria-hidden="true">${I[n] || ''}</svg>`;

const TELAS = [
  ['hoje', 'Hoje'],
  ['trajetoria', 'Trajetória'],
  ['avancos', 'Centelhas'],
  ['entregas', 'Entregas'],
  ['ajustes', 'Ajustes'],
];
const ESTADO = {
  sugerido: 'sugerida',
  na_fila: 'na fila',
  em_andamento: 'em andamento',
  conquistado: 'acesa',
  descartado: 'descartada',
};
// Grupos da lista de avanços, na ordem em que aparecem (o filtro por estado fino continua no chat: `--estado`).
const GRUPOS = [
  ['em_andamento', 'Em andamento'],
  ['na_fila', 'Na fila'],
  ['sugerido', 'Sugeridas'],
  ['conquistado', 'Acesas'],
  ['descartado', 'Descartadas'],
];
// [ícone, nome curto (selo e opção), descrição (até 8 palavras), dica do selo]
const MODOS = {
  ativo: ['raio', 'Em foco', 'Soma lúmens e mostra centelhas', 'Com centelhas da sessão no chat'],
  passivo: ['olho', 'Em silêncio', 'Soma lúmens sem interromper', 'Em foco, sem interromper o chat'],
  sob_demanda: ['chat', 'Fora de foco', 'Só age quando você chama', 'Só age quando você chama um comando'],
};
const AGENTES = {
  'claude-code': ['Claude Code', 'Fila, comandos e foco automático'],
  codex: ['Codex', 'Fila e comandos via AGENTS.md'],
  cursor: ['Cursor', 'Fila e comandos via User Rules'],
  antigravity: ['Antigravity', 'Fila e comandos via GEMINI.md'],
  outro: ['Outro', 'Qualquer agente com terminal'],
};
const TIPO_PEDIDO_NOME = {
  incluir: 'Incluir',
  mudar_meta: 'Mudar meta de',
  arquivar: 'Arquivar',
  reativar: 'Reativar',
  dividir: 'Dividir',
};
const NOME_DIM = { P1: 'Direção no prompt', P2: 'Coesão', P3: 'Aplicação de conceito', P4: 'Decisão de arquitetura' };
const FALTA_DIM = { P1: 'sem base ainda', P2: 'sem base ainda', P3: 'falta você explicar', P4: 'falta você defender' };
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

let E = null;
let filtroEstado = 'abertos';
let filtroPrisma = 'todos';
let filtroTipo = 'todos';
let mostrarFormPedido = false;
let tipoPedidoForm = 'incluir';
let ajustandoPedido = null;          // id do pedido com os campos Nível/Meta à mostra (só depois de "Ajustar")
const entregasAbertas = new Set();   // detalhes de entrega abertos: sobrevivem ao render() do polling

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const listaAvancos = () => (E?.avancos || E?.acoes || []);
const listaPrismas = () => (E?.prismas || E?.skills || []);
const prismasAtivos = () => (E?.skills || listaPrismas().filter((p) => p.estado !== 'arquivado'));
const avancoPorId = (id) => listaAvancos().find((a) => a.id === id);
const nomeAgente = () => AGENTES[E?.agente]?.[0] || 'seu agente';
const ABERTOS = ['sugerido', 'na_fila', 'em_andamento'];

// Nome curto do prisma (o mesmo de prismas.nome_curto no servidor, que manda quando o prisma está no estado):
// sigla entre parênteses; senão o nome inteiro se couber; senão o trecho após o último " / "; senão 18 caracteres.
function nomeCurto(nome) {
  const n = String(nome || '').replace(/\s+/g, ' ').trim();
  const doServidor = listaPrismas().find((p) => p.nome === n)?.nome_curto;
  if (doServidor) return doServidor;
  const m = /^(.*?)\s*\(([^()]+)\)\s*$/.exec(n);
  if (m && /^[\wÀ-ÿ.#+-]{2,10}$/.test(m[2].trim())) return m[2].trim();
  const base = (m ? m[1] : n).trim();
  if (base.length <= 20) return base;
  const ultimo = base.split(/\s+\/\s+/).pop().trim();
  if (ultimo !== base && ultimo.length >= 2 && ultimo.length <= 20) return ultimo;
  return base.slice(0, 18).trim() + '…';
}
const curto = (s) => esc(nomeCurto(s));
const rotuloPrisma = (s) => `<span title="${esc(s)}">${curto(s)}</span>`;
const plural = (n, um, varios) => `${n} ${Number(n) === 1 ? um : (varios || um + 's')}`;
const numero = (n) => Number(n || 0).toLocaleString('pt-BR');
function dataCurta(iso, comAno = false) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return '';
  const ano = comAno || m[1] !== String(new Date().getFullYear()) ? ` ${m[1]}` : '';
  return `${Number(m[3])} ${MESES[Number(m[2]) - 1]}${ano}`;
}
function periodoCurto(inicio, fim) {
  const a = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(inicio || ''));
  const b = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(fim || inicio || ''));
  if (!a || !b) return '';
  if (a[0] === b[0]) return dataCurta(inicio);
  if (a[1] === b[1] && a[2] === b[2]) return `${Number(a[3])}–${dataCurta(fim)}`;
  return `${dataCurta(inicio)} – ${dataCurta(fim)}`;
}
const truncar = (t, n = 120) => {
  const s = String(t || '').trim();
  return s.length <= n ? s : s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…';
};

// `auto`: pedido que a página faz sozinha (polling, leituras automáticas); o servidor confere a sessão sem renová-la.
async function api(caminho, dados, auto = false) {
  try {
    const headers = auto ? { 'X-Luzia-Auto': '1' } : {};
    if (dados) headers['Content-Type'] = 'application/json';
    const r = await fetch(caminho, dados ? { method: 'POST', headers, body: JSON.stringify(dados) } : { headers });
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && j.login) {  // sessão ausente, vencida ou derrubada: volta ao login e para o polling
      acessoAoIniciar();
      return { erro: j.erro || 'abra o painel pelo seu agente', login: true };
    }
    return r.ok ? j : { ...j, erro: j.erro || `erro ${r.status}` };
  } catch {
    return { erro: 'Luzia desligada. Rode /luzia:career-map no chat.', offline: true };
  }
}

// Toast = resultado, não instrução. `acao` opcional: um botão (ex.: Desfazer) com os mesmos data-* dos botões da tela.
function toast(texto, classe = '', acao = null) {
  const el = $('#toast');
  el.className = 'toast ' + classe;
  const bt = acao ? `<button class="btn link mini" ${Object.entries(acao.dados || {}).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')}>${esc(acao.rotulo)}</button>` : '';
  el.innerHTML = ic(classe === 'celebra' ? 'lumen' : 'check') + `<span>${esc(texto)}</span>` + bt;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), acao ? 6000 : classe === 'celebra' ? 4200 : 2800);
}

// ------------------------------------------------------------------ ao vivo: o painel acompanha o que acontece no agente
const FONTES = {
  avanco: 'centelha acesa',
  'passivo-prompt': 'você dirigiu',
  'passivo-refletida': 'o agente aplicou',
  'passivo-conversao': 'centelha da sessão',
  conversao: 'centelha da sessão',
};
const legFonte = (f) => FONTES[f] || 'centelha acesa';
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
  toast(`+${total} lm · ${nomeCurto(l.skill)} · ${novos.length > 1 ? `${novos.length} reconhecimentos` : legFonte(l.fonte)}`, 'celebra');
  document.querySelectorAll('.trajetoria-linha .luz, .barra-nivel .p, .barra-nivel .r').forEach((b) => {
    b.classList.remove('brilho');
    void b.offsetWidth;
    b.classList.add('brilho');
  });
}

function maiorLacuna() {
  const abertos = new Set(listaAvancos().filter((a) => ABERTOS.includes(a.estado)).map((a) => a.skill_plano || a.skill));
  return prismasAtivos().filter((s) => !s.na_meta).sort((a, b) => (abertos.has(a.nome) - abertos.has(b.nome)) || ((b.alvo - b.nivel) - (a.alvo - a.nivel)))[0];
}

function botaoAcender(s, classe = 'sec') {
  return s ? `<button class="btn ${classe}" data-acender="${esc(s.nome)}" title="${esc(s.nome)}">${ic('raio')}Acender 3 centelhas de ${curto(s.nome)}</button>` : '';
}

// Banner único das leituras vencidas (as automáticas de leiturasAutomaticas continuam).
function bannerLeituras() {
  const n = E?.leituras_vencidas || 0;
  if (!n || !E.modelo_pronto) return '';
  return `<div class="aviso fino" role="status">${ic('info', 'p')}<span>${plural(n, 'análise desatualizada', 'análises desatualizadas')}</span>
    <button class="btn link mini" data-gerar-leituras="1">Atualizar</button></div>`;
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
    faixas += `<i class="${classes}"></i>`;
  }
  return `<span class="espectro-wrap"><span class="espectro" role="img" aria-label="nível ${nivel} de 5, meta ${meta}" title="nível ${nivel} de 5 · meta ${meta}">${faixas}</span>${legenda ? `<span class="espectro-legenda">${nivel} → ${meta}</span>` : ''}</span>`;
}

function resumoBaseLeitura(leitura, fallbackFatos = '') {
  // Os mesmos fatos que a CLI mostra depois de "base:" (cli.base_resumo), lidos da base guardada.
  if (leitura && leitura.base && typeof leitura.base === 'object') {
    const b = leitura.base;
    const alvo = leitura.alvo_tipo;
    if (alvo === 'prisma') {
      const lm = b.lumens || {};
      return `nível ${b.nivel ?? '?'} de ${b.meta ?? '?'}, ${lm.total ?? 0} lm (${lm.propria ?? 0} própria), ${plural((b.avancos_conquistados || []).length, 'centelha acesa', 'centelhas acesas')}, ${plural(b.entregas_total ?? 0, 'entrega')}`;
    }
    if (alvo === 'entrega') {
      const f = b.fatos || {};
      return `${plural(f.commits ?? 0, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}, ${plural((b.prismas || []).length, 'prisma')}`;
    }
    if (alvo === 'pedido') {
      return `o pedido (${TIPO_PEDIDO_NOME[b.tipo] || b.tipo || ''} ${nomeCurto(b.prisma || '')}) e a trajetória atual`;
    }
  }
  return fallbackFatos || 'fatos medidos pela Luzia';
}

// Análise da Luzia (`leitura` no código): texto primeiro; abaixo "Luzia · 12 nov" e um ícone focável com a base e o modelo (popover).
// `json`: mostra "Ver base (JSON)" (só nas gavetas).
function blocoLeitura(leitura, fallbackFatos = '', json = false, indisponivel = '') {
  if (!leitura || !leitura.texto || !leitura.modelo) {
    let txt = indisponivel ? `Sem análise: ${esc(indisponivel)}` : 'Sem análise ainda.';
    let bt = '';
    if (!indisponivel && E && !E.modelo_pronto) {
      txt = 'Sem análise: falta configurar o modelo.';
      bt = '<button class="btn link mini" data-ir="ajustes">Configurar</button>';
    } else if (!indisponivel && E && E.modelo_pronto) {
      bt = `<button class="btn link mini" data-gerar-leituras="1">Gerar análise</button>`;
    }
    return `<div class="leitura vazia"><span>${txt}</span> ${bt}</div>`;
  }
  const base = resumoBaseLeitura(leitura, fallbackFatos);
  const data = dataCurta(leitura.criado_em) || 'data desconhecida';
  const dica = `Base: ${base} · Modelo: ${leitura.modelo} · ${dataCurta(leitura.criado_em, true) || 'data desconhecida'}`;
  const vencida = leitura.vencida
    ? ` <span class="pilula">desatualizada</span><button class="btn link mini" data-gerar-leituras="1">Atualizar</button>` : '';
  const verJson = json && leitura.base
    ? `<details class="base-json"><summary>Ver base (JSON)</summary><pre>${esc(JSON.stringify(leitura.base, null, 2))}</pre></details>` : '';
  return `<div class="leitura">
    <p class="leitura-texto">${esc(leitura.texto)}</p>
    <div class="assin">Luzia · ${esc(data)}
      <span class="info-base" tabindex="0" role="img" aria-label="${esc(dica)}" data-dica="${esc(dica)}">${ic('info', 'p')}</span>${vencida}
    </div>${verJson}
  </div>`;
}

// ------------------------------------------------------------------ peças de avanço e prisma
const tipoDe = (a) => {
  const t = String(a?.tipo || 'praticar').toLowerCase();
  return ['praticar', 'explicar', 'estudar', 'explorar'].includes(t) ? t : 'praticar';
};
const quadradoTipo = (a) => {
  const t = tipoDe(a);
  return `<span class="tipo ${a.estado === 'conquistado' ? 'conquistado' : t}" title="${esc(a.tipo || t)}">${ic(a.estado === 'conquistado' ? 'check' : t, 'p')}</span>`;
};
// Origem da centelha, como etiqueta curta: da sessão (o que era o lampejo), da triagem ou de uma entrega passada.
function origemTag(a) {
  const o = String(a?.origem || '').toLowerCase();
  if (a?.entrega_id || (o === 'entrega' && !a?.da_triagem)) return 'da entrega';
  if (a?.da_triagem || o === 'rota' || o === 'triagem' || o === 'entrega') return 'da triagem';
  if (['sessão', 'sessao', 'guardada', 'lampejo', 'cartao'].includes(o)) return 'da sessão';
  return '';
}
const valorAvanco = (a) => (a.estado === 'conquistado' ? `+${a.lm_ganho} lm` : `${a.valor_lm} lm`);
const tentativaTxt = (a) => (a.tentativas && a.estado !== 'conquistado' ? `${a.tentativas + 1}ª tentativa` : '');

// Cartão de 2 linhas: título; embaixo [tipo] prisma · min à esquerda e lúmens à direita. Pílula só quando não é sugerido.
function cartaoAvanco(a, { semEstado = false } = {}) {
  const pilulas = [];
  if (!semEstado && a.estado === 'em_andamento') pilulas.push('<span class="pilula and">Em andamento</span>');
  if (!semEstado && a.estado === 'na_fila') pilulas.push('<span class="pilula fila">Na fila</span>');
  if (tentativaTxt(a)) pilulas.push(`<span class="pilula">${tentativaTxt(a)}</span>`);
  const prisma = a.skill_plano || a.skill;
  const rotulo = `${a.titulo}, ${tipoDe(a)}, ${nomeCurto(prisma)}, ${a.duracao_min || '?'} minutos, ${a.estado === 'conquistado' ? `ganhou ${a.lm_ganho}` : a.valor_lm} lúmens${a.estado !== 'sugerido' ? `, ${ESTADO[a.estado] || ''}` : ''}`;
  return `<button class="avanco ${esc(a.estado)}" data-avanco="${esc(a.id)}" aria-label="${esc(rotulo)}">
    <span class="topo"><b>${esc(a.titulo)}</b>${pilulas.join('')}</span>
    <span class="pe"><span class="meta">${quadradoTipo(a)}<span title="${esc(prisma)}">${curto(prisma)}</span><span class="sep"></span><span>${a.duracao_min || '?'} min</span></span><span class="lm ${a.estado === 'conquistado' ? 'ok' : ''}">${valorAvanco(a)}</span></span>
  </button>`;
}

// Avanço compacto (detalhe da entrega): ícone, título, prisma · min · dimensão e lúmens.
function miniAvanco(a) {
  const prisma = a.skill_plano || a.skill;
  return `<button class="mini-av" data-avanco="${esc(a.id)}">${quadradoTipo(a)}<span class="mini-txt"><b>${esc(a.titulo)}</b>
    <span class="meta"><span title="${esc(prisma)}">${curto(prisma)}</span><span class="sep"></span><span>${a.duracao_min || '?'} min</span>${a.dimensao ? `<span class="sep"></span><span>prova ${esc(a.dimensao)}</span>` : ''}</span></span>
    <span class="lm">${valorAvanco(a)}</span></button>`;
}

// `contexto`: 'hoje' (um primário + copiar como ícone) ou 'gaveta' (mesmos botões e uma dica curta).
function botoesAvanco(a, contexto = 'gaveta') {
  if (a.estado === 'descartado') {
    return `<div class="acoes-bt"><button class="btn sec" data-restaurar="${esc(a.id)}">${ic('restaurar')}Restaurar</button></div>`;
  }
  const naFila = (E.fila || []).includes(a.id);
  const agente = esc(nomeAgente());
  if (a.estado === 'conquistado') {
    const pode = [2, 3].includes(a.nota) && !a.revisitas;
    return pode ? `<div class="acoes-bt"><button class="btn prim" data-enviar="${esc(a.id)}" ${naFila ? 'disabled' : ''} title="Abre na sua próxima mensagem no chat">${ic(naFila ? 'check' : 'enviar')}${naFila ? 'Na fila' : 'Revisitar'}</button></div>
      <p class="dica">Você levou ${a.lm_ganho} de ${a.valor_lm} lm. A revisita vale os ${a.valor_lm - a.lm_ganho} restantes.</p>` : '';
  }
  const rotulo = naFila ? `Na fila do ${agente}` : a.estado === 'em_andamento' ? 'Continuar' : `Acender no ${agente}`;
  const dica = contexto === 'gaveta'
    ? `<p class="dica">Abre na sua próxima mensagem no chat${E.agente === 'claude-code' ? `, ou digite <b>/luzia:fazer ${esc(a.id)}</b>` : ''}.</p>` : '';
  return `<div class="acoes-bt">
    <button class="btn prim" data-enviar="${esc(a.id)}" ${naFila ? 'disabled' : ''} title="Abre na sua próxima mensagem no chat">${ic(naFila ? 'check' : 'enviar')}${rotulo}</button>
    <button class="btn ico" data-copiar="${esc(a.id)}" aria-label="Copiar prompt" title="Copiar prompt">${ic('copiar')}</button>
  </div>${dica}`;
}

function motivoValor(a) {
  const prio = (a.conta || []).find((c) => c[0] === 'prioridade');
  const lac = (a.conta || []).find((c) => c[0] === 'lacuna');
  const nomeP = curto(a.skill_plano || a.skill);
  if (prio && prio[2] === 10) return `Vale mais porque ${nomeP} é uma das suas maiores lacunas (${esc(lac?.[1] || '')}).`;
  if (prio && prio[2] === 0) return `Vale menos porque ${nomeP} já está na sua meta.`;
  return `Centelha de ${nomeP}, uma lacuna da sua trajetória (${esc(lac?.[1] || '')}).`;
}

function abrirAvanco(id) {
  const a = avancoPorId(id);
  if (!a) return;
  const t = tipoDe(a);
  const conta = (a.conta || []).map(([r, d, v]) => `<span>${esc(r)} <small>(${esc(d)})</small></span><b>+${v}</b>`).join('');
  const hist = (a.historico || []).slice(-5).reverse().map((h) => `<li>${esc(dataCurta(h.quando))} · ${esc(h.evento)}${h.nota != null ? ` · nota ${h.nota}/4` : ''}${h.lm ? ` · +${h.lm} lm` : ''}${h.motivo ? ` · ${esc(h.motivo)}` : ''}${h.onde ? ` · ${esc(h.onde)}` : ''}</li>`).join('');
  const motivos = Object.entries(E.regras.motivos || {}).map(([k, v]) => `<button class="btn sec mini" data-descartar="${esc(a.id)}" data-motivo="${esc(k)}">${esc(v)}</button>`).join('');
  const origem = a.entrega_id ? `<span class="tag">${ic('pacote', 'p')}Entrega #${esc(a.entrega_id)}${a.dimensao ? ` · prova ${esc(a.dimensao)}` : ''}</span>` : '';
  const estadoPil = a.estado === 'em_andamento' ? '<span class="pilula and">Em andamento</span>'
    : a.estado === 'na_fila' ? '<span class="pilula fila">Na fila</span>'
      : a.estado !== 'sugerido' ? `<span class="pilula">${esc(ESTADO[a.estado] || a.estado)}</span>` : '';
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <div class="etiquetas">
      <span class="tipo-chip tipo-${t}">${ic(t, 'p')}${esc(t)}</span>
      <span class="tag">${rotuloPrisma(a.skill_plano || a.skill)}</span>
      <span class="tag">${a.duracao_min} min</span>
      <span class="tag luz">${valorAvanco(a)}</span>
      ${origemTag(a) ? `<span class="tag refl">${origemTag(a)}</span>` : ''}
      ${estadoPil}${tentativaTxt(a) ? `<span class="pilula">${tentativaTxt(a)}</span>` : ''}
    </div>
    <h3>${esc(a.titulo)}</h3>
    <p>${esc(a.por_que)}</p>
    ${origem ? `<div class="etiquetas">${origem}</div>` : ''}
    <div class="gaveta-acoes">${botoesAvanco(a, 'gaveta')}</div>
    <h4>Passo a passo</h4><ol>${(a.como || []).map((p) => `<li>${esc(p)}</li>`).join('')}</ol>
    <h4>Conceitos</h4><div class="etiquetas">${(a.conceitos || []).map((c) => `<span class="tag">${esc(c)}</span>`).join('')}</div>
    <h4>Onde olhar</h4><p class="lacuna">${esc(a.onde_explorar)}</p>
    <details class="recolhido"><summary>${ic('baixo', 'p')}Por que ${a.valor_lm} lm</summary>
      <p class="lacuna">${motivoValor(a)}</p>
      <div class="conta">${conta}<span class="total">Nota 4 = 100% · 3 = 75% · 2 = 50%</span><b class="total">${a.valor_lm} lm</b></div></details>
    <details class="recolhido"><summary>${ic('baixo', 'p')}Ver prompt</summary><pre class="prompt">${esc(a.prompt_completo)}</pre></details>
    ${hist ? `<details class="recolhido"><summary>${ic('baixo', 'p')}Histórico</summary><ul class="lacuna lista">${hist}</ul></details>` : ''}
    ${['conquistado', 'descartado'].includes(a.estado) ? '' : `<details class="recolhido descartar"><summary>Descartar…</summary><div class="motivos">${motivos}</div></details>`}`;
  $('#gaveta').hidden = false;
}

function abrirPrisma(nome) {
  const s = listaPrismas().find((x) => x.nome === nome);
  if (!s) return;
  const doPrisma = listaAvancos().filter((a) => (a.skill_plano || a.skill) === nome && a.estado !== 'descartado');
  const subidas = (s.niveis_conquistados || []).map((h) => `<li>${esc(dataCurta(h.quando))} · nível ${h.para} (${h.lm} lm, ${h.luz_propria}% própria)</li>`).join('');
  const fatosPrisma = `nível ${s.nivel} de ${s.meta ?? s.alvo}, ${s.lm || 0} lm (${s.luz_propria || 0}% própria), ${plural(doPrisma.length, 'centelha')}`;
  const nv = s.nivel ?? s.voce;
  const temSubtitulo = nomeCurto(nome) !== nome;
  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <span class="pilula ${s.estado === 'arquivado' ? '' : 'and'}">${s.estado === 'arquivado' ? 'arquivado' : 'ativo'}</span>
    <h3>${curto(nome)}</h3>
    ${temSubtitulo ? `<p class="subtitulo">${esc(nome)}</p>` : ''}
    <p>${espectroPrisma(s, false)}</p>
    <p class="frase-nivel">${s.autoavaliada
      ? `Nível <b>${nv}</b> de 5 · meta <b>${s.meta ?? s.alvo}</b>`
      : `Estimado em <b>${nv}</b> pela triagem · meta <b>${s.meta ?? s.alvo}</b>. <button class="btn link" data-ir="ajustes">Declarar meu nível</button>`}
      ${s.autoavaliada && Number(s.sugere) !== Number(nv) ? `<br><small>A Luzia estimaria ${s.sugere} (losango lilás). Você decide.</small>` : ''}</p>
    <h4>Progresso até o próximo nível</h4>${s.estado === 'arquivado' ? `<p class="lacuna">${s.lm || 0} lm preservados</p>` : barraNivel(s)}
    <h4>Centelhas</h4><div class="grade">${doPrisma.map((a) => cartaoAvanco(a)).join('') || '<span class="vazio">Nenhuma centelha aberta.</span>'}</div>
    ${s.na_meta || s.estado === 'arquivado' ? '' : `<p style="margin-top:var(--e4)">${botaoAcender(s)}</p>`}
    <h4>Análise</h4>
    ${blocoLeitura(s.leitura, fatosPrisma, true)}
    ${s.evidencia ? `<details class="recolhido"><summary>${ic('baixo', 'p')}Evidência da triagem</summary>${blocoLeitura({ texto: s.evidencia, alvo_tipo: 'triagem', modelo: E.triagem_modelo?.modelo || 'modelo desconhecido', criado_em: E.triagem_modelo?.quando || '' }, `triagem: currículo, commits e histórico autorizados${E.triagem_modelo?.mascarado ? ' (mascarados antes do envio ao modelo)' : ''}`)}</details>` : ''}
    ${subidas ? `<details class="recolhido"><summary>${ic('baixo', 'p')}Níveis conquistados</summary><ul class="lacuna lista">${subidas}</ul></details>` : ''}`;
  $('#gaveta').hidden = false;
}

// "Ver tudo" de uma entrega: fatos, fonte, áreas, termos, leitura com a base em JSON e todos os lúmens e avanços.
async function abrirEntregaDetalhe(id) {
  const det = await api(`/api/entrega?id=${encodeURIComponent(id)}`);
  if (det.erro) {
    toast(det.erro);
    return;
  }
  const f = det.fatos || {};
  const prismasTags = (det.prismas || []).map((p) => {
    const termos = (p.termos || []).length ? ` · termos: ${p.termos.map(esc).join(', ')}` : '';
    return `<span class="tag refl" title="${esc(p.prisma)}">${curto(p.prisma)}${termos}</span>`;
  }).join('') || '<span class="vazio">Nenhum prisma nos caminhos ou mensagens.</span>';
  const lms = (det.lumens_ligados || []).map((l) =>
    `<li><span class="lm ${l.luz === 'refletida' ? 'refl' : ''}">+${l.lm}</span> ${curto(l.prisma || l.skill)} · ${esc(legFonte(l.fonte))} · ${esc(dataCurta(l.quando))}</li>`
  ).join('');
  const feitos = (det.avancos_feitos || []).map(miniAvanco).join('');
  const uteis = (det.avancos_uteis || []).map(miniAvanco).join('');
  const resumoFatos = `${plural(f.commits ?? 1, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}`;

  $('#gaveta-corpo').innerHTML = `
    <button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>
    <span class="pilula">Entrega #${esc(det.id)}</span>
    <h3>${esc(det.titulo)}</h3>
    <div class="etiquetas">
      <span class="tag">${esc(det.fonte || 'git')}</span>
      ${(det.ids || []).map((i) => `<span class="tag">#${esc(i)}</span>`).join('')}
      <span class="tag">${esc(periodoCurto(f.inicio, f.fim) || '—')} · ${plural(f.duracao_dias || 1, 'dia')}</span>
      <span class="tag">${plural(f.commits || 1, 'commit')}</span>
      <span class="tag">${plural(f.arquivos || 0, 'arquivo')}</span>
      <span class="tag">+${numero(f.linhas || 0)} linhas</span>
      ${(f.areas || []).map((ar) => `<span class="tag">${esc(ar)}</span>`).join('')}
    </div>
    <h4>Prismas</h4>
    <div class="etiquetas">${prismasTags}</div>
    <div style="margin-top:var(--e4)">${botaoAcenderEntrega(det.id, (det.propriedade || {}).dimensoes, det.avancos_feitos)}</div>
    <h4>Análise</h4>
    ${blocoLeitura(det.leitura, resumoFatos, true)}
    <h4>Lúmens no período · ${(det.lumens_ligados || []).length}</h4>
    ${lms ? `<ul class="lacuna lista">${lms}</ul>` : '<p class="vazio">Nenhum lúmen no período desta entrega.</p>'}
    ${feitos ? `<h4>Feitos para esta entrega</h4>${feitos}` : ''}
    <h4>Centelhas que ajudam</h4>
    ${uteis || '<span class="vazio">Nenhuma centelha aberta para estes prismas.</span>'}`;
  $('#gaveta').hidden = false;
}

// P3/P4 sem evidência e sem avanço aberto que as prove: oferece acender 2 avanços ligados a esta entrega.
function botaoAcenderEntrega(id, dimensoes, feitos, classe = 'prim') {
  const lacunas = ['P3', 'P4'].filter((d) => !(dimensoes || {})[d]);
  const abertas = new Set((feitos || []).filter((a) => a && ABERTOS.includes(a.estado)).map((a) => a.dimensao));
  if (!id || !lacunas.length || lacunas.every((d) => abertas.has(d))) return '';
  return `<button class="btn ${classe}" data-acender-entrega="${esc(id)}" title="Acende 2 centelhas curtas ligadas a esta entrega">${ic('raio')}Provar ${lacunas.join(' e ')}</button>`;
}

// O que ainda falta para subir de nível, só o que falta (as regras ficam em "Como subir de nível").
function faltaNivel(s) {
  if (s.pronto) return 'pronto';
  const lim = s.limiar || E.regras.limiar;
  const falta = [];
  if ((s.lm || 0) < lim) falta.push(`${lim - (s.lm || 0)} lm`);
  if ((s.luz_propria || 0) < E.regras.min_propria) falta.push(`luz própria (${s.luz_propria || 0}% de ${E.regras.min_propria}%)`);
  if ((s.avancos_conquistados ?? 0) < (E.regras.min_avancos || 1)) falta.push(plural((E.regras.min_avancos || 1) - (s.avancos_conquistados ?? 0), 'centelha'));
  return falta.length ? 'falta ' + falta.join(' · ') : 'pronto';
}

function barraNivel(s) {
  if (s.na_meta) return `<div class="info"><span>${ic('check', 'p')} na meta</span><span>nível ${s.nivel} de ${s.meta ?? s.alvo}</span></div>`;
  const lim = s.limiar || E.regras.limiar;
  const p = Math.min(100, (100 * (s.propria || 0)) / lim);
  const r = Math.min(100 - p, (100 * (s.refletida || 0)) / lim);
  return `<div class="barra-nivel" role="img" aria-label="${s.lm || 0} de ${lim} lúmens, ${s.luz_propria || 0}% própria"><span class="p" style="width:${p}%"></span><span class="r" style="width:${r}%"></span></div>
    <div class="info"><span class="${s.pronto ? 'pronto' : ''}">${esc(faltaNivel(s))}</span><span>${s.lm || 0}/${lim} lm</span></div>`;
}

function trajetoriaHero() {
  const r = E.trajetoria?.resumo || E.rota || {};
  const total = r.niveis_total ?? 0;
  const feitos = r.niveis_feitos ?? 0;
  const rot = E.perfil.rotulos || [];
  return `<div class="bloco trilha">
    <span class="sobre-linha">Trajetória · ${esc(rot[0] || 'Hoje')} → ${esc(rot[1] || 'Meta')}</span>
    <div class="grande">${feitos} <small>de ${total} níveis</small></div>
    <div class="trajetoria-linha" role="img" aria-label="${feitos} de ${total} níveis"><span class="luz" style="width:${Math.max(2, r.pct || 0)}%"></span></div>
    <div class="nums"><span><span class="lm">${numero(r.lm_total)} lm</span> · ${r.luz_propria || 0}% própria</span><button class="btn link mini" data-ir="trajetoria">Ver</button></div>
    <h4 title="Laranja: luz própria (você demonstrou). Lilás: luz refletida (o agente aplicou).">Lúmens recentes</h4>
    <div class="feed" id="feed"></div>
  </div>`;
}

function prontos() {
  return prismasAtivos().filter((s) => s.pronto && !s.na_meta).map((s) => `<div class="aviso" role="status">${ic('subir')}
    <b title="${esc(s.nome)}">${curto(s.nome)} pronto para o nível ${s.proximo}</b>
    <span class="meta"><span class="lm">${s.lm} lm</span><span class="sep"></span><span>${s.luz_propria}% própria</span></span>
    <button class="btn prim mini" data-subir="${esc(s.nome)}">Subir para ${s.proximo}</button></div>`).join('');
}

// ------------------------------------------------------------------ telas
function cabecalho() {
  $('#nav').innerHTML = TELAS.map(([id, nome]) => `<button data-tela="${id}">${ic(id)}${nome}</button>`).join('');
  const m = MODOS[E.modo];
  $('#selo').innerHTML = `<span class="ponto ${esc(E.modo)}"></span>${esc(m?.[1] || E.modo_nome || E.modo)}`;
  $('#selo').title = m?.[3] || E.modo_nome || '';
}

function telaHoje() {
  const p = E.proxima;
  const abertos = listaAvancos().filter((a) => ABERTOS.includes(a.estado));
  const outros = abertos.filter((a) => !p || a.id !== p.id).slice(0, 3);
  const aviso = prontos() || (E.autoavaliada ? '' : `<div class="aviso" role="status">${ic('info')}<span>Seu nível ainda é uma estimativa.</span><button class="btn link mini" data-ir="ajustes">Declarar</button></div>`);
  let destaque;
  if (p) {
    const prisma = p.skill_plano || p.skill;
    destaque = `<div class="bloco destaque">
      <span class="sobre-linha">${p.estado === 'em_andamento' ? 'Continue' : 'Próximo passo'}</span>
      <h3><button class="titulo-link" data-avanco="${esc(p.id)}">${esc(p.titulo)}</button></h3>
      <p>${esc(truncar(p.por_que, 120))}</p>
      <div class="meta">${quadradoTipo(p)}<span>${esc(tipoDe(p))}</span>${origemTag(p) ? `<span class="sep"></span><span>${origemTag(p)}</span>` : ''}<span class="sep"></span><span title="${esc(prisma)}">${curto(prisma)}</span><span class="sep"></span><span>${p.duracao_min} min</span><span class="sep"></span><span class="lm">${p.valor_lm} lm</span></div>
      <div class="acoes-destaque">${botoesAvanco(p, 'hoje')}</div>
    </div>`;
  } else {
    destaque = `<div class="bloco destaque"><span class="sobre-linha">Tudo em dia</span><h3>Nenhuma centelha aberta</h3>${botaoAcender(maiorLacuna(), 'prim')}</div>`;
  }
  $('#hoje').innerHTML = `
    ${aviso}
    <div class="hoje-grade">${destaque}${trajetoriaHero()}</div>
    ${outros.length ? `<h4 class="secao">Também abertas <button class="btn link mini" data-ir="avancos">Ver todos (${abertos.length})</button></h4>
    <div class="grade">${outros.map((a) => cartaoAvanco(a)).join('')}</div>` : ''}`;
}

function feed() {
  const el = $('#feed');
  if (!el) return;
  el.innerHTML = (E.lumens || []).slice(0, 5).map((l) => `<div class="feed-lm" title="${l.luz === 'refletida' ? 'luz refletida' : 'luz própria'}"><span class="lm ${l.luz === 'refletida' ? 'refl' : ''}">+${l.lm}</span>
      <span><span title="${esc(l.skill)}">${curto(l.skill)}</span> · ${esc(legFonte(l.fonte))}</span><small>${esc(String(l.quando || '').slice(11, 16))}</small></div>`).join('')
    || '<div class="vazio">Seus lúmens aparecem aqui.</div>';
}

function renderFormPedido() {
  if (!mostrarFormPedido) return '';
  const todosNomes = listaPrismas().map((p) => p.nome);
  const seletorExistente = ['mudar_meta', 'arquivar', 'reativar'].includes(tipoPedidoForm);
  const opcoesPrisma = todosNomes.map((n) => `<option value="${esc(n)}">${curto(n)}</option>`).join('');
  const opcao = (v, rot) => `<option value="${v}" ${tipoPedidoForm === v ? 'selected' : ''}>${rot}</option>`;
  return `<div class="bloco form-pedido">
    <div class="pedido-cab">
      <b>Mudar trajetória</b>
      <button class="btn link mini" data-abrir-pedido-form="0">${ic('fechar', 'p')}Fechar</button>
    </div>
    <div class="campos">
      <label>O que mudar
        <select id="ped-tipo">
          ${opcao('incluir', 'Incluir prisma')}${opcao('mudar_meta', 'Mudar meta')}${opcao('arquivar', 'Arquivar prisma')}${opcao('reativar', 'Reativar prisma')}
        </select>
      </label>
      ${seletorExistente
        ? `<label>Prisma<select id="ped-prisma">${opcoesPrisma}</select></label>`
        : `<label>Nome do prisma<input id="ped-prisma" placeholder="ex.: Mensageria"></label>`}
      <label>Por quê?<input id="ped-motivo" placeholder="ex.: o time vai adotar mensageria"></label>
      ${['incluir', 'mudar_meta'].includes(tipoPedidoForm)
        ? `<label>Meta (1 a 5)<input id="ped-meta" type="number" min="1" max="5" placeholder="ex.: 4"></label>`
        : ''}
    </div>
    <p class="dica">A Luzia propõe; você decide. Nada se perde.</p>
    <div class="acoes-bt" style="margin-top:var(--e3)">
      <button class="btn prim" id="ped-enviar">${ic('enviar')}Pedir proposta</button>
    </div>
  </div>`;
}

const pilulaPedido = (p, aberto) => `<span class="pilula ${aberto ? 'fila' : ''}">${esc(p.estado)}</span>`;

// Pedido `dividir` (um prisma = uma habilidade): as partes com nível e meta herdados e para onde vai cada avanço.
function renderCardDividir(p, prop, aberto) {
  const partes = prop.partes || [];
  const nomes = partes.map((x) => x.nome);
  const avs = prop.avancos || [];
  const opcoes = (atual) => nomes.map((n) => `<option value="${esc(n)}" ${n === atual ? 'selected' : ''}>${esc(n)}</option>`).join('');
  return `<div class="pedido-card ${esc(p.estado)}">
    <div class="pedido-cab">
      <span><b title="${esc(p.prisma)}">Dividir ${curto(p.prisma)}</b> <small class="discreto">#${p.id} · ${esc(dataCurta(p.criado_em))}</small></span>
      ${pilulaPedido(p, aberto)}
    </div>
    <p class="lacuna">Cada parte herda ${prop.nivel_partida ?? '?'} → meta ${prop.meta ?? '?'}. O prisma antigo é arquivado com os lúmens.</p>
    <div class="campos">
      ${partes.map((x, i) => aberto
        ? `<label>Habilidade ${i + 1}<input data-div-parte="${p.id}" value="${esc(x.nome)}"></label>`
        : `<span class="tag luz">${esc(x.nome)} · ${x.nivel} → meta ${x.meta}</span>`).join('')}
    </div>
    ${avs.length ? `<ul class="lacuna lista">${avs.map((a) => `<li>${esc(a.titulo)} <small>(${esc(a.estado)})</small> → ${aberto
      ? `<select data-div-mover="${p.id}" data-avanco-id="${esc(a.id)}" aria-label="Para qual habilidade">${opcoes(a.para)}</select>`
      : `<b>${esc(a.para)}</b>`}</li>`).join('')}</ul>` : ''}
    ${aberto ? `<div class="pedido-ajuste">
      <button class="btn prim mini" data-pedido-aceitar="${p.id}">${ic('check', 'p')}Aceitar</button>
      <button class="btn sec mini" data-pedido-dividir-ajustar="${p.id}">Ajustar</button>
      <button class="btn link mini" data-pedido-recusar="${p.id}">Recusar</button>
    </div>` : ''}
  </div>`;
}

function renderCardPedido(p) {
  const prop = p.proposta || {};
  const aberto = ['aberto', 'proposto'].includes(p.estado);
  const nvSug = prop.nivel_partida ?? 1;
  const metaSug = prop.meta ?? 4;
  // A leitura guardada do pedido (texto, modelo e data de quando foi gerada), nunca o modelo configurado agora.
  const comAnalise = ['incluir', 'mudar_meta'].includes(p.tipo) && (prop.nivel_partida != null || prop.meta != null);
  if (p.tipo === 'dividir') return renderCardDividir(p, prop, aberto);
  const ajustavel = ['incluir', 'mudar_meta'].includes(p.tipo);
  const ajustando = ajustandoPedido === p.id;

  return `<div class="pedido-card ${esc(p.estado)}">
    <div class="pedido-cab">
      <span><b title="${esc(p.prisma)}">${esc(TIPO_PEDIDO_NOME[p.tipo] || p.tipo)} ${curto(p.prisma)}</b> <small class="discreto">#${p.id} · ${esc(dataCurta(p.criado_em))}</small></span>
      ${pilulaPedido(p, aberto)}
    </div>
    ${p.motivo ? `<p class="lacuna">${esc(p.motivo)}</p>` : ''}
    ${prop && (prop.nivel_partida != null || prop.meta != null) ? `
      <div class="etiquetas">
        <span class="tag luz">Proposta: ${nvSug} → meta ${metaSug}</span>
        ${(prop.palavras_chave || []).map((w) => `<span class="tag">${esc(w)}</span>`).join('')}
        ${(prop.acoes || []).length ? `<span class="tag">${plural(prop.acoes.length, 'centelha inicial', 'centelhas iniciais')}</span>` : ''}
      </div>` : ''}
    ${comAnalise ? blocoLeitura(p.leitura, `pedido #${p.id} · ${nomeCurto(p.prisma)}`, false, prop.leitura_indisponivel) : ''}
    ${aberto ? `<div class="pedido-ajuste">
      <button class="btn prim mini" data-pedido-aceitar="${p.id}">${ic('check', 'p')}Aceitar</button>
      ${ajustavel && ajustando ? `
        <label>Nível <input type="number" min="0" max="5" value="${nvSug}" id="aj-nv-${p.id}"></label>
        <label>Meta <input type="number" min="1" max="5" value="${metaSug}" id="aj-mt-${p.id}"></label>
        <button class="btn sec mini" data-pedido-ajustar="${p.id}">Recalcular</button>
        <button class="btn link mini" data-ajustar-pedido="0">Cancelar</button>` : ''}
      ${ajustavel && !ajustando ? `<button class="btn link mini" data-ajustar-pedido="${p.id}">Ajustar</button>` : ''}
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
  const rot = E.perfil.rotulos || [];
  const ritmoSem = E.ritmo?.avancos_semana || 1;

  $('#trajetoria').innerHTML = `
    <div class="cab-tela">
      <div>
        <h2>Trajetória</h2>
        <p>v${versao} · ${esc(rot[0] || 'Hoje')} → ${esc(rot[1] || 'Meta')}</p>
        <p class="ritmo">${plural(ritmoSem, 'centelha')} por semana te leva até ${esc(rot[1] || 'a meta')} em ~${E.ritmo?.meses || 12} meses</p>
      </div>
      <div class="acoes-bt">
        ${ativos.some((s) => (s.divisao || []).length) ? `<button class="btn sec mini" data-dividir-todos="1">Separar prismas compostos</button>` : ''}
        <button class="btn prim mini" data-abrir-pedido-form="1">${ic('enviar', 'p')}Mudar trajetória</button>
      </div>
    </div>
    ${bannerLeituras()}
    <details class="como"><summary>${ic('info', 'p')}Como subir de nível</summary>
      <p>${E.regras.limiar} lm · ${E.regras.min_propria}% própria · ${plural(E.regras.min_avancos || 1, 'centelha acesa', 'centelhas acesas')} · você confirma</p></details>
    ${renderFormPedido()}
    <div class="legenda">
      <span title="Luz própria: você demonstrou"><i class="propria"></i>própria</span>
      <span title="Luz refletida: o agente aplicou"><i class="refletida"></i>refletida</span>
      <span title="Borda na faixa: a meta do prisma"><i class="meta"></i>meta</span>
    </div>
    <div class="prismas-lista">
      ${ativos.map((s) => `<div class="prisma-card ${s.pronto && !s.na_meta ? 'pronta' : ''} ${s.na_meta ? 'meta-ok' : ''}">
          <button class="prisma-topo" data-prisma="${esc(s.nome)}" aria-label="${esc(s.nome)}: ${esc(s.na_meta ? 'na meta' : faltaNivel(s))}">
            <span class="nome"><b title="${esc(s.nome)}">${curto(s.nome)}</b>${espectroPrisma(s)}</span>
            <span>${barraNivel(s)}</span>
            <span class="lado">${s.pronto && !s.na_meta ? `<span class="btn prim mini" data-subir="${esc(s.nome)}">${ic('subir', 'p')}Subir para ${s.proximo}</span>` : ic('seta', 'p')}</span>
          </button>
          ${(s.divisao || []).length ? `<p class="dica">Junta assuntos: ${s.divisao.map(esc).join(', ')}. <button class="btn sec mini" data-dividir-prisma="${esc(s.nome)}">Separar em habilidades</button></p>` : ''}
        </div>`).join('')}
    </div>

    ${pedidos.length ? `<h4 class="secao">Pedidos</h4>
    <div class="pedidos-lista">${pedidos.map(renderCardPedido).join('')}</div>` : ''}

    ${arquivados.length ? `
      <details class="recolhido secao-det"><summary>${ic('baixo', 'p')}Arquivados (${arquivados.length}) · lúmens preservados</summary>
      <div class="prismas-lista">
        ${arquivados.map((s) => `<div class="prisma-card">
          <div class="prisma-topo arquivado">
            <span class="nome"><b title="${esc(s.nome)}">${curto(s.nome)}</b>${espectroPrisma(s)}</span>
            <span class="lacuna">${s.lm || 0} lm preservados</span>
            ${pedidos.some((p) => p.tipo === 'dividir' && p.estado === 'aceito' && p.prisma === s.nome)
              ? '<span class="lacuna">dividido em habilidades</span>'
              : `<button class="btn sec mini" data-reativar-prisma="${esc(s.nome)}">Reativar</button>`}
          </div>
        </div>`).join('')}
      </div></details>
    ` : ''}

    <details class="recolhido secao-det"><summary>${ic('baixo', 'p')}Versões (${versoes.length})</summary>
    <div class="versoes-lista">
      ${versoes.map((v) => `<div class="versao-item">
        <span><b>v${v.numero}</b> · ${v.pedido_id ? `pedido #${esc(v.pedido_id)}` : esc(v.origem)} · ${esc(dataCurta(v.criada_em))}</span>
        <span>${plural((v.prismas || []).filter((p) => p.estado !== 'arquivado').length, 'prisma ativo', 'prismas ativos')}</span>
      </div>`).join('')}
    </div></details>`;
}

// Mantida para paridade com o chat (`avancos --estado`): o painel usa o segmentado e agrupa por estado.
function passaEstado(a, est) {
  if (est === 'todos') return true;
  if (est === 'abertos') return ABERTOS.includes(a.estado);
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
  if (!['abertos', 'conquistado', 'todos'].includes(filtroEstado)) filtroEstado = 'abertos';
  const segmentos = [['abertos', 'Abertas'], ['conquistado', 'Acesas'], ['todos', 'Todas']];
  const tipos = ['praticar', 'explicar', 'estudar', 'explorar'];
  const outrosFiltros = (a) => passaPrisma(a, filtroPrisma) && passaTipo(a, filtroTipo);
  const cont = (k) => todos.filter((a) => passaEstado(a, k) && outrosFiltros(a)).length;
  const filtrados = todos.filter((a) => passaEstado(a, filtroEstado) && outrosFiltros(a));

  let lista;
  if (!filtrados.length) {
    lista = `<div class="vazio-bloco"><span>Nada com esses filtros.</span> <button class="btn link mini" data-limpar-filtros="1">Limpar filtros</button></div>`;
  } else if (filtroEstado === 'conquistado') {
    lista = `<div class="grade">${filtrados.map((a) => cartaoAvanco(a, { semEstado: true })).join('')}</div>`;
  } else {
    lista = GRUPOS.map(([est, nome]) => {
      const grupo = filtrados.filter((a) => a.estado === est);
      return grupo.length ? `<h4 class="grupo">${nome} · ${grupo.length}</h4><div class="grade">${grupo.map((a) => cartaoAvanco(a, { semEstado: true })).join('')}</div>` : '';
    }).join('');
  }

  $('#avancos').innerHTML = `
    <div class="cab-tela"><h2>Centelhas</h2></div>
    <div class="filtros">
      <div class="seg" role="group" aria-label="Estado">
        ${segmentos.map(([k, rot]) => `<button data-filtro-estado="${k}" aria-pressed="${filtroEstado === k}">${rot}<small>${cont(k)}</small></button>`).join('')}
      </div>
      <label class="menu"><span>Prisma:</span>
        <select data-filtro-select="prisma" aria-label="Filtrar por prisma">
          <option value="todos">todos</option>
          ${listaPrismas().map((p) => `<option value="${esc(p.nome)}" ${filtroPrisma === p.nome ? 'selected' : ''}>${curto(p.nome)}</option>`).join('')}
        </select>${ic('baixo', 'p')}</label>
      <label class="menu"><span>Tipo:</span>
        <select data-filtro-select="tipo" aria-label="Filtrar por tipo">
          <option value="todos">todos</option>
          ${tipos.map((t) => `<option value="${t}" ${filtroTipo === t ? 'selected' : ''}>${t}</option>`).join('')}
        </select>${ic('baixo', 'p')}</label>
    </div>
    ${lista}`;
}

// P2 em palavras: o que reduziu a nota (a fórmula completa fica no title).
function baseHumana(k, d) {
  if (k !== 'P2' || !d.base) return d.base || '';
  const pen = [...String(d.base).matchAll(/−\s*(\d+)\s*\(([^)]+)\)/g)].filter((m) => Number(m[1]) > 0).map((m) => m[2]);
  return pen.length ? `${pen.join(' e ')} reduzem a nota` : 'entrega focada';
}

function dimsMedidas(e) {
  const ks = ['P1', 'P2', 'P3', 'P4'].filter((k) => (e.dimensoes || {})[k]);
  if (!ks.length) return '';
  if (ks.length === 4) return 'P1 a P4';
  return ks.length === 1 ? ks[0] : `${ks.slice(0, -1).join(', ')} e ${ks[ks.length - 1]}`;
}

function cartaoEntrega(e) {
  const f = e.fatos || {};
  const aberta = entregasAbertas.has(String(e.id));
  const prismas = (e.prismas || []).map((p) => (typeof p === 'string' ? { prisma: p, termos: [] } : p));
  const pils = prismas.slice(0, 3).map((p) => `<span class="pilula" title="${esc(p.prisma)}${(p.termos || []).length ? ` · termos: ${esc(p.termos.join(', '))}` : ''}">${curto(p.prisma)}</span>`).join('')
    + (prismas.length > 3 ? `<span class="pilula" title="${esc(prismas.slice(3).map((p) => nomeCurto(p.prisma)).join(', '))}">+${prismas.length - 3}</span>` : '');
  const medidas = dimsMedidas(e);
  const ind = e.indice;
  const feitos = (e.avancos_feitos || []).map(avancoPorId).filter(Boolean);
  const uteis = (e.avancos_uteis || e.acoes || []).map(avancoPorId).filter(Boolean).filter((a) => a.estado !== 'descartado');

  const dims = ['P1', 'P2', 'P3', 'P4'].map((k) => {
    const d = (e.dimensoes || {})[k];
    if (!d) {
      return `<div class="dim sem"><span class="nome">${k} ${NOME_DIM[k]}</span><span class="v">—</span><span class="b"></span><span class="base">${FALTA_DIM[k]}</span></div>`;
    }
    const dica = `${d.tipo || ''}${d.base ? ` · ${d.base}` : ''}`;
    return `<div class="dim"><span class="nome">${k} ${NOME_DIM[k]} <small title="${esc(dica)}">${esc(String(d.tipo || '').split(' · ')[0])}</small></span><span class="v">${d.nota}</span>
      <span class="b"><i style="width:${Math.max(0, Math.min(100, d.nota))}%"></i></span><span class="base" title="${esc(d.base || '')}">${esc(baseHumana(k, d))}</span></div>`;
  }).join('');
  const lms = e.lumens_ligados || [];
  const ajuda = [...feitos.filter((a) => ABERTOS.includes(a.estado)), ...uteis.filter((a) => ABERTOS.includes(a.estado))]
    .filter((a, i, arr) => arr.findIndex((x) => x.id === a.id) === i).slice(0, 2);
  const feitosConq = feitos.filter((a) => a.estado === 'conquistado').slice(0, 2);

  return `<details class="entrega" data-entrega-id="${esc(e.id)}" ${aberta ? 'open' : ''}>
    <summary>
      <div class="entrega-resumo">
        <h3>${esc(e.titulo || e.tarefa)}</h3>
        <div class="meta"><span>${plural(f.duracao_dias || 1, 'dia')}</span><span class="sep"></span><span>${plural(f.commits ?? 1, 'commit')}</span><span class="sep"></span><span>${plural(f.arquivos ?? 0, 'arquivo')}</span><span class="sep"></span><span>+${numero(f.linhas ?? 0)} linhas</span></div>
        ${pils ? `<div class="prismas">${pils}</div>` : ''}
      </div>
      <div class="prop">
        <div class="num"><b>${ind == null ? '—' : `${ind}% seu`}</b><small>${ind == null ? 'sem medida ainda' : `${100 - ind}% do agente`}</small></div>
        <div class="medidor" role="img" aria-label="${ind == null ? 'propriedade sem medida' : `${ind}% seu, ${100 - ind}% do agente`}">${ind == null ? '' : `<i style="width:${ind}%"></i><i style="width:${100 - ind}%"></i>`}</div>
        <div class="acoes-prop">${medidas ? `<span class="pilula" title="${esc(e.base || '')}">${medidas}</span>` : '<span></span>'}<span class="ver"><span class="abre">Ver detalhe</span><span class="fecha">Fechar</span>${ic('baixo', 'p')}</span></div>
      </div>
    </summary>
    <div class="detalhe">
      <div>
        <h5>Propriedade</h5>
        <div class="dims">${dims}</div>
        <div class="prova">${botaoAcenderEntrega(e.id, e.dimensoes, feitos)}</div>
      </div>
      <div>
        <h5>Análise</h5>
        ${blocoLeitura(e.leitura, `${plural(f.commits ?? 1, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}`)}
        ${feitosConq.length ? `<h5>Feitos para esta entrega</h5>${feitosConq.map(miniAvanco).join('')}` : ''}
        ${ajuda.length ? `<h5>Centelhas que ajudam</h5>${ajuda.map(miniAvanco).join('')}` : ''}
        <p class="meta rodape-entrega"><span>${plural(lms.length, 'lúmen', 'lúmens')} no período</span>${f.inicio ? `<span class="sep"></span><span>${esc(periodoCurto(f.inicio, f.fim))}</span>` : ''}${e.id ? `<span class="sep"></span><button class="btn link mini" data-entrega-detalhe="${esc(e.id)}">Ver tudo</button>` : ''}</p>
      </div>
    </div>
  </details>`;
}

function telaEntregas() {
  const lista = (E.entregas || []).map(cartaoEntrega).join('');
  $('#entregas').innerHTML = `
    <div class="cab-tela"><div><h2>Entregas</h2><p>Quanto de cada entrega é seu</p></div></div>
    ${bannerLeituras()}
    <details class="como"><summary>${ic('info', 'p')}Como medimos</summary><ul>${(E.como_e_medido || []).map((l) => `<li>${esc(l)}</li>`).join('')}</ul></details>
    ${lista ? `${lista}<div class="mais-antigas"><button class="btn sec mini" data-ampliar-entregas="180">${ic('relogio', 'p')}Buscar mais antigas</button></div>` : semEntregas()}`;
}

// Sem entrega no git: só fatos (repositório, identidades, janela) e o que a pessoa pode fazer. Nunca as tarefas da IA.
function semEntregas() {
  const d = E.entregas_diagnostico || {};
  const ids = (d.identidades || []).map(esc).join(', ') || 'nenhum';
  const janela = d.janela_desde
    ? `desde ${esc(dataCurta(d.janela_desde))} · ${plural(d.commits_seus ?? 0, 'commit seu', 'commits seus')}`
    : 'ainda não lida';
  return `<div class="bloco entregas-diagnostico">
    <h3>Nenhuma entrega encontrada</h3>
    <ul class="lacuna lista">
      <li title="${d.repo_configurado ? '' : 'campo repo em private/entrada.json'}">Repositório: ${d.repo_configurado ? 'configurado' : 'não configurado'}</li>
      <li>E-mails do git: ${ids}</li>
      <li>Janela: ${janela}</li>
    </ul>
    <div class="acoes-bt" style="margin-top:var(--e4)">
      <button class="btn prim mini" data-ampliar-entregas="180" title="No chat: /luzia:entregas">${ic('relogio', 'p')}Buscar 180 dias</button>
    </div>
    <details class="recolhido add-identidade"><summary>Adicionar e-mail do git</summary>
      <div class="pedido-ajuste">
        <label>Nome ou e-mail do git <input type="text" id="ent-identidade" maxlength="120" autocomplete="off"></label>
        <button class="btn sec mini" id="ent-identidade-salvar">${ic('check', 'p')}Adicionar</button>
      </div>
    </details>
  </div>`;
}

let provEscolhido = null;
function secaoModelo() {
  const m = E.modelo;
  const prov = provEscolhido || m.provedor;
  const info = m.provedores[prov];
  const atual = prov === m.provedor;
  return `<div class="titulo"><h2>Modelo</h2><span>Em uso: ${esc(m.modelo)}</span></div>
    <div class="opcoes">${Object.entries(m.provedores).map(([k, v]) => `<button class="opcao ${prov === k ? 'ativo' : ''}" data-provedor="${k}" aria-pressed="${prov === k}">${ic('agente')}<span><b>${esc(v.nome)}</b><small>${v.chave_configurada ? 'com chave' : 'sem chave'}</small></span></button>`).join('')}</div>
    <div class="bloco" style="margin-top:var(--e3)">
      <div class="campos">
        ${(() => {
          const valor = atual ? m.modelo : (info.sugestoes[0] || '');
          const conhecido = info.sugestoes.includes(valor);
          const opcoes = info.sugestoes.map((s) => `<option value="${esc(s)}" ${s === valor ? 'selected' : ''}>${esc(s)}</option>`).join('');
          return `<label>Modelo<select id="m-select">${opcoes}<option value="__outro" ${conhecido ? '' : 'selected'}>Outro…</option></select></label>
            <label ${conhecido ? 'hidden' : ''} id="m-outro-l">Nome exato<input id="m-outro" value="${conhecido ? '' : esc(valor)}" placeholder="nome exato do modelo"></label>`;
        })()}
        ${info.base_url ? `<label>URL da API<input id="m-base" value="${esc(atual ? m.base_url : '')}" placeholder="ex.: http://localhost:11434/v1"></label>` : ''}
        <label>API key<input id="m-chave" type="password" autocomplete="off" placeholder="${info.chave_configurada ? 'Já salva. Deixe vazio para manter.' : 'Cole a chave'}"></label>
      </div>
      <p class="dica">Fica só no .env desta máquina.${atual && !m.sdk_instalado ? ` Falta o SDK: <b>pip install ${esc(m.pip)}</b>.` : ''}</p>
      <div class="acoes-bt"><button class="btn prim" id="m-salvar">${ic('check')}Salvar</button><button class="btn sec" id="m-testar">${ic('raio')}Testar</button></div>
    </div>`;
}

function telaAjustes() {
  const opcao = (grupo, chave, [icone, titulo, desc], ativo) =>
    `<button class="opcao ${ativo ? 'ativo' : ''}" data-${grupo}="${chave}" aria-pressed="${!!ativo}">${ic(icone)}<span><b>${titulo}</b><small>${desc}</small></span></button>`;
  const ex = E.execucao || {};
  const mascarar = !!E.privacidade?.mascarar_modelo;
  $('#ajustes').innerHTML = `
    <div class="titulo"><h2>Seu nível</h2><span>0 a 5. A trajetória parte daqui.</span></div>
    <div class="niveis">${prismasAtivos().map((s, i) => `<div class="bloco nivel">
      <div class="cab"><b title="${esc(s.nome)}">${curto(s.nome)}</b><span id="n${i}">${s.voce}</span></div>
      <input type="range" min="0" max="5" value="${s.voce}" data-prisma-nivel="${esc(s.nome)}" data-i="${i}" aria-label="Nível de ${esc(s.nome)}">
      <small>meta ${s.meta ?? s.alvo} · Luzia estima ${s.sugere}</small></div>`).join('')}</div>
    <p style="margin-top:var(--e4)"><button class="btn prim" id="salvar-niveis">${ic('check')}Salvar níveis</button></p>
    <div class="titulo"><h2>Foco</h2></div>
    <div class="opcoes">${Object.entries(MODOS).map(([k, v]) => opcao('modo', k, v, E.modo === k)).join('')}</div>
    ${secaoModelo()}
    <div class="titulo"><h2>Agente</h2></div>
    <div class="opcoes">${Object.entries(AGENTES).map(([k, [t, d]]) => opcao('agente', k, ['agente', t, d], E.agente === k)).join('')}</div>
    <div class="titulo"><h2>O que vai para o modelo</h2></div>
    <div class="opcoes">
      ${opcao('privacidade', 'off', ['olho', 'Dados reais', 'Padrão'], !mascarar)}
      ${opcao('privacidade', 'on', ['info', 'Mascarar', 'E-mails, tickets e nomes viram marcadores'], mascarar)}
    </div>
    ${mascarar && !E.privacidade?.termos ? '<p class="aviso fino">Liste empresa e clientes em private/termos.txt.</p>' : ''}
    <p class="dica">Vale só para as chamadas da Luzia. Seu agente vê os dados reais.</p>
    <div class="titulo"><h2>Sobre</h2></div>
    <dl class="sobre-lista">
      <dt>Versão</dt><dd>${esc(ex.versao || '—')}</dd>
      <dt>Última chamada</dt><dd>${ex.tempo_total_s ? `${esc(ex.tempo_total_s)} s · ${esc(ex.pico_memoria_mib)} MiB · ${esc(ex.tokens_entrada)}→${esc(ex.tokens_saida)} tokens` : '—'}</dd>
      <dt>Modelo da última chamada</dt><dd>${esc(ex.modelo || '—')}${ex.quando ? ` · ${esc(dataCurta(ex.quando, true))}` : ''}</dd>
    </dl>`;
}

// Leituras vencidas com modelo configurado: o painel pede sozinho, em segundo plano, uma vez por carregamento
// da página (o servidor ainda segura no máximo uma rodada a cada 10 min). A tela não espera: avisa quando terminar.
let leiturasAutoPedidas = false;
function leiturasAutomaticas() {
  if (leiturasAutoPedidas || !E || !E.modelo_pronto || !(E.leituras_vencidas > 0)) return;
  leiturasAutoPedidas = true;
  api('/api/leituras', { auto: true }, true).then(async (r) => {
    if (r.erro || !r.geradas) return;
    toast(plural(r.geradas, 'análise atualizada', 'análises atualizadas'));
    await carregar(true);
  });
}

async function carregar(auto = false) {
  const tela = document.querySelector('.tela.ativa')?.id || 'hoje';
  const novo = await api('/api/estado', null, auto);
  if (novo.login) return;  // a tela de entrada já está aberta
  if (novo.erro) {
    toast(novo.erro);
    if (E) return;
    $('#hoje').innerHTML = `<div class="bloco destaque"><h3>Não carregou.</h3><p>Tente de novo pelo chat. <small>(${esc(novo.erro)})</small></p></div>`;
    return;
  }
  E = novo;
  if (!$('#jornada')) $('main').innerHTML = MAIN_HTML;  // voltou depois de um painel vazio ou de sair
  if (E.vazio) {
    $('main').innerHTML = '<div class="bloco destaque"><h3>Olá, eu sou a Luzia.</h3><p>Comece com /luzia:triage no chat.</p></div>';
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
  document.querySelectorAll('nav button').forEach((b) => {
    b.classList.toggle('ativo', b.dataset.tela === destino);
    if (b.dataset.tela === destino) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  document.querySelectorAll('.tela').forEach((s) => s.classList.toggle('ativa', s.id === destino));
}

// ------------------------------------------------------------------ eventos
document.addEventListener('click', async (ev) => {
  const seletor = [
    '[data-acender]', '[data-provedor]', '#m-salvar', '#m-testar', '[data-subir]',
    '[data-tela]', '[data-ir]', '[data-avanco]', '[data-prisma]', '[data-enviar]',
    '[data-copiar]', '[data-descartar]', '[data-restaurar]', '[data-fechar]',
    '[data-modo]', '[data-agente]', '[data-privacidade]', '[data-filtro-estado]', '[data-limpar-filtros]',
    '#salvar-niveis', '[data-abrir-pedido-form]', '#ped-enviar', '[data-ajustar-pedido]',
    '[data-pedido-aceitar]', '[data-pedido-ajustar]', '[data-pedido-recusar]',
    '[data-reativar-prisma]', '[data-gerar-leituras]', '[data-ampliar-entregas]',
    '[data-dividir-prisma]', '[data-dividir-todos]', '[data-pedido-dividir-ajustar]',
    '[data-entrega-detalhe]', '#ent-identidade-salvar', '[data-acender-entrega]',
  ].join(',');
  const t = ev.target.closest(seletor);
  if (!t) return;
  const ds = t.dataset;
  // Botões dentro do <summary> de uma entrega não abrem/fecham o detalhe.
  if (t.closest('summary') && t.tagName === 'BUTTON') ev.preventDefault();

  if (t.id === 'ent-identidade-salvar') {
    const identidade = ($('#ent-identidade')?.value || '').trim();
    if (!identidade) {
      toast('Informe um nome ou e-mail dos seus commits.');
      return;
    }
    t.disabled = true;
    const r = await api('/api/identidade', { identidade });
    if (r.erro) {
      toast(`Não adicionou: ${r.erro}`);
      t.disabled = false;
      return;
    }
    toast('Buscando…');
    const amp = await api('/api/entregas/ampliar', { dias: 90 });
    toast(amp.erro ? `Falhou: ${amp.erro}` : plural(amp.atualizacao?.novas ?? 0, 'entrega nova', 'entregas novas'));
    await carregar();
    return;
  }

  if (ds.acender) {
    ev.stopPropagation();
    t.disabled = true;
    toast('Acendendo…');
    const r = await api('/api/acender', { prisma: ds.acender });
    const qtd = (r.avancos || []).length;
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${plural(qtd, 'centelha nova', 'centelhas novas')} · ${nomeCurto(ds.acender)}`, r.erro ? '' : 'celebra');
    await carregar();
    if (!$('#gaveta').hidden && !r.erro) abrirPrisma(r.prisma || r.skill);
    return;
  }
  if (ds.gerarLeituras) {
    ev.stopPropagation();
    t.disabled = true;
    toast('Atualizando análises…');
    const r = await api('/api/leituras', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.geradas ? plural(r.geradas, 'análise atualizada', 'análises atualizadas')
      : (E && E.modelo_pronto ? 'Nada gravado: já em dia ou o modelo não respondeu' : 'Sem modelo: configure em Ajustes')));
    await carregar();
    return;
  }
  if (ds.ampliarEntregas) {
    t.disabled = true;
    const dias = Number(ds.ampliarEntregas) || 180;
    toast('Buscando…');
    const r = await api('/api/entregas/ampliar', { dias });
    toast(r.erro ? `Falhou: ${r.erro}` : plural(r.atualizacao?.novas ?? 0, 'entrega nova', 'entregas novas'));
    await carregar();
    return;
  }
  if (ds.acenderEntrega) {
    ev.stopPropagation();
    t.disabled = true;
    toast('Acendendo…');
    const r = await api('/api/entrega/acender', { id: Number(ds.acenderEntrega) });
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${plural((r.avancos || []).length, 'centelha ligada', 'centelhas ligadas')} à entrega`, r.erro ? '' : 'celebra');
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
  if (ds.ajustarPedido !== undefined) {
    ajustandoPedido = Number(ds.ajustarPedido) || null;
    telaTrajetoria();
    if (ajustandoPedido) $(`#aj-nv-${ajustandoPedido}`)?.focus();
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
    toast('Analisando…');
    const payload = { acao: 'abrir', tipo, prisma, motivo };
    if (metaVal) payload.meta = Number(metaVal);
    const r = await api('/api/pedido', payload);
    if (r.erro) {
      toast(`Não abriu: ${r.erro}`);
    } else {
      mostrarFormPedido = false;
      toast('Pedido aberto');
    }
    await carregar();
    return;
  }
  if (ds.pedidoAceitar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'aceitar', id: Number(ds.pedidoAceitar) });
    if (!r.erro) ajustandoPedido = null;
    const v = r.pedido?.versao || null;
    toast(r.erro ? `Erro: ${r.erro}` : (v ? `Trajetória v${v} criada` : 'Nova versão da trajetória criada'), r.erro ? '' : 'celebra');
    await carregar();
    return;
  }
  if (ds.pedidoAjustar) {
    t.disabled = true;
    const pid = Number(ds.pedidoAjustar);
    const nivel = Number($(`#aj-nv-${pid}`)?.value ?? 1);
    const meta = Number($(`#aj-mt-${pid}`)?.value ?? 4);
    toast('Recalculando…');
    const r = await api('/api/pedido', { acao: 'ajustar', id: pid, nivel, meta });
    if (!r.erro) ajustandoPedido = null;
    toast(r.erro ? `Erro: ${r.erro}` : 'Proposta ajustada');
    await carregar();
    return;
  }
  if (ds.pedidoRecusar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'recusar', id: Number(ds.pedidoRecusar) });
    toast(r.erro ? `Erro: ${r.erro}` : 'Pedido recusado');
    await carregar();
    return;
  }
  if (ds.dividirPrisma || ds.dividirTodos) {
    t.disabled = true;
    const r = ds.dividirPrisma
      ? await api('/api/pedido', { acao: 'abrir', tipo: 'dividir', prisma: ds.dividirPrisma, motivo: 'um prisma por habilidade' })
      : await api('/api/pedido', { acao: 'dividir_todos' });
    // Como todo pedido: a Luzia propõe a divisão e a pessoa confere, ajusta e aceita no card do pedido.
    toast(r.erro ? `Erro: ${r.erro}` : 'Divisão proposta: confira em Pedidos');
    await carregar();
    return;
  }
  if (ds.pedidoDividirAjustar) {
    t.disabled = true;
    const pid = ds.pedidoDividirAjustar;
    const partes = [...document.querySelectorAll(`[data-div-parte="${pid}"]`)].map((i) => i.value.trim()).filter(Boolean);
    const mover = {};
    document.querySelectorAll(`[data-div-mover="${pid}"]`).forEach((s) => { mover[s.dataset.avancoId] = s.value; });
    // Renomear uma parte: os avanços dela seguem a posição (o servidor mapeia nome antigo → novo).
    const antes = [...document.querySelectorAll(`[data-div-parte="${pid}"]`)].map((i) => i.defaultValue);
    Object.keys(mover).forEach((k) => { const i = antes.indexOf(mover[k]); if (i >= 0 && partes[i]) mover[k] = partes[i]; });
    const r = await api('/api/pedido', { acao: 'ajustar', id: Number(pid), partes, mover });
    toast(r.erro ? `Erro: ${r.erro}` : 'Divisão ajustada');
    await carregar();
    return;
  }
  if (ds.reativarPrisma) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'abrir', tipo: 'reativar', prisma: ds.reativarPrisma, motivo: 'Reativado pelo painel' });
    // Como todo pedido: abre, a Luzia propõe e a pessoa aceita no card do pedido (nada muda sozinho).
    toast(r.erro ? (r.erro || 'Não reativou.') : 'Pedido aberto: aceite em Pedidos');
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
    toast(r.erro ? `Não salvou: ${r.erro}` : 'Modelo salvo');
    if (!r.erro) { provEscolhido = null; carregar(); }
    return;
  }
  if (t.id === 'm-testar') {
    toast('Testando…');
    const r = await api('/api/modelo/testar', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.aviso ? `Atenção: ${r.aviso}` : `Respondeu em ${String(r.segundos).replace('.', ',')} s`));
    return;
  }
  if (ds.subir) {
    ev.stopPropagation();
    ev.preventDefault();
    const r = await api('/api/subir', { prisma: ds.subir });
    toast(r.erro ? r.erro : `${nomeCurto(ds.subir)} no nível ${r.para}${r.marco ? ' · Dossiê gerado' : ''}`, r.erro ? '' : 'celebra');
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
    toast(r.erro ? `Não enviou: ${r.erro}` : `Na fila do ${nomeAgente()}`);
    await carregar();
    if (!$('#gaveta').hidden) abrirAvanco(ds.enviar);
  } else if (ds.copiar) {
    try {
      await navigator.clipboard.writeText(avancoPorId(ds.copiar).prompt_completo);
    } catch {
      toast('Não copiou: o navegador bloqueou a área de transferência');
      return;
    }
    const r = await api('/api/iniciar', { id: ds.copiar });
    toast(r.erro ? `Copiado, mas: ${r.erro}` : 'Prompt copiado. Cole no chat.');
    await carregar();
    if (!$('#gaveta').hidden) abrirAvanco(ds.copiar);
  } else if (ds.descartar) {
    const id = ds.descartar;
    await api('/api/descartar', { id, motivo: ds.motivo });
    $('#gaveta').hidden = true;
    toast('Descartada', '', { rotulo: 'Desfazer', dados: { restaurar: id } });
    carregar();
  } else if (ds.restaurar) {
    await api('/api/restaurar', { id: ds.restaurar });
    $('#gaveta').hidden = true;
    toast('Restaurada');
    carregar();
  } else if (ds.fechar !== undefined) {
    $('#gaveta').hidden = true;
  } else if (ds.filtroEstado) {
    filtroEstado = ds.filtroEstado;
    telaAvancos();
  } else if (ds.limparFiltros) {
    filtroEstado = 'abertos';
    filtroPrisma = 'todos';
    filtroTipo = 'todos';
    telaAvancos();
  } else if (ds.modo) {
    const r = await api('/api/modo', { modo: ds.modo });
    toast(r.erro ? `Não salvou: ${r.erro}` : `Foco: ${MODOS[ds.modo]?.[1] || r.modo_nome || ds.modo}`);
    carregar();
  } else if (ds.privacidade) {
    const r = await api('/api/privacidade', { mascarar_modelo: ds.privacidade === 'on' });
    toast(r.erro ? `Não salvou: ${r.erro}` : (r.mascarar_modelo ? 'Mascarando' : 'Enviando dados reais'));
    carregar();
  } else if (ds.agente) {
    await api('/api/agente', { agente: ds.agente });
    toast(`Agente: ${AGENTES[ds.agente]?.[0] || ds.agente}`);
    carregar();
  } else if (t.id === 'salvar-niveis') {
    const niveis = {};
    document.querySelectorAll('[data-prisma-nivel]').forEach((i) => (niveis[i.dataset.prismaNivel] = Number(i.value)));
    await api('/api/nivel', { niveis });
    toast('Níveis salvos');
    carregar();
  }
});

document.addEventListener('change', (ev) => {
  if (ev.target.id === 'm-select') $('#m-outro-l').hidden = ev.target.value !== '__outro';
  if (ev.target.id === 'ped-tipo') {
    tipoPedidoForm = ev.target.value;
    telaTrajetoria();
  }
  if (ev.target.matches('[data-filtro-select]')) {
    if (ev.target.dataset.filtroSelect === 'prisma') filtroPrisma = ev.target.value;
    else filtroTipo = ev.target.value;
    telaAvancos();
    $(`[data-filtro-select="${ev.target.dataset.filtroSelect}"]`)?.focus();
  }
});
document.addEventListener('input', (ev) => {
  if (ev.target.matches('[data-prisma-nivel]')) $('#n' + ev.target.dataset.i).textContent = ev.target.value;
});
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape') $('#gaveta').hidden = true;
});
// Detalhe de entrega aberto/fechado: guardado por id para o polling não fechar o que a pessoa abriu.
document.addEventListener('toggle', (ev) => {
  const d = ev.target;
  if (!d.matches || !d.matches('details.entrega')) return;
  if (d.open) entregasAbertas.add(d.dataset.entregaId); else entregasAbertas.delete(d.dataset.entregaId);
}, true);

// ------------------------------------------------------------------ acesso (entrada herdada do agente)
// O painel abre pelo agente (`career-map`) com um link de uso único no fragmento (#entrar=...), que nunca vai ao
// servidor nem ao Referer: a página o tira da barra e do histórico e o troca por uma sessão de 30 dias (cookie
// HttpOnly que o JS não vê). Nenhum dado é buscado antes de haver sessão; qualquer 401 traz de volta a tela de entrada
// e para o polling. Nada fica guardado no navegador.
const MAIN_HTML = $('main').innerHTML;
const COMANDO_PAINEL = '/luzia:career-map';
let polling = null;
let acessoAberto = false;

function pararPolling() {
  clearInterval(polling);
  polling = null;
}

function limparPainel() {
  pararPolling();
  E = null;
  leiturasAutoPedidas = false;
  entregasAbertas.clear();
  $('#gaveta').hidden = true;
  $('#gaveta-corpo').innerHTML = '';
  $('main').innerHTML = MAIN_HTML;
  $('#nav').innerHTML = '';
  $('#selo').innerHTML = '';
}

function linkDaBarra() {
  const m = /^#entrar=([\w-]{20,256})$/.exec(location.hash || '');
  if (location.hash) history.replaceState(null, '', location.pathname);  // o token sai da barra e do histórico
  return m ? m[1] : null;
}

async function acessoAoIniciar() {
  if (acessoAberto) return;
  acessoAberto = true;
  limparPainel();
  document.body.classList.add('fora');
  const token = linkDaBarra();
  let aviso = '';
  if (token) {
    const r = await api('/api/acesso/link', { token });
    if (!r.erro) return entrou();
    aviso = r.erro;
  }
  const st = await api('/api/acesso/estado');
  if (st.erro) {
    aviso = st.erro;
  } else if (st.sessao_valida) {
    return entrou();
  }
  telaAcesso(aviso);
}

function telaAcesso(aviso = '') {
  $('#acesso').innerHTML = `<div class="bloco destaque acesso-cartao">
    <div class="marca"><img src="logo.svg" alt=""><div><b>Luzia</b><small>sua líder técnica</small></div></div>
    <h3>Abra pelo seu agente</h3>
    <p>Rode no chat. Você fica conectada por 30 dias.</p>
    <div class="acoes-bt"><code class="tag">${COMANDO_PAINEL}</code><button class="btn sec mini" type="button" id="ac-copiar">${ic('copiar')}Copiar</button></div>
    <p class="dica acesso-msg" role="alert">${esc(aviso)}</p>
    <p class="dica">Só quem usa o seu agente nesta máquina entra.</p>
  </div>`;
}

async function entrou() {
  acessoAberto = false;
  $('#acesso').innerHTML = '';
  document.body.classList.remove('fora');
  await carregar();
  if (E && !polling) polling = setInterval(atualizarSozinho, 4000);
}

async function sair() {
  await api('/api/acesso/sair', {});
  toast('Você saiu neste navegador.');
  acessoAoIniciar();
}

document.addEventListener('click', async (ev) => {
  if (ev.target.closest('#ac-copiar')) {
    try {
      await navigator.clipboard.writeText(COMANDO_PAINEL);
      toast('Copiado. Cole no chat.');
    } catch {
      toast(`Copie: ${COMANDO_PAINEL}`);
    }
  }
});
$('#sair').addEventListener('click', sair);
window.addEventListener('hashchange', () => {  // link novo do agente numa aba que já estava aberta
  if (!/^#entrar=/.test(location.hash)) return;
  acessoAberto = false;
  acessoAoIniciar();
});

async function atualizarSozinho() {
  if (!E || !$('#gaveta').hidden || mostrarFormPedido || ajustandoPedido) return;
  const novo = await api('/api/estado', null, true);
  if (novo.erro || novo.vazio || !E) return;
  const vistos = new Set((E.lumens || []).map(chaveLm));
  const novos = (novo.lumens || []).filter((l) => !vistos.has(chaveLm(l)));
  const mudou = assinatura(novo) !== assinatura(E);
  E = novo;
  const editando = document.activeElement && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
  if (mudou && !editando) render();
  else feed();
  celebrar(novos);
}

acessoAoIniciar();
