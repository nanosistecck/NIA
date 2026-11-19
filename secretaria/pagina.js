/* SECRETARIA DO WHATSAPP (05/11/2026) — roda DENTRO do WhatsApp Web, antes da pagina.
 *
 * Faz quatro coisas, e so' elas:
 *   1. Percebe a ligacao tocando, atendida e encerrada (lendo a tela e as notificacoes).
 *   2. Aperta os botoes que o motor mandar (atender, recusar, desligar).
 *   3. Capta a VOZ DE QUEM LIGOU (a faixa de audio que chega da ligacao) e manda ao
 *      motor em pedacos de 100 ms, 16 kHz.
 *   4. Quando a secretaria atende, o "microfone" que o WhatsApp recebe e' a VOZ DELA
 *      (o motor empurra o audio da Gemini aqui). O microfone e a caixa de som do PC
 *      ficam fora: quem ligou nao ouve a sala, e a sala nao ouve quem ligou.
 *
 * Fora de uma ligacao da secretaria, nada muda: o microfone de verdade segue normal.
 * A ponte com o motor e' a funcao window.__secretaria(json), posta pelo Playwright.
 */
(() => {
  'use strict';
  if (window.__secretariaInstalada) return;
  window.__secretariaInstalada = true;

  const enviar = (tipo, dados) => {
    try { window.__secretaria(JSON.stringify(Object.assign({ tipo }, dados || {}))); } catch (e) { /* motor fora */ }
  };
  const diag = (oque, dados) => enviar('diag', { oque, dados: dados || {} });

  const S = {
    modo: 'livre',            // livre | secretaria | dono
    ctx: null, prontoCtx: null,
    toca: null, ganhoIA: null, capta: null,
    faixasLocais: new Set(),  // faixas que NOS demos ao WhatsApp (nunca captar)
    faixasCaptadas: new Set(),
    elementos: new Set(),
    pcs: new Set(),
    restaIA: 0,
    enviando: false,
  };

  // ─── O motor de audio (um AudioContext so' nosso, 48 kHz) ──────────────────
  const WORKLET = `
  class SecToca extends AudioWorkletProcessor {
    constructor() {
      super();
      this.tam = 48000 * 30; this.buf = new Float32Array(this.tam);
      this.r = 0; this.w = 0; this.n = 0; this.cont = 0;
      this.port.onmessage = (e) => {
        const d = e.data;
        if (d.limpar) { this.r = this.w = this.n = 0; return; }
        const a = d.amostras;
        for (let i = 0; i < a.length && this.n < this.tam; i++) {
          this.buf[this.w] = a[i]; this.w = (this.w + 1) % this.tam; this.n++;
        }
      };
    }
    process(entradas, saidas) {
      const o = saidas[0][0];
      for (let i = 0; i < o.length; i++) {
        if (this.n > 0) { o[i] = this.buf[this.r]; this.r = (this.r + 1) % this.tam; this.n--; } else o[i] = 0;
      }
      if (++this.cont % 20 === 0) this.port.postMessage({ resta: this.n });
      return true;
    }
  }
  registerProcessor('sec-toca', SecToca);

  class SecCapta extends AudioWorkletProcessor {
    constructor() {
      super();
      this.passo = sampleRate / 16000; this.fase = 0; this.soma = 0; this.qtd = 0;
      this.lote = new Int16Array(1600); this.k = 0;
    }
    process(entradas) {
      const ent = entradas[0];
      if (!ent || !ent[0]) return true;
      const a = ent[0], b = ent[1];
      for (let i = 0; i < a.length; i++) {
        this.soma += b ? (a[i] + b[i]) * 0.5 : a[i]; this.qtd++; this.fase += 1;
        if (this.fase >= this.passo) {
          this.fase -= this.passo;
          let v = this.soma / this.qtd; this.soma = 0; this.qtd = 0;
          v = v < -1 ? -1 : (v > 1 ? 1 : v);
          this.lote[this.k++] = v < 0 ? v * 32768 : v * 32767;
          if (this.k === this.lote.length) { this.port.postMessage(this.lote.slice(0)); this.k = 0; }
        }
      }
      return true;
    }
  }
  registerProcessor('sec-capta', SecCapta);`;

  const b64 = {
    de: (s) => { const bin = atob(s); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; },
    para: (u8) => { let s = ''; const P = 0x8000; for (let i = 0; i < u8.length; i += P) s += String.fromCharCode.apply(null, u8.subarray(i, i + P)); return btoa(s); },
  };

  // ESCUTA DE UMA FONTE SO' (05/11): a pagina pode ter varios "canais de som" (o da ligacao, o do
  // toque, o dos avisos). Misturar todos mandava a voz junto com silencio de outro canal, em dobro
  // de velocidade, e a secretaria entendia picado. Fica a primeira fonte com VOZ; outra so' assume
  // se tiver voz e a escolhida estiver calada ha 4 s.
  const fonte = { id: null, ultimaVoz: 0 };
  const energia = (i16) => { let s = 0, n = 0; for (let i = 0; i < i16.length; i += 8) { s += Math.abs(i16[i]); n++; } return n ? s / n : 0; };
  const encaminhar = (id, buf) => {
    if (S.modo !== 'secretaria') return;
    const temVoz = energia(new Int16Array(buf)) > 250;
    const agora = Date.now();
    if (fonte.id === null) {
      if (!temVoz) return;
      fonte.id = id; fonte.ultimaVoz = agora;
      diag('escuta_escolhida', { fonte: id });
    } else if (fonte.id !== id) {
      if (!(temVoz && agora - fonte.ultimaVoz > 4000)) return;
      diag('escuta_trocou', { de: fonte.id, para: id });
      fonte.id = id;
    }
    if (temVoz) fonte.ultimaVoz = agora;
    enviar('audio', { b64: b64.para(new Uint8Array(buf)) });
  };
  let contaCtx = 0;

  const garantirCtx = () => {
    if (S.prontoCtx) return S.prontoCtx;
    S.prontoCtx = (async () => {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      S.ctx = new Ctx({ sampleRate: 48000 });
      const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
      await S.ctx.audioWorklet.addModule(url);
      S.toca = new AudioWorkletNode(S.ctx, 'sec-toca', { numberOfInputs: 0, outputChannelCount: [1] });
      S.toca.port.onmessage = (e) => { if (e.data && typeof e.data.resta === 'number') S.restaIA = e.data.resta; };
      // Um ganho ZERO ligado na caixa: so' para o navegador processar os nos (ele so'
      // calcula o que chega ate' uma saida). Nada daqui toca no PC.
      S.mudo = S.ctx.createGain();
      S.mudo.gain.value = 0;
      S.mudo.connect(S.ctx.destination);
      S.ganhoIA = S.ctx.createGain();
      S.ganhoIA.gain.value = 0;
      S.toca.connect(S.ganhoIA);
      S.ganhoIA.connect(S.mudo);
      // OUVIR NO PC (05/11): a voz dela tambem na caixa do computador, so' com a opcao ligada.
      S.ouvirIA = S.ctx.createGain();
      S.ouvirIA.gain.value = 0;
      S.ganhoIA.connect(S.ouvirIA);
      S.ouvirIA.connect(S.ctx.destination);
      S.capta = new AudioWorkletNode(S.ctx, 'sec-capta', { numberOfOutputs: 1, outputChannelCount: [1] });
      S.capta.connect(S.mudo);
      S.capta.port.onmessage = (e) => encaminhar('faixa', e.data.buffer);
      if (S.ctx.state !== 'running') { try { await S.ctx.resume(); } catch (e) { /* sem gesto */ } }
      diag('audio_pronto', { estado: S.ctx.state, taxa: S.ctx.sampleRate });
      return S.ctx;
    })().catch((e) => { diag('audio_erro', { erro: String(e) }); S.prontoCtx = null; throw e; });
    return S.prontoCtx;
  };

  // A VOZ DA SECRETARIA: PCM 16 bits, 24 kHz, em base64 -> 48 kHz no worklet.
  window.__secTocar = (s) => {
    if (!S.toca) return 0;
    const u8 = b64.de(s);
    const i16 = new Int16Array(u8.buffer, u8.byteOffset, Math.floor(u8.byteLength / 2));
    const f = new Float32Array(i16.length * 2);
    for (let i = 0; i < i16.length; i++) {
      const v = i16[i] / 32768, prox = i + 1 < i16.length ? i16[i + 1] / 32768 : v;
      f[2 * i] = v; f[2 * i + 1] = (v + prox) * 0.5;
    }
    S.toca.port.postMessage({ amostras: f }, [f.buffer]);
    S.restaIA += f.length;
    return S.restaIA;
  };
  window.__secLimpar = () => { if (S.toca) S.toca.port.postMessage({ limpar: true }); S.restaIA = 0; };
  window.__secResta = () => S.restaIA / 48000;

  // A faixa que vira o "microfone" do WhatsApp quando a secretaria atende (uma por ligacao).
  const faixaDaSecretaria = async () => {
    await garantirCtx();
    if (S.faixaIA && S.faixaIA.readyState === 'live') return S.faixaIA;
    S.dest = S.ctx.createMediaStreamDestination();
    S.ganhoIA.connect(S.dest);
    S.faixaIA = S.dest.stream.getAudioTracks()[0];
    S.faixasLocais.add(S.faixaIA.id);
    return S.faixaIA;
  };
  const soltarFaixaDaSecretaria = () => {
    try { if (S.dest) S.ganhoIA.disconnect(S.dest); } catch (e) { /* ja solta */ }
    S.dest = null; S.faixaIA = null;
  };

  // REDE DE SEGURANCA: com a secretaria na linha, NENHUM microfone de verdade vai
  // para a ligacao. Se o WhatsApp abriu o microfone antes (ao tocar), a faixa e'
  // trocada pela voz dela aqui. Quem ligou nunca ouve a sala.
  const garantirVozNaLigacao = async () => {
    if (S.modo !== 'secretaria' || !S.pcs.size) return;
    const faixa = await faixaDaSecretaria();
    for (const pc of S.pcs) {
      let envios = [];
      try { envios = pc.getSenders(); } catch (e) { continue; }
      for (const env of envios) {
        const t = env.track;
        if (t && t.kind === 'audio' && t !== faixa) {
          try { await env.replaceTrack(faixa); diag('microfone_trocado', { de: String(t.label || '').slice(0, 40) }); } catch (e) { diag('troca_erro', { erro: String(e) }); }
        }
      }
    }
  };

  // ─── Captar quem ligou ────────────────────────────────────────────────────
  const captarFaixa = (faixa, origem) => {
    try {
      if (!faixa || faixa.kind !== 'audio') return;
      if (S.faixasLocais.has(faixa.id) || S.faixasCaptadas.has(faixa.id)) return;
      S.faixasCaptadas.add(faixa.id);
      garantirCtx().then(() => {
        const fonte = S.ctx.createMediaStreamSource(new MediaStream([faixa]));
        fonte.connect(S.capta);
        diag('faixa_captada', { origem, id: String(faixa.id).slice(0, 8), estado: faixa.readyState });
        faixa.addEventListener('ended', () => {
          diag('faixa_fim', { origem });
          try { fonte.disconnect(); } catch (e) { /* ja foi */ }
          S.faixasCaptadas.delete(faixa.id);
        });
      }).catch(() => {});
    } catch (e) { diag('captar_erro', { erro: String(e) }); }
  };

  // Som de quem ligou NUNCA sai na caixa do PC enquanto a secretaria fala com ele.
  // 05/11 22h45 (Diego gravando video): com "ouvir no PC" so' a voz DELA sai na caixa; a de quem liga
  // ficava em dobro no video (a voz de verdade na sala + a copia tocada pelo PC).
  const aplicarMudo = (el) => {
    try {
      if (S.modo === 'secretaria') {
        if (el.__secMudoAntes === undefined) el.__secMudoAntes = el.muted;
        el.muted = true;
      } else if (el.__secMudoAntes !== undefined) {
        el.muted = el.__secMudoAntes; delete el.__secMudoAntes;
      }
    } catch (e) { /* elemento sumiu */ }
  };

  // AudioContext do WhatsApp -> { pre (tudo que ia para a caixa entra aqui), mudo (dai para a caixa) }
  const saidas = new Map();
  const aplicarModo = (modo, ouvir) => {
    S.ouvir = (modo === 'secretaria') && !!ouvir;
    S.modo = modo;
    fonte.id = null; fonte.ultimaVoz = 0;
    S.elementos.forEach(aplicarMudo);
    saidas.forEach((s) => { try { s.mudo.gain.value = (modo === 'secretaria') ? 0 : 1; } catch (e) { /* */ } });
    if (S.ouvirIA) S.ouvirIA.gain.value = S.ouvir ? 1 : 0;
    if (S.ganhoIA) S.ganhoIA.gain.value = (modo === 'secretaria') ? 1 : 0;
    if (modo !== 'secretaria') {
      window.__secLimpar();
      if (modo === 'livre') soltarFaixaDaSecretaria();
    } else {
      garantirVozNaLigacao().catch(() => {});
    }
  };

  // getUserMedia: na ligacao da secretaria o WhatsApp recebe a voz DELA.
  const md = navigator.mediaDevices;
  if (md && md.getUserMedia) {
    const gumOriginal = md.getUserMedia.bind(md);
    S.gumOriginal = gumOriginal;
    md.getUserMedia = async function (c) {
      const pedeAudio = !!(c && c.audio);
      if (pedeAudio && S.modo === 'secretaria') {
        const faixa = await faixaDaSecretaria();
        diag('microfone', { quem: 'secretaria', video: !!(c && c.video) });
        return new MediaStream([faixa]);
      }
      const st = await gumOriginal(c);
      try { st.getTracks().forEach((t) => S.faixasLocais.add(t.id)); } catch (e) { /* */ }
      diag('microfone', { quem: S.modo, video: !!(c && c.video) });
      return st;
    };
  }

  // RTCPeerConnection: a faixa que chega e' a voz de quem ligou.
  if (window.RTCPeerConnection) {
    const Original = window.RTCPeerConnection;
    class SecPC extends Original {
      constructor(...args) {
        super(...args);
        // So' a bancada de teste usa: o lado de "quem liga" fica fora da secretaria.
        if (args[0] && args[0].__secIgnorar) return;
        S.pcs.add(this);
        diag('pc_criado', { total: S.pcs.size });
        this.addEventListener('track', (ev) => captarFaixa(ev.track, 'pc'));
        this.addEventListener('connectionstatechange', () => {
          diag('pc_estado', { estado: this.connectionState });
          if (this.connectionState === 'closed' || this.connectionState === 'failed') S.pcs.delete(this);
        });
      }
    }
    window.RTCPeerConnection = SecPC;
    if (window.webkitRTCPeerConnection) window.webkitRTCPeerConnection = SecPC;
  }

  // <audio>/<video> com a ligacao: capta e silencia na caixa durante a secretaria.
  try {
    const d = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'srcObject');
    if (d && d.set) {
      Object.defineProperty(HTMLMediaElement.prototype, 'srcObject', {
        configurable: true, enumerable: d.enumerable,
        get() { return d.get.call(this); },
        set(v) {
          d.set.call(this, v);
          try {
            if (this.__secIgnorar) return;    // so' a bancada de teste
            if (v && typeof v.getAudioTracks === 'function' && v.getAudioTracks().length) {
              S.elementos.add(this);
              v.getAudioTracks().forEach((t) => captarFaixa(t, 'elemento'));
              aplicarMudo(this);
            }
          } catch (e) { /* */ }
        },
      });
    }
  } catch (e) { diag('gancho_erro', { onde: 'srcObject', erro: String(e) }); }

  // WebAudio do proprio WhatsApp tocando na caixa (05/11: e' ASSIM que a ligacao toca no Edge:
  // um AudioContext de 16 kHz do motor de voz deles, sem faixa de WebRTC). Tudo que ia direto
  // para a caixa passa por `pre` -> `mudo` -> caixa. A ESCUTA da secretaria sai do `pre`, ANTES
  // do mudo: na ligacao dela a caixa fica calada e ela ouve a pessoa. (Antes a escuta vinha
  // depois do mudo e ela ouvia silencio: se apresentou e nunca mais respondeu.)
  try {
    const conOriginal = AudioNode.prototype.connect;
    const desOriginal = AudioNode.prototype.disconnect;
    const saidaDe = (ctx) => {
      let s = saidas.get(ctx);
      if (!s) {
        const pre = ctx.createGain();
        pre.gain.value = 1;
        const mudo = ctx.createGain();
        mudo.gain.value = (S.modo === 'secretaria') ? 0 : 1;
        conOriginal.call(pre, mudo);
        conOriginal.call(mudo, ctx.destination);
        s = { pre, mudo };
        saidas.set(ctx, s);
        diag('webaudio_do_whatsapp', { taxa: ctx.sampleRate });
        (async () => {
          try {
            const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
            await ctx.audioWorklet.addModule(url);
            const cap = new AudioWorkletNode(ctx, 'sec-capta', { numberOfOutputs: 1, outputChannelCount: [1] });
            const zero = ctx.createGain();
            zero.gain.value = 0;
            conOriginal.call(cap, zero);
            conOriginal.call(zero, ctx.destination);
            const idFonte = 'som' + (++contaCtx) + '-' + ctx.sampleRate;
            cap.port.onmessage = (e) => encaminhar(idFonte, e.data.buffer);
            conOriginal.call(pre, cap);
            diag('escuta_pronta', { taxa: ctx.sampleRate });
          } catch (e) { diag('webaudio_captar_erro', { erro: String(e) }); }
        })();
      }
      return s;
    };
    AudioNode.prototype.connect = function (destino, ...resto) {
      try {
        if (destino instanceof AudioDestinationNode && this.context !== S.ctx && this.context === destino.context) {
          return conOriginal.call(this, saidaDe(this.context).pre, ...resto);
        }
      } catch (e) { /* segue normal */ }
      return conOriginal.call(this, destino, ...resto);
    };
    AudioNode.prototype.disconnect = function (destino, ...resto) {
      try {
        if (destino instanceof AudioDestinationNode && saidas.has(destino.context)) {
          return desOriginal.call(this, saidas.get(destino.context).pre, ...resto);
        }
      } catch (e) { /* segue normal */ }
      return desOriginal.apply(this, arguments);
    };
  } catch (e) { diag('gancho_erro', { onde: 'webaudio', erro: String(e) }); }

  // Notificacao do navegador: "Chamada de voz recebida" chega aqui mesmo sem a aba na frente.
  try {
    const N = window.Notification;
    if (N) {
      class SecNotificacao extends N {
        constructor(titulo, op) {
          super(titulo, op);
          enviar('notificacao', { titulo: String(titulo || '').slice(0, 120), corpo: String((op && op.body) || '').slice(0, 200) });
        }
      }
      Object.defineProperty(SecNotificacao, 'permission', { get: () => N.permission });
      SecNotificacao.requestPermission = N.requestPermission.bind(N);
      window.Notification = SecNotificacao;
    }
  } catch (e) { diag('gancho_erro', { onde: 'notificacao', erro: String(e) }); }

  // ─── Ler a tela: tocando / em ligacao / nada ──────────────────────────────
  if (window.top !== window) return;   // a leitura da tela so' na janela de cima

  // A janela da secretaria fica escondida e sem foco; sem foco o WhatsApp nao mostra a
  // ligacao na tela (so' tenta notificacao). Para ele, esta janela esta sempre em uso.
  try {
    document.hasFocus = () => true;
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'visible' });
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
    // O "perdeu o foco" nunca chega no WhatsApp (este ouvinte e' o primeiro da fila).
    window.addEventListener('blur', (e) => { if (e.target === window) e.stopImmediatePropagation(); }, true);
  } catch (e) { diag('gancho_erro', { onde: 'foco', erro: String(e) }); }

  const semAcento = (t) => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const RX = {
    aceitar: /^(aceitar|atender|accept|answer)\b|\b(aceitar|atender) (a )?(chamada|ligacao)\b|\b(accept|answer) (the )?call\b/,
    recusar: /^(recusar|rejeitar|decline|reject|ignorar|ignore)\b|\b(recusar|rejeitar) (a )?(chamada|ligacao)\b|\bdecline (the )?call\b/,
    desligar: /\b(encerrar|desligar|finalizar|terminar|sair d[ae]) (a )?(chamada|ligacao)\b|\bend (the )?call\b|\bhang ?up\b|^(encerrar|desligar)$/,
  };
  const GENERICAS = /(chamada|ligacao|whatsapp|chamando|tocando|calling|incoming|voice call|video call|de voz|de video|criptografia|encrypted|toque|ring|aceitar|recusar|atender|ignorar|mensagem|message|\d{1,2}:\d{2})/;

  // Nome do icone (data-icon) quando o botao nao tem texto nem rotulo.
  const RX_ICONE = {
    aceitar: /(^|[-_])(accept|answer|aceitar|atender)([-_]|$)|call-accept|call-answer/,
    recusar: /(^|[-_])(decline|reject|recusar|rejeitar)([-_]|$)|call-decline|call-reject/,
    desligar: /end-?call|hang-?up|call-end|encerrar/,
  };

  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    const st = getComputedStyle(el);
    return st.visibility !== 'hidden' && st.display !== 'none' && Number(st.opacity || 1) > 0.05;
  };

  // UMA passada pela tela a cada leitura (o WhatsApp tem milhares de elementos):
  // rotulo/titulo/icone primeiro; texto so' de botao e com textContent (nao forca layout).
  const acharTodos = () => {
    const achados = { aceitar: null, recusar: null, desligar: null };
    const candidatos = document.querySelectorAll('button, [role="button"], [aria-label], [title], [data-icon]');
    for (const el of candidatos) {
      const icone = el.getAttribute('data-icon');
      let r = el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('data-tooltip') || '';
      if (!r && !icone && (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button')) {
        const tc = el.textContent || '';
        if (tc.length <= 40) r = tc;
      }
      const n = r ? semAcento(r) : '';
      const ic = icone ? semAcento(icone) : '';
      if (n.length > 60) continue;
      for (const tipo of ['aceitar', 'recusar', 'desligar']) {
        if (achados[tipo]) continue;
        if ((n && RX[tipo].test(n)) || (ic && RX_ICONE[tipo].test(ic))) {
          // data-icon fica num <span> dentro do botao: sobe ate' o clicavel.
          const alvo = el.closest('button, [role="button"]') || el;
          if (visivel(alvo)) achados[tipo] = alvo;
        }
      }
      if (achados.aceitar && achados.recusar && achados.desligar) break;
    }
    return achados;
  };

  const caixaDaLigacao = (bt) => {
    let caixa = bt;
    for (let i = 0; i < 8 && caixa && caixa.parentElement; i++) {
      caixa = caixa.parentElement;
      const r = caixa.getBoundingClientRect();
      if (r.height > 90 && (caixa.innerText || '').trim().length > 6) break;
    }
    return caixa;
  };

  const nomeNaCaixa = (caixa) => {
    if (!caixa) return '';
    const linhas = String(caixa.innerText || '').split('\n').map((s) => s.trim()).filter(Boolean);
    for (const ln of linhas) {
      const n = semAcento(ln);
      if (n.length < 2 || n.length > 60) continue;
      if (GENERICAS.test(n)) continue;
      return ln;
    }
    // Sem texto: o nome as vezes so' existe no aria-label da foto.
    const img = caixa.querySelector('img[alt]');
    return img ? String(img.getAttribute('alt') || '').trim() : '';
  };

  const fotografia = (caixa) => {
    if (!caixa) return {};
    const rotulos = Array.from(caixa.querySelectorAll('[aria-label],[title],[data-icon]')).slice(0, 25)
      .map((e) => (e.getAttribute('aria-label') || e.getAttribute('title') || ('icon:' + e.getAttribute('data-icon')))).filter(Boolean);
    return { texto: String(caixa.innerText || '').slice(0, 400), rotulos };
  };

  const marcar = (el, nome) => {
    document.querySelectorAll(`[data-sec-alvo="${nome}"]`).forEach((e) => e.removeAttribute('data-sec-alvo'));
    if (el) el.setAttribute('data-sec-alvo', nome);
  };

  let ultimo = 'nada';
  let nomeAtual = '';
  let desde = 0;
  const olhar = () => {
    let estado = 'nada';
    const t = acharTodos();
    const bAceitar = t.aceitar, bRecusar = t.recusar, bDesligar = t.desligar;
    if (bAceitar && (bRecusar || bDesligar)) estado = 'tocando';
    else if (bDesligar) estado = 'em_ligacao';
    marcar(bAceitar, 'aceitar');
    marcar(bRecusar, 'recusar');
    marcar(bDesligar, 'desligar');
    if (estado !== ultimo) {
      const agora = Date.now();
      if (estado === 'tocando') {
        const caixa = caixaDaLigacao(bAceitar);
        nomeAtual = nomeNaCaixa(caixa);
        enviar('tela', { estado, nome: nomeAtual, foto: fotografia(caixa) });
      } else if (estado === 'em_ligacao') {
        enviar('tela', { estado, nome: nomeAtual, foto: fotografia(caixaDaLigacao(bDesligar)) });
      } else {
        // Some por 1,5 s antes de dizer que acabou: a tela troca de caixa ao atender.
        if (agora - desde < 1500) return;
        enviar('tela', { estado, nome: nomeAtual });
        nomeAtual = '';
      }
      ultimo = estado;
      desde = agora;
    } else {
      desde = Date.now();
    }
  };

  // Estado do WhatsApp Web: carregando / qr / conectado.
  let ultimoLogin = '';
  let ultimoQr = '';
  let contaQr = 0;
  const olharLogin = () => {
    let est = 'carregando';
    if (document.querySelector('canvas[aria-label], [data-ref] canvas, div[data-ref]')) est = 'qr';
    if (document.querySelector('#pane-side, [data-testid="chat-list"], div[aria-label][role="grid"], #side')) est = 'conectado';
    if (est !== ultimoLogin) { ultimoLogin = est; enviar('login', { estado: est }); }
    // O QR CODE vai para o cartao do NIA (o navegador interno fica escondido).
    // Ele troca sozinho a cada ~20 s: confere a cada 2 s e so' manda quando muda.
    if (est === 'qr' && (contaQr++ % 5) === 0) {
      const cv = document.querySelector('[data-ref] canvas, canvas[aria-label], canvas');
      if (cv && cv.width > 60) {
        try {
          const img = cv.toDataURL('image/png');
          if (img && img !== ultimoQr) { ultimoQr = img; enviar('qr', { img }); }
        } catch (e) { /* canvas protegido */ }
      }
    } else if (est !== 'qr') {
      ultimoQr = '';
    }
    // Depois de uns minutos o WhatsApp para de trocar o codigo e mostra "Clique para
    // recarregar o QR code". Ninguem ve esta pagina: o clique sai daqui (1 a cada 15 s).
    if (est === 'qr' && Date.now() - ultimoRecarregar > 15000) {
      const rx = /(recarregar|reload|tentar de novo|tentar novamente|try again)/;
      for (const b of document.querySelectorAll('button, [role="button"]')) {
        const r = semAcento(b.getAttribute('aria-label') || b.getAttribute('title') || b.textContent || '');
        if (r.length <= 60 && rx.test(r) && visivel(b)) {
          ultimoRecarregar = Date.now();
          b.click();
          diag('qr_recarregado', { botao: r.slice(0, 40) });
          break;
        }
      }
    }
  };
  let ultimoRecarregar = 0;

  // Comandos do motor: o botao a apertar fica marcado; o clique de verdade e' do Playwright.
  window.__secCmd = async (c) => {
    try {
      if (c.acao === 'modo') {
        if (c.modo === 'secretaria') await garantirCtx();
        aplicarModo(c.modo, c.ouvir);
        return { ok: true, modo: S.modo, ouvir: !!S.ouvir };
      }
      if (c.acao === 'preparar') { await garantirCtx(); return { ok: true, estado: S.ctx.state }; }
      if (c.acao === 'clicar_js') {
        const el = document.querySelector(`[data-sec-alvo="${c.alvo}"]`);
        if (!el) return { ok: false, erro: 'botao nao esta na tela' };
        for (const t of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
          el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }));
        }
        return { ok: true };
      }
      if (c.acao === 'transferir') {
        // A secretaria sai, o dono entra: troca a voz dela pelo microfone de verdade na ligacao.
        aplicarModo('dono');
        let trocou = 0;
        if (S.gumOriginal) {
          const real = await S.gumOriginal({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
          const faixaReal = real.getAudioTracks()[0];
          S.faixasLocais.add(faixaReal.id);
          for (const pc of S.pcs) {
            for (const env of pc.getSenders()) {
              if (env.track && env.track.kind === 'audio') { try { await env.replaceTrack(faixaReal); trocou++; } catch (e) { /* */ } }
            }
          }
        }
        return { ok: trocou > 0, trocou };
      }
      if (c.acao === 'clicar_texto') {
        // Diagnostico/ajuste: clica no primeiro item visivel cujo rotulo/texto casa com `rx`
        // e devolve o texto da tela logo depois (para ler configuracoes, avisos).
        const rx = new RegExp(c.rx, 'i');
        const els = Array.from(document.querySelectorAll('button, [role="button"], [role="listitem"], [role="tab"], [role="menuitem"], a, span, div[title], div[aria-label]'));
        const el = els.find((e) => {
          const t = semAcento(e.getAttribute('aria-label') || e.getAttribute('title') || (e.children.length === 0 ? e.textContent : '') || '');
          return t && t.length < 90 && rx.test(t) && visivel(e);
        });
        if (!el) return { ok: false, erro: 'nao achei' };
        const clicavel = el.closest('button, [role="button"], [role="listitem"], [role="menuitem"], a') || el;
        clicavel.click();
        await new Promise((ok) => setTimeout(ok, c.espera || 1500));
        const main = document.querySelector('#app') || document.body;
        return { ok: true, clicado: String(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 60),
                 texto: String(main.innerText || '').replace(/\n+/g, ' | ').slice(0, c.max || 2500) };
      }
      if (c.acao === 'sondar') {
        // Diagnostico: o que este navegador oferece para chamada, e o que a aba de ligacoes diz.
        const r = {
          ua: navigator.userAgent,
          marcas: navigator.userAgentData ? navigator.userAgentData.brands.map((b) => b.brand + ' ' + b.version) : null,
          plataforma: navigator.userAgentData ? navigator.userAgentData.platform : null,
          isolado: self.crossOriginIsolated, sab: typeof SharedArrayBuffer,
          scriptTransform: typeof window.RTCRtpScriptTransform,
          encodedStreams: !!(window.RTCRtpSender && RTCRtpSender.prototype.createEncodedStreams),
          webtransport: typeof window.WebTransport, webcodecs: typeof window.AudioEncoder,
          notificacao: window.Notification ? Notification.permission : 'sem',
          visivel: document.visibilityState, foco: document.hasFocus(),
        };
        try {
          const d = await navigator.mediaDevices.enumerateDevices();
          r.aparelhos = d.map((x) => x.kind).join(',');
        } catch (e) { r.aparelhos = 'erro ' + e; }
        try {
          const cv = (RTCRtpSender.getCapabilities('video') || { codecs: [] }).codecs.map((x) => x.mimeType);
          const ca = (RTCRtpSender.getCapabilities('audio') || { codecs: [] }).codecs.map((x) => x.mimeType);
          r.codecsVideo = Array.from(new Set(cv)).join(',');
          r.codecsAudio = Array.from(new Set(ca)).join(',');
          r.h264mse = window.MediaSource ? MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"') : null;
          r.h264dec = typeof VideoDecoder !== 'undefined'
            ? (await VideoDecoder.isConfigSupported({ codec: 'avc1.42E01E' }).catch(() => ({ supported: 'erro' }))).supported : null;
        } catch (e) { r.codecs = 'erro ' + e; }
        try { const p = await navigator.permissions.query({ name: 'microphone' }); r.permMic = p.state; } catch (e) { r.permMic = 'erro'; }
        if (c.abrirLigacoes) {
          const alvo = Array.from(document.querySelectorAll('[aria-label],[title],[data-icon]')).find((e) => {
            const t = semAcento(e.getAttribute('aria-label') || e.getAttribute('title') || '');
            return t === 'calls' || t === 'ligacoes' || t === 'chamadas' || e.getAttribute('data-icon') === 'ic-call';
          });
          if (alvo) {
            (alvo.closest('button, [role="button"]') || alvo).click();
            await new Promise((ok) => setTimeout(ok, 2500));
            const main = document.querySelector('#app') || document.body;
            r.abaLigacoes = String(main.innerText || '').replace(/\n+/g, ' | ').slice(0, 1500);
          } else r.abaLigacoes = 'nao achei a aba';
        }
        return r;
      }
      if (c.acao === 'botoes') {
        // Diagnostico da primeira ligacao de verdade: tudo que e' clicavel e visivel.
        const lista = [];
        for (const el of document.querySelectorAll('button, [role="button"], [aria-label], [data-icon]')) {
          if (lista.length >= 120) break;
          if (!visivel(el)) continue;
          const r = el.getAttribute('aria-label') || el.getAttribute('title') || '';
          const ic = el.getAttribute('data-icon') || '';
          const tx = (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button') ? String(el.textContent || '').trim().slice(0, 40) : '';
          if (r || ic || tx) lista.push({ tag: el.tagName.toLowerCase(), rotulo: r.slice(0, 60), icone: ic, texto: tx });
        }
        return { ok: true, botoes: lista, titulo: document.title };
      }
      if (c.acao === 'estado') {
        return { ok: true, modo: S.modo, pcs: S.pcs.size, captando: S.faixasCaptadas.size, ctx: S.ctx ? S.ctx.state : 'nenhum',
                 tela: ultimo, login: ultimoLogin, resta: S.restaIA / 48000 };
      }
      return { ok: false, erro: 'acao desconhecida' };
    } catch (e) { return { ok: false, erro: String(e) }; }
  };

  const ligar = () => {
    setInterval(() => {
      try { olhar(); olharLogin(); } catch (e) { /* tela trocando */ }
      if (S.modo === 'secretaria') garantirVozNaLigacao().catch(() => {});
    }, 400);
    diag('pagina_pronta', { url: location.href.slice(0, 80) });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ligar); else ligar();
})();
