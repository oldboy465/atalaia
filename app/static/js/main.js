// --- MONITORAMENTO GLOBAL DO ESP32 NA TOPBAR ---
async function checkESPStatus() {
  const dot = document.getElementById('espDot');
  const txt = document.getElementById('espStatusText');
  try {
    const res = await fetch('/api/esp/status');
    const data = await res.json();
    if (data.online) {
      dot.className = 'status-dot online';
      const modeStr = data.wifi_mode ? ` (${data.wifi_mode})` : '';
      txt.innerText = `ESP32: Online${modeStr} [${data.buffer_count || 0}/7200 regs]`;
    } else {
      dot.className = 'status-dot offline';
      txt.innerText = 'ESP32: Inacessível (Verifique Wi-Fi/AP)';
    }
  } catch (err) {
    dot.className = 'status-dot offline';
    txt.innerText = 'ESP32: Falha na Conexão';
  }
}

// Ping periódico a cada 5 segundos
setInterval(checkESPStatus, 5000);
checkESPStatus();

// --- CONTROLE DO MODAL DE EXTRAÇÃO COM GEOLOCALIZAÇÃO ---
function openExtractModal() {
  document.getElementById('extractModal').classList.remove('hidden');
}

function closeExtractModal() {
  document.getElementById('extractModal').classList.add('hidden');
}

function handleModalLocalChange() {
  const select = document.getElementById('modalLocalSelect');
  const nomeInput = document.getElementById('modalLocalNome');
  const latInput = document.getElementById('modalLocalLat');
  const lngInput = document.getElementById('modalLocalLng');

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

async function executeExtraction() {
  const nome = document.getElementById('modalLocalNome').value.trim();
  const desc = document.getElementById('modalLocalDesc').value.trim();
  const lat = document.getElementById('modalLocalLat').value.trim();
  const lng = document.getElementById('modalLocalLng').value.trim();
  const btn = document.getElementById('btnConfirmExtract');

  if (!nome) {
    alert('Informe o nome do local da coleta.');
    return;
  }

  btn.disabled = true;
  btn.innerText = 'Extraindo...';

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
      alert(`Sucesso! ${result.count} registros inseridos com sucesso.`);
      closeExtractModal();
      window.location.reload();
    } else {
      alert('Erro na extração: ' + (result.error || 'Erro desconhecido'));
    }
  } catch (err) {
    alert('Erro de comunicação com o servidor Flask.');
  } finally {
    btn.disabled = false;
    btn.innerText = 'Confirmar e Extrair';
  }
}

async function triggerShutdown() {
  if (!confirm('Deseja realmente colocar o ESP32 em Deep-Sleep para economia de bateria?')) return;
  try {
    const res = await fetch('/api/esp/shutdown', { method: 'POST' });
    const data = await res.json();
    alert(data.message || data.error);
    checkESPStatus();
  } catch (err) {
    alert('Falha ao comunicar com o servidor.');
  }
}