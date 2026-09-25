/**
 * Dashboard SPA Engine Dinâmico - Estação Atalaia
 * Orquestração com suporte a filtros triplos (data/hora/local), exclusão, psicrometria e renderização offline.
 */

let filtroDataInicio = null;
let filtroDataFim = null;
let filtroHoraInicio = null;
let filtroHoraFim = null;
let filtroLocal = 'TODOS';

const darkPlotlyLayout = {
  paper_bgcolor: '#151d30',
  plot_bgcolor: '#151d30',
  font: { color: '#8b949e', family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
  xaxis: { gridcolor: '#212c42', zerolinecolor: '#212c42' },
  yaxis: { gridcolor: '#212c42', zerolinecolor: '#212c42' },
  margin: { t: 40, r: 30, l: 50, b: 40 },
  hovermode: 'closest'
};

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  carregarOpcoesLocais();
  atualizarTudo();
  setInterval(verificarStatusESP, 3000);
  setInterval(() => {
    if (!temFiltroAtivo()) {
      atualizarTudo();
    }
  }, 5000);
});

function temFiltroAtivo() {
  return !!(filtroDataInicio || filtroDataFim || filtroHoraInicio || filtroHoraFim || (filtroLocal && filtroLocal !== 'TODOS'));
}

function setupEventListeners() {
  document.getElementById('btn-filtrar').addEventListener('click', () => {
    filtroDataInicio = document.getElementById('filtro-data-inicio').value || null;
    filtroDataFim = document.getElementById('filtro-data-fim').value || null;
    filtroHoraInicio = document.getElementById('filtro-hora-inicio').value || null;
    filtroHoraFim = document.getElementById('filtro-hora-fim').value || null;
    filtroLocal = document.getElementById('filtro-local').value || 'TODOS';

    document.getElementById('refresh-indicator-text').innerText = temFiltroAtivo() ? 'Filtro Dinâmico Ativo' : 'Atualização automática ativa';
    atualizarLinksExportacao();
    atualizarTudo();
  });

  document.getElementById('btn-limpar-filtro').addEventListener('click', () => {
    ['filtro-data-inicio', 'filtro-data-fim', 'filtro-hora-inicio', 'filtro-hora-fim'].forEach(id => document.getElementById(id).value = '');
    document.getElementById('filtro-local').value = 'TODOS';

    filtroDataInicio = null;
    filtroDataFim = null;
    filtroHoraInicio = null;
    filtroHoraFim = null;
    filtroLocal = 'TODOS';

    document.getElementById('refresh-indicator-text').innerText = 'Atualização automática ativa';
    atualizarLinksExportacao();
    atualizarTudo();
  });

  document.getElementById('btn-sync').addEventListener('click', executarSincronizacao);
  document.getElementById('btn-excluir-filtrados').addEventListener('click', excluirFiltrados);
  document.getElementById('btn-limpar-tudo').addEventListener('click', limparBancoCompleto);
}

async function carregarOpcoesLocais() {
  try {
    const res = await fetch('/api/locais');
    const locais = await res.json();
    const select = document.getElementById('filtro-local');
    const valorAtual = select.value;
    
    select.innerHTML = '<option value="TODOS">Todos os Locais</option>';
    locais.forEach(loc => {
      const opt = document.createElement('option');
      opt.value = loc;
      opt.innerText = loc;
      select.appendChild(opt);
    });
    select.value = valorAtual;
  } catch (err) {
    console.error("Falha ao carregar locais:", err);
  }
}

function buildApiUrl(base) {
  const params = [];
  if (filtroDataInicio) params.push(`data_inicio=${encodeURIComponent(filtroDataInicio)}`);
  if (filtroDataFim) params.push(`data_fim=${encodeURIComponent(filtroDataFim)}`);
  if (filtroHoraInicio) params.push(`hora_inicio=${encodeURIComponent(filtroHoraInicio)}`);
  if (filtroHoraFim) params.push(`hora_fim=${encodeURIComponent(filtroHoraFim)}`);
  if (filtroLocal && filtroLocal !== 'TODOS') params.push(`local=${encodeURIComponent(filtroLocal)}`);

  return params.length > 0 ? `${base}?${params.join('&')}` : base;
}

function atualizarLinksExportacao() {
  const url = buildApiUrl('');
  const query = url.startsWith('?') ? url : (url.includes('?') ? '?' + url.split('?')[1] : '');
  document.getElementById('exp-csv').href = `/api/exportar/csv${query}`;
  document.getElementById('exp-xlsx').href = `/api/exportar/excel${query}`;
}

async function verificarStatusESP() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    
    const dot = document.getElementById('esp-status-dot');
    const text = document.getElementById('esp-status-text');
    const pending = document.getElementById('esp-pending-val');

    dot.className = data.esp32_conectada ? 'dot online' : 'dot offline';
    text.innerText = data.esp32_conectada ? 'ESP32 Conectada' : 'ESP32 Offline (AP)';
    pending.innerText = data.registros_pendentes_esp32;
  } catch (e) {
    console.error("Erro checando status:", e);
  }
}

async function executarSincronizacao() {
  const btn = document.getElementById('btn-sync');
  const msg = document.getElementById('sync-msg');
  const localInput = document.getElementById('sync-local-input').value.trim() || 'Sede Principal';

  btn.disabled = true;
  btn.innerText = 'Transferindo...';
  msg.innerText = '';

  try {
    const res = await fetch('/api/sincronizar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ local: localInput })
    });
    const data = await res.json();
    msg.style.color = data.sucesso ? '#10b981' : '#ef4444';
    msg.innerText = data.mensagem;
    if (data.sucesso) {
      await carregarOpcoesLocais();
      atualizarTudo();
    }
  } catch (err) {
    msg.style.color = '#ef4444';
    msg.innerText = 'Falha crítica de comunicação com a ESP32/Flask.';
  } finally {
    btn.disabled = false;
    btn.innerText = 'SINCRONIZAR ESP32';
  }
}

async function excluirFiltrados() {
  const msg = document.getElementById('delete-msg');
  if (!confirm("Deseja realmente excluir todos os registros que atendem aos filtros atuais?")) return;

  try {
    const payload = {
      limpar_tudo: false,
      data_inicio: filtroDataInicio,
      data_fim: filtroDataFim,
      hora_inicio: filtroHoraInicio,
      hora_fim: filtroHoraFim,
      local: filtroLocal
    };

    const res = await fetch('/api/excluir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    msg.style.color = '#10b981';
    msg.innerText = data.mensagem;
    await carregarOpcoesLocais();
    atualizarTudo();
  } catch (err) {
    msg.style.color = '#ef4444';
    msg.innerText = 'Erro ao excluir registros filtrados.';
  }
}

async function limparBancoCompleto() {
  const msg = document.getElementById('delete-msg');
  if (!confirm("ATENÇÃO: Deseja apagar ABSOLUTAMENTE TODOS os dados do SQLite?")) return;
  if (prompt("Digite 'EXCLUIR' para confirmar a limpeza total:") !== 'EXCLUIR') {
    alert("Operação cancelada.");
    return;
  }

  try {
    const res = await fetch('/api/excluir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limpar_tudo: true })
    });
    const data = await res.json();
    msg.style.color = '#10b981';
    msg.innerText = data.mensagem;
    await carregarOpcoesLocais();
    atualizarTudo();
  } catch (err) {
    msg.style.color = '#ef4444';
    msg.innerText = 'Erro ao limpar banco completo.';
  }
}

async function atualizarTudo() {
  try {
    const [resStats, resDados, resUltimos] = await Promise.all([
      fetch(buildApiUrl('/api/estatisticas')),
      fetch(buildApiUrl('/api/dados')),
      fetch(buildApiUrl('/api/ultimos'))
    ]);

    const stats = await resStats.json();
    const dados = await resDados.json();
    const ultimos = await resUltimos.json();

    renderizarCards(stats);
    renderizarTabelasDescritivas(stats);
    renderizarGraficos(dados);
    renderizarTabelaBrutos(ultimos);
  } catch (e) {
    console.error("Erro atualizando dashboard:", e);
  }
}

function setElem(id, val) {
  const el = document.getElementById(id);
  if (el) el.innerText = val !== undefined && val !== null ? val : '--';
}

function renderizarCards(s) {
  if (!s || s.total_registros === 0) {
    setElem('card-temp-atual', '-- °C');
    setElem('card-hum-atual', '-- %');
    setElem('card-total-registros', '0');
    return;
  }

  setElem('card-temp-atual', `${s.temperatura.atual.toFixed(1)} °C`);
  setElem('card-temp-media', s.temperatura.descritiva.media);
  setElem('card-temp-min', s.temperatura.descritiva.minimo);
  setElem('card-temp-max', s.temperatura.descritiva.maximo);

  setElem('card-hum-atual', `${s.umidade.atual.toFixed(1)} %`);
  setElem('card-hum-media', s.umidade.descritiva.media);
  setElem('card-hum-min', s.umidade.descritiva.minimo);
  setElem('card-hum-max', s.umidade.descritiva.maximo);

  setElem('card-dp-atual', `${s.ponto_orvalho.atual.toFixed(1)} °C`);
  setElem('card-hi-atual', `${s.sensacao_termica.atual.toFixed(1)} °C`);

  setElem('card-total-registros', s.total_registros);
  setElem('card-tempo-total', `${(s.tempo_monitoramento_segundos / 60).toFixed(1)} min`);

  setElem('card-correlacao', s.bivariada.correlacao_pearson);
  setElem('card-covariancia', s.bivariada.covariancia);

  // Psicrometria & Bioclima
  const psi = s.psicrometria_avancada;
  setElem('card-vp-atual', `${psi.pressao_vapor_atual.toFixed(1)} hPa`);
  setElem('card-vp-media', psi.pressao_vapor_descritiva.media);
  setElem('card-ah-atual', `${psi.umidade_absoluta_atual.toFixed(1)} g/m³`);
  setElem('card-ent-atual', `${psi.entalpia_atual.toFixed(1)} kJ/kg`);
  setElem('card-thom-atual', psi.indice_thom_atual.toFixed(1));
  setElem('card-thom-class', psi.indice_thom_classificacao);

  // Relações & Regressões
  setElem('ind-delta-orvalho', s.indicadores_derivados.diferenca_temperatura_orvalho);
  setElem('ind-razao-amp', s.indicadores_derivados.razao_amplitudes);

  setElem('reg-t-eq', s.temperatura.regressao.equacao);
  setElem('reg-t-angular', s.temperatura.regressao.coef_angular);
  setElem('reg-t-r2', s.temperatura.regressao.r2);
  setElem('reg-t-tend', s.temperatura.regressao.tendencia);

  setElem('reg-h-eq', s.umidade.regressao.equacao);
  setElem('reg-h-angular', s.umidade.regressao.coef_angular);
  setElem('reg-h-r2', s.umidade.regressao.r2);
  setElem('reg-h-tend', s.umidade.regressao.tendencia);
}

function preencherLinhaEstatistica(prefixo, d, taxa) {
  setElem(`${prefixo}-med`, d.media);
  setElem(`${prefixo}-mediana`, d.mediana);
  setElem(`${prefixo}-moda`, d.moda);
  setElem(`${prefixo}-min`, d.minimo);
  setElem(`${prefixo}-max`, d.maximo);
  setElem(`${prefixo}-amp`, d.amplitude);
  setElem(`${prefixo}-std`, d.desvio_padrao);
  setElem(`${prefixo}-var`, d.variancia);
  setElem(`${prefixo}-mad`, d.mad);
  setElem(`${prefixo}-cv`, `${d.coef_variacao}%`);
  setElem(`${prefixo}-iqr`, d.iqr);
  setElem(`${prefixo}-assim`, d.assimetria);
  setElem(`${prefixo}-curt`, d.curtose);
  setElem(`${prefixo}-rate`, taxa);
}

function renderizarTabelasDescritivas(s) {
  if (!s || s.total_registros === 0) return;
  preencherLinhaEstatistica('t', s.temperatura.descritiva, `${s.temperatura.taxa_por_hora} °C/h`);
  preencherLinhaEstatistica('h', s.umidade.descritiva, `${s.umidade.taxa_por_hora} %/h`);
}

function calcularMediaMovel(arr, k) {
  const res = [];
  for (let i = 0; i < arr.length; i++) {
    const inicio = Math.max(0, i - k + 1);
    const sub = arr.slice(inicio, i + 1);
    res.push(sub.reduce((a, b) => a + b, 0) / sub.length);
  }
  return res;
}

function renderizarGraficos(dados) {
  if (typeof Plotly === 'undefined') {
    console.warn("Plotly offline não encontrado em static/js/plotly.min.js.");
    return;
  }

  const chartIds = [
    'chart-temp-hum-tempo', 'chart-temp-tempo', 'chart-temp-ma', 'chart-hum-tempo',
    'chart-hum-ma', 'chart-ah-tempo', 'chart-thom-tempo', 'chart-dispersao',
    'chart-regressoes-comparadas', 'chart-hist-temp', 'chart-hist-hum',
    'chart-box-temp', 'chart-box-hum', 'chart-orvalho-tempo', 'chart-sensacao-tempo'
  ];

  if (!dados || dados.length === 0) {
    chartIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) Plotly.purge(id);
    });
    return;
  }

  const timestamps = dados.map(d => d.timestamp);
  const temperaturas = dados.map(d => d.temperatura);
  const umidades = dados.map(d => d.umidade);
  const pontosOrvalho = dados.map(d => d.ponto_orvalho);
  const sensacoes = dados.map(d => d.sensacao_termica);
  const umidadesAbs = dados.map(d => d.umidade_absoluta);
  const indicesThom = dados.map(d => d.indice_thom);

  // 1. Eixo Duplo Temporal Integrado
  Plotly.react('chart-temp-hum-tempo', [
    { x: timestamps, y: temperaturas, name: 'Temperatura (°C)', type: 'scatter', mode: 'lines+markers', line: { color: '#ff5e62', width: 2 } },
    { x: timestamps, y: umidades, name: 'Umidade (%)', yaxis: 'y2', type: 'scatter', mode: 'lines+markers', line: { color: '#00d2ff', width: 2 } }
  ], {
    ...darkPlotlyLayout,
    title: 'Monitoramento Temporal Integrado (Temperatura e Umidade)',
    yaxis: { title: 'Temperatura (°C)', titlefont: { color: '#ff5e62' }, tickfont: { color: '#ff5e62' }, gridcolor: '#212c42' },
    yaxis2: { title: 'Umidade (%)', titlefont: { color: '#00d2ff' }, tickfont: { color: '#00d2ff' }, overlaying: 'y', side: 'right', gridcolor: '#212c42' }
  }, { responsive: true });

  // 2. Temperatura Individual e Média Móvel
  const maTemp = calcularMediaMovel(temperaturas, 5);
  Plotly.react('chart-temp-tempo', [
    { x: timestamps, y: temperaturas, type: 'scatter', mode: 'lines', line: { color: '#ff5e62' }, name: 'Temp' }
  ], { ...darkPlotlyLayout, title: 'Temperatura ao Longo do Tempo' }, { responsive: true });

  Plotly.react('chart-temp-ma', [
    { x: timestamps, y: temperaturas, type: 'scatter', mode: 'lines', opacity: 0.3, name: 'Bruto', line: { color: '#ff5e62' } },
    { x: timestamps, y: maTemp, type: 'scatter', mode: 'lines', name: 'Média Móvel (k=5)', line: { color: '#fff', width: 2 } }
  ], { ...darkPlotlyLayout, title: 'Tendência Suavizada: Temperatura' }, { responsive: true });

  // 3. Umidade Individual e Média Móvel
  const maHum = calcularMediaMovel(umidades, 5);
  Plotly.react('chart-hum-tempo', [
    { x: timestamps, y: umidades, type: 'scatter', mode: 'lines', line: { color: '#00d2ff' }, name: 'Umidade' }
  ], { ...darkPlotlyLayout, title: 'Umidade Relativa ao Longo do Tempo' }, { responsive: true });

  Plotly.react('chart-hum-ma', [
    { x: timestamps, y: umidades, type: 'scatter', mode: 'lines', opacity: 0.3, name: 'Bruto', line: { color: '#00d2ff' } },
    { x: timestamps, y: maHum, type: 'scatter', mode: 'lines', name: 'Média Móvel (k=5)', line: { color: '#fff', width: 2 } }
  ], { ...darkPlotlyLayout, title: 'Tendência Suavizada: Umidade' }, { responsive: true });

  // 4. Psicrometria e Thom
  Plotly.react('chart-ah-tempo', [
    { x: timestamps, y: umidadesAbs, mode: 'lines+markers', line: { color: '#38ef7d' } }
  ], { ...darkPlotlyLayout, title: 'Umidade Absoluta ao Longo do Tempo (g/m³)' }, { responsive: true });

  Plotly.react('chart-thom-tempo', [
    { x: timestamps, y: indicesThom, mode: 'lines+markers', line: { color: '#f7b733' } }
  ], { ...darkPlotlyLayout, title: 'Evolução do Índice de Desconforto de Thom' }, { responsive: true });

  // 5. Dispersão e Séries Comparadas
  Plotly.react('chart-dispersao', [
    { x: temperaturas, y: umidades, mode: 'markers', type: 'scatter', marker: { size: 7, color: '#38ef7d', opacity: 0.8 }, name: 'Amostras' }
  ], { ...darkPlotlyLayout, title: 'Diagrama de Dispersão (Temperatura vs Umidade)', xaxis: { title: 'Temperatura (°C)' }, yaxis: { title: 'Umidade (%)' } }, { responsive: true });

  Plotly.react('chart-regressoes-comparadas', [
    { x: timestamps, y: temperaturas, mode: 'lines', name: 'Temp Real', line: { color: '#ff5e62' } },
    { x: timestamps, y: umidades, mode: 'lines', name: 'Umidade Real', line: { color: '#00d2ff' } }
  ], { ...darkPlotlyLayout, title: 'Séries Históricas Comparadas' }, { responsive: true });

  // 6. Histogramas e Boxplots
  Plotly.react('chart-hist-temp', [{ x: temperaturas, type: 'histogram', marker: { color: '#ff5e62' }, nbinsx: 15 }], { ...darkPlotlyLayout, title: 'Histograma de Temperatura' }, { responsive: true });
  Plotly.react('chart-hist-hum', [{ x: umidades, type: 'histogram', marker: { color: '#00d2ff' }, nbinsx: 15 }], { ...darkPlotlyLayout, title: 'Histograma de Umidade' }, { responsive: true });
  Plotly.react('chart-box-temp', [{ y: temperaturas, type: 'box', marker: { color: '#ff5e62' }, name: 'Temp' }], { ...darkPlotlyLayout, title: 'Boxplot: Temperatura' }, { responsive: true });
  Plotly.react('chart-box-hum', [{ y: umidades, type: 'box', marker: { color: '#00d2ff' }, name: 'Umidade' }], { ...darkPlotlyLayout, title: 'Boxplot: Umidade' }, { responsive: true });

  // 7. Ponto de Orvalho e Sensação Térmica
  Plotly.react('chart-orvalho-tempo', [{ x: timestamps, y: pontosOrvalho, mode: 'lines+markers', line: { color: '#38ef7d' } }], { ...darkPlotlyLayout, title: 'Histórico do Ponto de Orvalho (°C)' }, { responsive: true });
  Plotly.react('chart-sensacao-tempo', [{ x: timestamps, y: sensacoes, mode: 'lines+markers', line: { color: '#f7b733' } }], { ...darkPlotlyLayout, title: 'Histórico de Sensação Térmica (°C)' }, { responsive: true });
}

function renderizarTabelaBrutos(amostras) {
  const tbody = document.querySelector('#tabela-brutos tbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  amostras.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.esp_seq}</td>
      <td><span class="status-badge" style="background: rgba(0,210,255,0.1); color: #00d2ff; padding: 2px 6px; border-radius: 4px;">${r.local}</span></td>
      <td>${r.timestamp}</td>
      <td><strong>${r.temperatura.toFixed(2)}</strong></td>
      <td><strong>${r.umidade.toFixed(2)}</strong></td>
      <td>${r.ponto_orvalho.toFixed(2)}</td>
      <td>${r.sensacao_termica.toFixed(2)}</td>
      <td>${r.umidade_absoluta ? r.umidade_absoluta.toFixed(2) : '--'}</td>
      <td>${r.indice_thom ? r.indice_thom.toFixed(2) : '--'}</td>
      <td>${r.intervalo_segundos}s</td>
    `;
    tbody.appendChild(tr);
  });
}