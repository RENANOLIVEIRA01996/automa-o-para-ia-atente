(() => {
  'use strict';
  // Only public destinations and local illustrative data belong in this file.
  const SIGNUP_URL = 'https://recepia.132-226-243-173.sslip.io/cadastro';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const mobile = window.matchMedia('(max-width: 768px)');
  const body = document.body;
  const hero = document.querySelector('.hero');
  const video = document.querySelector('.hero-video');
  const motionButton = document.querySelector('.motion-toggle');
  let effectsPaused = reduced.matches;
  let heroVisible = true;
  let mediaLoaded = false;
  let mediaLoading = false;
  let heroFrame = 0;

  document.querySelectorAll('a.signup').forEach(a => { a.href = SIGNUP_URL; });
  document.getElementById('year').textContent = String(new Date().getFullYear());

  const menuButton = document.querySelector('.menu-toggle');
  const menu = document.getElementById('navigation');
  function closeMenu() {
    menu.classList.remove('is-open');
    body.classList.remove('menu-open');
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Abrir menu');
  }
  menuButton.addEventListener('click', () => {
    const open = menuButton.getAttribute('aria-expanded') !== 'true';
    menuButton.setAttribute('aria-expanded', String(open));
    menuButton.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    menu.classList.toggle('is-open', open);
    body.classList.toggle('menu-open', open);
  });
  menu.querySelectorAll('a').forEach(a => a.addEventListener('click', closeMenu));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeMenu(); menuButton.focus(); } });
  mobile.addEventListener('change', closeMenu);

  const revealNodes = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduced.matches) {
    body.classList.add('js-motion');
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); revealObserver.unobserve(entry.target); }
      });
    }, { threshold: .08 });
    revealNodes.forEach(node => revealObserver.observe(node));
  }

  const particles = document.querySelector('.particle-field');
  if (!reduced.matches) {
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < 18; i++) {
      const particle = document.createElement('i');
      particle.style.left = `${38 + (i * 17 % 60)}%`;
      particle.style.top = `${8 + (i * 13 % 76)}%`;
      particle.style.animationDelay = `${-(i * .65)}s`;
      fragment.append(particle);
    }
    particles.append(fragment);
  }
  const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
  hero.addEventListener('pointermove', event => {
    if (!finePointer.matches || effectsPaused || !heroVisible || heroFrame) return;
    heroFrame = requestAnimationFrame(() => {
      const rect = hero.getBoundingClientRect();
      hero.style.setProperty('--scene-x', `${((event.clientX - rect.left) / rect.width - .5) * 14}px`);
      hero.style.setProperty('--scene-y', `${((event.clientY - rect.top) / rect.height - .5) * 10}px`);
      heroFrame = 0;
    });
  }, { passive: true });
  hero.addEventListener('pointerleave', () => { hero.style.setProperty('--scene-x', '0px'); hero.style.setProperty('--scene-y', '0px'); });
  document.querySelectorAll('.bento').forEach(card => card.addEventListener('pointermove', event => {
    if (!finePointer.matches || effectsPaused) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--glow-x', `${(event.clientX - rect.left) / rect.width * 100}%`);
    card.style.setProperty('--glow-y', `${(event.clientY - rect.top) / rect.height * 100}%`);
  }, { passive: true }));

  function mediaAllowed() {
    const connection = navigator.connection;
    return !effectsPaused && !reduced.matches && !mobile.matches && !connection?.saveData && !['slow-2g', '2g', '3g'].includes(connection?.effectiveType);
  }
  function syncVideo() {
    if (mediaLoaded && mediaAllowed() && heroVisible && !document.hidden) {
      video.play().then(() => video.classList.add('is-playing')).catch(() => video.classList.remove('is-playing'));
    } else { video.pause(); video.classList.remove('is-playing'); }
  }
  async function loadMedia() {
    if (mediaLoaded || mediaLoading || !mediaAllowed()) return;
    mediaLoading = true;
    try {
      // HEAD avoids a broken media request when a loop has not been supplied.
      const types = [
        { url: '/assets/recepia-secretaria-loop.webm', type: 'video/webm' },
        { url: '/assets/recepia-secretaria-loop.mp4', type: 'video/mp4' }
      ];
      const supported = types.filter(source => video.canPlayType(source.type));
      const found = await Promise.all(supported.map(async source => {
        const response = await fetch(source.url, { method: 'HEAD', cache: 'no-cache' });
        return response.ok && response.headers.get('Content-Type')?.startsWith('video/') ? { ...source, modified: Date.parse(response.headers.get('Last-Modified') || '') || 0 } : null;
      }));
      const sources = found.filter(Boolean);
      // A newly replaced MP4 takes priority over an older WebM automatically.
      sources.sort((a, b) => b.modified - a.modified);
      for (const source of sources) {
        const element = document.createElement('source');
        element.src = source.url; element.type = source.type; video.append(element);
      }
      if (sources.length) { mediaLoaded = true; video.load(); syncVideo(); }
    } catch { /* Keep the image and CSS motion when media is unavailable. */ }
    finally { mediaLoading = false; }
  }
  video.addEventListener('error', () => video.classList.remove('is-playing'));
  const image = document.querySelector('.hero-image');
  function queueMedia() {
    if ('requestIdleCallback' in window) requestIdleCallback(loadMedia, { timeout: 1800 });
    else setTimeout(loadMedia, 250);
  }
  if (image.complete) queueMedia(); else image.addEventListener('load', queueMedia, { once: true });
  mobile.addEventListener('change', () => { loadMedia(); syncVideo(); });

  const messages = document.getElementById('chat-messages');
  const demoState = document.getElementById('demo-state');
  const result = document.getElementById('dashboard-result');
  const count = document.getElementById('demo-count');
  const channel = document.getElementById('channel-status');
  const pauseButton = document.getElementById('pause-demo');
  const scenarios = {
    booking: {
      messages: [['customer', 'Olá, tem horário amanhã às 14h?'], ['ai', 'Temos sim. Qual serviço você gostaria?'], ['customer', 'Lavagem completa.'], ['ai', 'Perfeito. Posso confirmar para amanhã às 14h?'], ['customer', 'Pode.'], ['ai', 'Agendamento confirmado ✅']],
      title: 'Novo agendamento criado', detail: 'Amanhã, 14h · Lavagem completa', icon: 'calendar', count: '1', channel: 'Assistente IA'
    },
    price: {
      messages: [['customer', 'Quanto custa a lavagem completa?'], ['ai', 'Neste exemplo, a lavagem completa custa R$ 80 e dura 60 minutos.'], ['customer', 'Vocês fazem lavagem interna também?'], ['ai', 'Sim, ela está incluída no serviço deste exemplo. Quer consultar um horário?']],
      title: 'Dúvida respondida', detail: 'Preço e serviço consultados no catálogo ilustrativo.', icon: 'list', count: '0', channel: 'Assistente IA'
    },
    human: {
      messages: [['customer', 'Quero falar com alguém'], ['ai', 'Claro. Vou encaminhar a conversa para a equipe.'], ['ai', 'Atendimento humano ativo. A equipe pode continuar pelo painel.']],
      title: 'Atendimento humano ativo', detail: 'A conversa fica disponível para a equipe no painel.', icon: 'users', count: '0', channel: 'Equipe da empresa'
    },
    info: {
      messages: [['customer', 'Qual é o horário de funcionamento?'], ['ai', 'Neste exemplo, atendemos de segunda a sexta, das 8h às 18h.'], ['customer', 'Como faço para marcar um horário?'], ['ai', 'Me conte qual serviço você precisa. Vou consultar a disponibilidade da agenda.']],
      title: 'Informações da empresa consultadas', detail: 'Respostas baseadas na configuração do negócio.', icon: 'case', count: '0', channel: 'Assistente IA'
    }
  };
  let scenario = 'booking';
  let cursor = 0;
  let timer = null;
  let demoVisible = false;
  let demoPaused = false;
  let demoStarted = false;
  let complete = false;
  function stopTimer() { clearTimeout(timer); timer = null; }
  function finishDemo() {
    stopTimer(); complete = true;
    const data = scenarios[scenario];
    result.replaceChildren();
    const symbol = document.createElement('span'); symbol.className = 'result-symbol';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.classList.add('icon');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use'); use.setAttribute('href', `#i-${data.icon}`); svg.append(use); symbol.append(svg);
    const heading = document.createElement('h4'); heading.textContent = data.title;
    const detail = document.createElement('p'); detail.textContent = data.detail;
    result.append(symbol, heading, detail); result.classList.add('is-complete');
    count.textContent = data.count; channel.textContent = data.channel;
    demoState.textContent = 'Demonstração concluída';
    pauseButton.disabled = true;
  }
  function appendMessage() {
    const data = scenarios[scenario].messages[cursor];
    const message = document.createElement('div');
    message.className = `message ${data[0]}`;
    if (scenario === 'booking' && cursor === scenarios[scenario].messages.length - 1) message.classList.add('confirmed');
    const text = document.createElement('span'); text.textContent = data[1].replace('✅', '').trim(); message.append(text);
    if (message.classList.contains('confirmed')) {
      const check = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); check.classList.add('icon'); check.setAttribute('aria-label', 'Confirmado');
      const use = document.createElementNS('http://www.w3.org/2000/svg', 'use'); use.setAttribute('href', '#i-check'); check.append(use); message.append(check);
    }
    const who = document.createElement('small'); who.textContent = data[0] === 'customer' ? 'Cliente' : 'Recepia'; message.append(who);
    messages.append(message); messages.scrollTop = messages.scrollHeight; cursor++;
  }
  function tick() {
    stopTimer();
    if (!demoVisible || demoPaused || document.hidden || complete) return;
    if (effectsPaused || reduced.matches) {
      while (cursor < scenarios[scenario].messages.length) appendMessage();
      finishDemo(); return;
    }
    if (cursor < scenarios[scenario].messages.length) { appendMessage(); demoState.textContent = 'Atendimento em andamento'; timer = setTimeout(tick, 1050); }
    else finishDemo();
  }
  function resetDemo(key) {
    stopTimer(); scenario = key; cursor = 0; complete = false; demoPaused = false; demoStarted = true;
    messages.replaceChildren(); result.classList.remove('is-complete');
    result.innerHTML = '<span class="result-symbol"><svg class="icon"><use href="#i-calendar"/></svg></span><h4>A conversa começa no WhatsApp.</h4><p>O resultado aparece aqui.</p>';
    count.textContent = '0'; channel.textContent = 'Assistente IA';
    demoState.textContent = 'Pronto para começar'; pauseButton.disabled = false; pauseButton.textContent = 'Pausar'; pauseButton.setAttribute('aria-pressed', 'false');
    document.querySelectorAll('[data-scenario]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.scenario === key)));
    tick();
  }
  document.querySelectorAll('[data-scenario]').forEach(button => button.addEventListener('click', () => resetDemo(button.dataset.scenario)));
  document.getElementById('replay-demo').addEventListener('click', () => resetDemo(scenario));
  pauseButton.addEventListener('click', () => {
    demoPaused = !demoPaused; pauseButton.setAttribute('aria-pressed', String(demoPaused)); pauseButton.textContent = demoPaused ? 'Continuar' : 'Pausar';
    demoState.textContent = demoPaused ? 'Demonstração pausada' : 'Atendimento em andamento';
    if (demoPaused) stopTimer(); else tick();
  });

  const humanButton = document.getElementById('human-toggle');
  const humanStatus = document.getElementById('human-status');
  let aiActive = false;
  humanButton.addEventListener('click', () => {
    aiActive = !aiActive; humanButton.setAttribute('aria-pressed', String(aiActive));
    humanStatus.classList.toggle('ai-active', aiActive);
    humanStatus.replaceChildren();
    const dot = document.createElement('span'); dot.className = 'status-indicator'; humanStatus.append(dot, document.createTextNode(aiActive ? 'Atendimento por IA ativo' : 'Atendimento humano ativo'));
    document.getElementById('human-response').textContent = aiActive ? 'A IA pode continuar o atendimento com as informações da empresa.' : 'Sua equipe pode continuar a conversa pelo painel.';
    humanButton.textContent = aiActive ? 'Assumir atendimento' : 'Reativar IA';
  });

  function syncEffects() {
    body.classList.toggle('effects-off', effectsPaused || reduced.matches);
    motionButton.setAttribute('aria-pressed', String(effectsPaused || reduced.matches));
    motionButton.textContent = reduced.matches ? 'Movimento reduzido ativo' : effectsPaused ? 'Ativar efeitos' : 'Pausar efeitos';
    motionButton.disabled = reduced.matches;
    syncVideo();
    if (effectsPaused || reduced.matches) { revealNodes.forEach(node => node.classList.add('is-visible')); tick(); }
  }
  motionButton.addEventListener('click', () => { effectsPaused = !effectsPaused; syncEffects(); loadMedia(); });
  reduced.addEventListener('change', () => { effectsPaused = reduced.matches; syncEffects(); loadMedia(); });
  if ('IntersectionObserver' in window) {
    const viewportObserver = new IntersectionObserver(entries => {
      for (const entry of entries) {
        entry.target.classList.toggle('is-outside', !entry.isIntersecting);
        if (entry.target === hero) { heroVisible = entry.isIntersecting; syncVideo(); }
        if (entry.target.id === 'demonstracao') {
          demoVisible = entry.isIntersecting;
          if (!demoVisible) stopTimer();
          else if (!demoStarted) resetDemo(scenario);
          else tick();
        }
      }
    }, { threshold: .08 });
    document.querySelectorAll('main>section, .connection-strip').forEach(section => viewportObserver.observe(section));
  } else { demoVisible = true; resetDemo(scenario); }
  document.addEventListener('visibilitychange', () => { syncVideo(); if (document.hidden) stopTimer(); else tick(); });
  syncEffects();
})();
