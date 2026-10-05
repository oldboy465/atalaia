/**
 * PROJETO ATALAIA v1.2 - CORE CONTROLLER
 * Gerencia ciclo de vida da conexão, comandos de controle de energia (Wake/Sleep),
 * modal de extração de dados e atualização dinâmica de listas suspensas.
 */

const AtalaiaApp = {
  pollIntervalMs: 4000,
  timerId: null,
  isOperating: false
};

// Monitoramento Contínuo com Timeout Curto para Evitar Travamentos
async function checkESPStatus() {
  const dot = document.getElementById('espDot');
  const txt = document.getElementById('espStatusText');
  const btnConnect = document.getElementById('btnConnect');

  if (btnConnect) btnConnect.style.opacity = '0.65';

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2600);

    const res = await fetch('/api/esp/status', { signal: controller.signal });
    clearTimeout(timeoutId);

    const data = await res.json();

    if (data.online) {
      dot.className = 'status-dot online';
      const modeStr = data.wifi_mode ? ` (${data.wifi_mode})` : '';
      const regs = data.buffer_count !== undefined ? data.buffer_count : 0;
      txt.innerText = `Online${modeStr} [${regs}/7200]`;
      txt.style.color = '#34d399';
    } else {
      dot.className = 'status-dot offline';
      txt.innerText = 'ESP32: Em Repouso / Desconectado';
      txt.style.color = '#f87171';
    }
  } catch (err) {
    dot.className = 'status-dot offline';
    txt.innerText = 'ESP32: Offline';
    txt.style.color = '#f87171';
  } finally {
    if (btnConnect) btnConnect.style.opacity = '1';
  }
}

function startStatusPolling() {
  checkESPStatus();
  if (AtalaiaApp.timerId) clearInterval(AtalaiaApp.timerId);
  AtalaiaApp.timerId = setInterval(checkESPStatus, AtalaiaApp.pollIntervalMs);
}

// COMANDO PARA LIGAR / RECONECTAR NÓ SENSORIAL
async function triggerWakeup() {
  const btn = document.getElementById('btnWakeup');
  if (btn) {
    btn.disabled = true;
    btn.style.opacity = '0.7';
  }

  try {
    const res = await fetch('/api/esp/wakeup', { method: 'POST' });
    const data = await res.json();
    alert(data.message || 'Sinal de despertar emitido.');
    await checkESPStatus();
  } catch (err) {
    alert('Erro ao tentar comunicar comando de ativação.');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.style.opacity = '1';
    }
  }
}

// COMANDO PARA COLOCAR EM DEEP-SLEEP (DESLIGAR NÓ)
async function triggerShutdown() {
  const confirmMsg = 'Deseja colocar o nó ESP32 em Deep-Sleep para economia de bateria?';
  if (!confirm(confirmMsg)) return;

  const btn = document.getElementById('btnShutdown');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch('/api/esp/shutdown', { method: 'POST' });
    const data = await res.json();
    alert(data.message || data.error);
    await checkESPStatus();
  } catch (err) {
    alert('Falha na transmissão do comando de suspensão.');
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Atualiza dinamicamente as listas suspensas de estações na tela
async function refreshLocaisSelects() {
  try {
    const res = await fetch('/api/locais?with_data=true');
    const locais = await res.json();

    const selectIds = ['filterLocal', 'filterManageLocal', 'mlLocal'];
    selectIds.forEach(id => {
      const select = document.getElementById(id);
      if (!select) return;

      const currentValue = select.value;
      const defaultOption = select.options[0] ? select.options[0].text : '-- Selecione --';

      select.innerHTML = `<option value="">${defaultOption}</option>`;
      locais.forEach(loc => {
        const opt = document.createElement('option');
        opt.value = loc.id;
        opt.text = loc.nome;
        select.appendChild(opt);
      });

      // Preserva o valor selecionado se o local ainda existir com dados
      if (currentValue && locais.some(l => String(l.id) === String(currentValue))) {
        select.value = currentValue;
      } else {
        select.value = "";
      }
    });
  } catch (e) {
    console.error('Erro ao atualizar dropdowns de locais:', e);
  }
}

// Controle do Modal de Extração
function openExtractModal() {
  const modal = document.getElementById('extractModal');
  if (modal) {
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
}

function closeExtractModal() {
  const modal = document.getElementById('extractModal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }
}

function handleModalLocalChange() {
  const select = document.getElementById('modalLocalSelect');
  const nomeInput = document.getElementById('modalLocalNome');
  const latInput = document.getElementById('modalLocalLat');
  const lngInput = document.getElementById('modalLocalLng');

  if (!select || !nomeInput) return;

  const selectedOpt = select.options[select.selectedIndex];
  if (select.value) {
    nomeInput.value = select.value;
    latInput.value = selectedOpt.getAttribute('data-lat') || '';
    lngInput.value = selectedOpt.getAttribute('data-lng') || '';
  } else {
    nomeInput.value = '';
    latInput.value = '';
    lngInput.value = '';
  }
}

// Extração de dados da memória Flash
async function executeExtraction() {
  const nome = document.getElementById('modalLocalNome').value.trim();
  const desc = document.getElementById('modalLocalDesc').value.trim();
  const lat = document.getElementById('modalLocalLat').value.trim();
  const lng = document.getElementById('modalLocalLng').value.trim();
  const btn = document.getElementById('btnConfirmExtract');

  if (!nome) {
    alert('Informe o nome da estação meteorológica para indexação.');
    return;
  }

  btn.disabled = true;
  const originalLabel = btn.innerHTML;
  btn.innerHTML = 'Extraindo...';

  try {
    const res = await fetch('/api/esp/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        local_nome: nome,
        local_descricao: desc,
        latitude: lat ? parseFloat(lat) : null,
        longitude: lng ? parseFloat(lng) : null
      })
    });
    const result = await res.json();

    if (res.ok) {
      alert(`Sucesso! ${result.count} amostras descarregadas com sucesso.`);
      closeExtractModal();
      window.location.reload();
    } else {
      alert('Falha na extração: ' + (result.error || 'Erro retornado pelo ESP32.'));
    }
  } catch (err) {
    alert('Erro de comunicação com o servidor Flask.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalLabel;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  startStatusPolling();

  const modalOverlay = document.getElementById('extractModal');
  if (modalOverlay) {
    modalOverlay.addEventListener('click', (e) => {
      if (e.target === modalOverlay) closeExtractModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeExtractModal();
  });
});