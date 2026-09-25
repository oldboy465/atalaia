/**
 * Dashboard SPA Engine Dinâmico - Estação Atalaia
 * Orquestração com suporte a filtros triplos (data/hora/local), exclusão e psicrometria completa.
 */

let filtroDataInicio = null;
let filtroDataFim = null;
let filtroHoraInicio = null;
let filtroHoraFim = null;
let filtroLocal = 'TODOS';

const darkPlotlyLayout = {
  paper_bgcolor: '#151d30',
  plot_bgcolor: '#151d30',
  font: { color: '#8b949e', family: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif' },
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
    // Atualiza periodicamente apenas se o usuário não estiver com filtros ativos
    if (!temFiltroAtivo()) {
      atualizarTudo();
    }
  }, 5000);
});

function temFiltroAtivo() {
  return filtroDataInicio || filtroDataFim || filtroHoraInicio || filtroHoraFim || (filtroLocal && filtroLocal !== 'TODOS');
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
    document.getElementById('filtro-data-inicio').value = '';
    document.getElementById('filtro-data-fim').value = '';
    document.getElementById('filtro-hora-inicio').value = '';
    document.getElementById('filtro-hora-fim').value = '';
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
    
    // Preserva o valor selecionado
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

    if (data.esp32_conectada) {
      dot.className = 'dot online';
      text.innerText = 'ESP32 Conectada';
    } else {
      dot.className = 'dot offline';
      text.innerText = 'ESP32 Offline (AP)';
    }
    pending.innerText = data.registros_pendentes_esp32;
  } catch (e) {
    console.error("Erro verificando status do ESP32:", e);
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
    if (data.sucesso) {
      msg.style.color = '#10b981';
      msg.innerText = data.mensagem;
      await carregarOpcoesLocais();
      atualizarTudo();
    } else {
      msg.style.color = '#ef4444';
      msg.innerText = data.mensagem;
    }
  } catch (err) {
    msg.style.color = '#ef4444';
    msg.innerText = 'Falha crítica de comunicação durante sincronização.';
  } finally {
    btn.disabled = false;
    btn.innerText = 'SINCRONIZAR ESP32';
  }
}

async function excluirFiltrados() {
  const msg = document.getElementById('delete-msg');
  const confirmacao = confirm("Deseja realmente excluir todos os registros que atendem aos filtros atuais?");
  if (!confirmacao) return;

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
  const confirmacao1 = confirm("ATENÇÃO: Deseja apagar ABSOLUTAMENTE TODOS os dados do SQLite?");
  if (!confirmacao1) return;
  const confirmacao2 = prompt("Digite 'EXCLUIR' para confirmar a limpeza total:");
  if (confirmacao2 !== 'EXCLUIR') {
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
    console.error("Erro renderizando dados dinâmicos:", e);
  }
}

function renderizarCards(s) {
  if (!s || s.total_registros === 0) {
    document.getElementById('card-temp-atual').innerText = '-- °C';
    document.getElementById('card-hum-atual').innerText = '-- %';
    document.getElementById('card-total-registros').innerText = '0';
    return;
  }

  document.getElementById('card-temp-atual').innerText = `${s.temperatura.atual.toFixed(1)} °C`;
  document.getElementById('card-temp-media').innerText = s.temperatura.descritiva.media;
  document.getElementById('card-temp-min').innerText = s.temperatura.descritiva.minimo;
  document.getElementById('card-temp-max').innerText = s.temperatura.descritiva.maximo;

  document.getElementById('card-hum-atual').innerText = `${s.umidade.atual.toFixed(1)} %`;
  document.getElementById('card-hum-media').innerText = s.umidade.descritiva.media;
  document.getElementById('card-hum-min').innerText = s.umidade.descritiva.minimo;
  document.getElementById('card-hum-max').innerText = s.umidade.descritiva.maximo;

  document.getElementById('card-dp-atual').innerText = `${s.ponto_orvalho.atual.toFixed(1)} °C`;
  document.getElementById('card-hi-atual').innerText = `${s.sensacao_termica.atual.toFixed(1)} °C`;

  document.getElementById('card-total-registros').innerText = s.total_registros;
  document.getElementById('card-tempo-total').innerText = `${(s.tempo_monitoramento_segundos / 60).toFixed(1)} min`;

  document.getElementById('card-correlacao').innerText = s.bivariada.correlacao_pearson;
  document.getElementById('card-covariancia').innerText = s.bivariada.covariancia;

  // Psicrometria & Bioclima
  const psi = s.psicrometria_avancada;
  document.getElementById('card-vp-atual').innerText = `${psi.pressao_vapor_atual.toFixed(1)} hPa`;
  document.getElementById('card-vp-media').innerText = psi.pressao_vapor_descritiva.media;
  document.getElementById('card-ah-atual').innerText = `${psi.umidade_absoluta_atual.toFixed(1)} g/m³`;
  document.getElementById('card-ent-atual').innerText = `${psi.entalpia_atual.toFixed(1)} kJ/kg`;
  document.getElementById('card-thom-atual').innerText = psi.indice_thom_atual.toFixed(1);
  document.getElementById('card-thom-class').innerText = psi.indice_thom_classificacao;

  // Derivados & Regressão
  document.getElementById('ind-delta-orvalho').innerText = s.indicadores_derivados.diferenca_temperatura_orvalho;
  document.getElementById('ind-razao-amp').innerText = s.indicadores_derivados.razao_amplitudes;

  document.getElementById('reg-t-eq').innerText = s.temperatura.regressao.equacao;
  document.getElementById('reg-t-angular').innerText = s.temperatura.regressao.coef_angular;
  document.getElementById('reg-t-r2').innerText = s.temperatura.regressao.r2;
  document.getElementById('reg-t-tend').innerText = s.temperatura.regressao.tendencia;

  document.getElementById('reg-h-eq').innerText = s.umidade.regressao.equacao;
  document.getElementById('reg-h-angular').innerText = s.umidade.regressao.coef_angular;
  document.getElementById('reg-h-r2').innerText = s.umidade.regressao.r2;
  document.getElementById('reg-h-tend').innerText = s.umidade.regressao.tendencia;
}

function renderizarTabelasDescritivas(s) {
  if (!s || s.total_registros === 0) return;

  const td = s.temperatura.descritiva;
  document.getElementById('t-med').innerText = td.media;
  document.getElementById('t-mediana').innerText = td.mediana;
  document.getElementById('t-moda').innerText = td.moda;
  document.getElementById('t-min').innerText = td.minimo;
  document.getElementById('t-max').innerText = td.maximo;
  document.getElementById('t-amp').innerText = td.amplitude;
  document.getElementById('t-std').innerText = td.desvio_padrao;
  document.getElementById('t-var').innerText = td.variancia;
  document.getElementById('t-mad').innerText = td.mad;
  document.getElementById('t-cv').innerText = `${td.coef_variacao}%`;
  document.getElementById('t-iqr').innerText = td.iqr;
  document.getElementById('t-assim').innerText = td.assimetria;
  document.getElementById('t-curt').innerText = td.curtose;
  document.getElementById('t-rate').innerText = `${s.temperatura.taxa_por_hora} °C/h`;

  const hd = s.umidade.descritiva;
  document.getElementById('h-med').innerText = hd.media;
  document.getElementById('h-mediana').innerText = hd.mediana;
  document.getElementById('h-moda').innerText = hd.moda;
  document.getElementById('h-min').innerText = hd.minimo;
  document.getElementById('h-max').innerText = hd.maximo;
  document.getElementById('h-amp').innerText = hd.amplitude;
  document.getElementById('h-std').innerText = hd.desvio_padrao;
  document.getElementById('h-var').innerText = hd.variancia;
  document.getElementById('h-mad').innerText = hd.mad;
  document.getElementById('h-cv').innerText = `${hd.coef_variacao}%`;
  document.getElementById('h-iqr').innerText = hd.iqr;
  document.getElementById('h-assim').innerText = hd.assimetria;
  document.getElementById('h-curt').innerText = hd.curtose;
  document.getElementById('h-rate').innerText = `${s.umidade.taxa_por_hora} %/h`;
}

function renderizarGraficos(dados) {
  if (!dados || dados.length === 0) {
    Plotly.purge('chart-temp-hum-tempo');
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
  const trace1 = {
    x: timestamps, y: temperaturas, name: 'Temperatura (°C)',
    type: 'scatter', mode: 'lines+markers', line: { color: '#ff5e62', width: 2 }
  };
  const trace2 = {
    x: timestamps, y: umidades, name: 'Umidade (%)',
    yaxis: 'y2', type: 'scatter', mode: 'lines+markers', line: { color: '#00d2ff', width: 2 }
  };
  const layoutDoubleY = {
    ...darkPlotlyLayout,
    title: 'Monitoramento Temporal Integrado (Temperatura e Umidade)',
    yaxis: { title: 'Temperatura (°C)', titlefont: { color: '#ff5e62' }, tickfont: { color: '#ff5e62' }, gridcolor: '#212c42' },
    yaxis2: {
      title: 'Umidade (%)', titlefont: { color: '#00d2ff' }, tickfont: { color: '#00d2ff' },
      overlaying: 'y', side: 'right', gridcolor: '#212c42'
    }
  };
  Plotly.react('chart-temp-hum-tempo', [trace1, trace2], layoutDoubleY, { responsive: true });

  // 2. Séries de Temperatura + Média Móvel
  const maTemp = calcularMediaMovel(temperaturas, 5);
  Plotly.react('chart-temp-tempo', [{
    x: timestamps, y: temperaturas, type: 'scatter', mode: 'lines', line: { color: '#ff5e62' }, name: 'Temp'
  }], { ...darkPlotlyLayout, title: 'Temperatura ao Longo do Tempo' }, { responsive: true });

  Plotly.react('chart-temp-ma', [
    { x: timestamps, y: temperaturas, type: 'scatter', mode: 'lines', opacity: 0.3, name: 'Bruto', line: { color: '#ff5e62' } },
    { x: timestamps, y: maTemp, type: 'scatter', mode: 'lines', name: 'Média Móvel (k=5)', line: { color: '#fff', width: 2 } }
  ], { ...darkPlotlyLayout, title: 'Tendência Suavizada: Temperatura' }, { responsive: true });

  // 3. Séries de Umidade + Média Móvel
  const maHum = calcularMediaMovel(umidades, 5);
  Plotly.react('chart-hum-tempo', [{
    x: timestamps, y: umidades, type: 'scatter', mode: 'lines', line: { color: '#00d2ff' }, name: 'Umidade'
  }], { ...darkPlotlyLayout, title: 'Umidade Relativa ao Longo do Tempo' }, { responsive: true });

  Plotly.react('chart-hum-ma', [
    { x: timestamps, y: umidades, type: 'scatter', mode: 'lines', opacity: 0.3, name: 'Bruto', line: { color: '#00d2ff' } },
    { x: timestamps, y: maHum, type: 'scatter', mode: 'lines', name: 'Média Móvel (k=5)', line: { color: '#fff', width: 2 } }
  ], { ...darkPlotlyLayout, title: 'Tendência Suavizada: Umidade' }, { responsive: true });

  // 4. Psicrometria: Umidade Absoluta e Índice Thom
  Plotly.react('chart-ah-tempo', [{
    x: timestamps, y: umidadesAbs, mode: 'lines+markers', line: { color: '#38ef7d' }
  }], { ...darkPlotlyLayout, title: 'Umidade Absoluta ao Longo do Tempo (g/m³)' }, { responsive: true });

  Plotly.react('chart-thom-tempo', [{
    x: timestamps, y: indicesThom, mode: 'lines+markers', line: { color: '#f7b733' }
  }], { ...darkPlotlyLayout, title: 'Evolução do Índice de Desconforto de Thom' }, { responsive: true });

  // 5. Dispersão e Correlação
  Plotly.react('chart-dispersao', [{
    x: temperaturas, y: umidades, mode: 'markers', type: 'scatter',
    marker: { size: 7, color: '#38ef7d', opacity: 0.8 }, name: 'Amostras'
  }], { ...darkPlotlyLayout, title: 'Diagrama de Dispersão (Temperatura vs Umidade)', xaxis: { title: 'Temperatura (°C)' }, yaxis: { title: 'Umidade (%)' } }, { responsive: true });

  Plotly.react('chart-regressoes-comparadas', [
    { x: timestamps, y: temperaturas, mode: 'lines', name: 'Temp Real', line: { color: '#ff5e62' } },
    { x: timestamps, y: umidades, mode: 'lines', name: 'Umidade Real', line: { color: '#00d2ff' } }
  ], { ...darkPlotlyLayout, title: 'Séries Históricas Comparadas' }, { responsive: true });

  // 6. Histogramas e Boxplots
  Plotly.react('chart-hist-temp', [{
    x: temperaturas, type: 'histogram', marker: { color: '#ff5e62' }, nbinsx: 15
  }], { ...darkPlotlyLayout, title: 'Histograma de Temperatura' }, { responsive: true });

  Plotly.react('chart-hist-hum', [{
    x: umidades, type: 'histogram', marker: { color: '#00d2ff' }, nbinsx: 15
  }], { ...darkPlotlyLayout, title: 'Histograma de Umidade' }, { responsive: true });

  Plotly.react('chart-box-temp', [{
    y: temperaturas, type: 'box', marker: { color: '#ff5e62' }, name: 'Temp'
  }], { ...darkPlotlyLayout, title: 'Boxplot: Temperatura' }, { responsive: true });

  Plotly.react('chart-box-hum', [{
    y: umidades, type: 'box', marker: { color: '#00d2ff' }, name: 'Umidade'
  }], { ...darkPlotlyLayout, title: 'Boxplot: Umidade' }, { responsive: true });

  // 7. Derivados (Ponto de Orvalho e Sensação)
  Plotly.react('chart-orvalho-tempo', [{
    x: timestamps, y: pontosOrvalho, mode: 'lines+markers', line: { color: '#38ef7d' }
  }], { ...darkPlotlyLayout, title: 'Histórico do Ponto de Orvalho (°C)' }, { responsive: true });

  Plotly.react('chart-sensacao-tempo', [{
    x: timestamps, y: sensacoes, mode: 'lines+markers', line: { color: '#f7b733' }
  }], { ...darkPlotlyLayout, title: 'Histórico de Sensação Térmica (°C)' }, { responsive: true });
}

function calcularMediaMovel(arr, k) {
  const res = [];
  for (let i = 0; i < arr.length; i++) {
    const inicio = Math.max(0, i - k + 1);
    const sub = arr.slice(inicio, i + 1);
    const media = sub.reduce((a, b) => a + b, 0) / sub.length;
    res.push(media);
  }
  return res;
}

function renderizarTabelaBrutos(amostras) {
  const tbody = document.querySelector('#tabela-brutos tbody');
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