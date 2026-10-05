/**
 * COMET DIAL v2.1 - GEOMETRICALLY CENTERED ENGINE
 * Resolve definitivamente a descentralização visual:
 * O texto, número e unidade ficam perfeitamente ancorados no centro geométrico (cx, cy)
 * do arco de 270 graus, com alinhamento flexbox absoluto e tipografia balanceada.
 */

class CometDialWidget {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.options = Object.assign({
      min: 0,
      max: 100,
      value: 0,
      unit: '%',
      label: 'Medição',
      accentColor: '#38bdf8',
      trackColor: 'rgba(255, 255, 255, 0.08)',
      size: 220,
      thickness: 10
    }, options);

    // Centro exato no viewBox 200x200
    this.cx = 100;
    this.cy = 100;
    this.radius = 76;
    this.circumference = 2 * Math.PI * this.radius;
    // Arco visível: 270 graus = 75% da circunferência
    this.arcLength = this.circumference * 0.75;

    this.currentValue = Number(this.options.value) || 0;
    this.targetValue = Number(this.options.value) || 0;
    this.rafId = null;

    this.initDOM();
    this.updateArc(this.currentValue);
  }

  initDOM() {
    this.container.classList.add('comet-dial-wrapper');
    this.container.innerHTML = `
      <div class="comet-dial-card" style="width: ${this.options.size}px; height: ${this.options.size}px; position: relative; display: flex; align-items: center; justify-content: center;">
        <svg class="comet-dial-svg" viewBox="0 0 200 200" style="width: 100%; height: 100%; position: absolute; inset: 0;">
          <defs>
            <linearGradient id="dialGrad-${this.container.id}" x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="${this.options.accentColor}" stop-opacity="0.45" />
              <stop offset="100%" stop-color="${this.options.accentColor}" stop-opacity="1" />
            </linearGradient>
            <filter id="dialGlow-${this.container.id}" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <!-- Trilha de Fundo Estável (abertura de 90° na base) -->
          <circle 
            class="dial-bg-track"
            cx="${this.cx}" 
            cy="${this.cy}" 
            r="${this.radius}" 
            fill="none" 
            stroke="${this.options.trackColor}" 
            stroke-width="${this.options.thickness}" 
            stroke-linecap="round"
            stroke-dasharray="${this.arcLength} ${this.circumference}"
            transform="rotate(135 ${this.cx} ${this.cy})"
          />

          <!-- Arco Preenchido Ativo com Brilho Convectivo -->
          <circle 
            id="dialActive-${this.container.id}"
            class="dial-active-arc"
            cx="${this.cx}" 
            cy="${this.cy}" 
            r="${this.radius}" 
            fill="none" 
            stroke="url(#dialGrad-${this.container.id})" 
            stroke-width="${this.options.thickness}" 
            stroke-linecap="round"
            filter="url(#dialGlow-${this.container.id})"
            stroke-dasharray="0 ${this.circumference}"
            transform="rotate(135 ${this.cx} ${this.cy})"
          />

          <!-- Indicador Terminal Luminoso (Knob) -->
          <circle 
            id="dialKnob-${this.container.id}"
            cx="${this.cx}" 
            cy="${this.cy + this.radius}" 
            r="${this.options.thickness * 0.9}" 
            fill="#ffffff"
            stroke="${this.options.accentColor}"
            stroke-width="3"
            filter="url(#dialGlow-${this.container.id})"
          />
        </svg>

        <!-- Readout Rigorosamente Centralizado (Anchor 50%/50%) -->
        <div class="dial-center-content" style="position: absolute; top: 48%; left: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; pointer-events: none; width: 100%;">
          <div class="dial-value-row" style="display: flex; align-items: baseline; justify-content: center; gap: 3px; line-height: 1;">
            <span id="dialVal-${this.container.id}" class="dial-number-val" style="font-size: 2.3rem; font-weight: 800; color: #ffffff; letter-spacing: -0.04em; font-variant-numeric: tabular-nums;">--</span>
            <span class="dial-unit-val" style="font-size: 0.95rem; font-weight: 600; color: ${this.options.accentColor};">${this.options.unit}</span>
          </div>
          <span class="dial-title-label" style="font-size: 0.72rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 6px;">${this.options.label}</span>
        </div>
      </div>
    `;

    this.activeArc = this.container.querySelector(`#dialActive-${this.container.id}`);
    this.knob = this.container.querySelector(`#dialKnob-${this.container.id}`);
    this.valText = this.container.querySelector(`#dialVal-${this.container.id}`);
  }

  setValue(val) {
    const parsed = Number(val);
    const clamped = Math.max(this.options.min, Math.min(this.options.max, isNaN(parsed) ? 0 : parsed));
    this.targetValue = clamped;

    if (!this.rafId) {
      this.animate();
    }
  }

  animate() {
    const diff = this.targetValue - this.currentValue;
    const step = diff * 0.12;

    this.currentValue += step;

    if (Math.abs(diff) < 0.05) {
      this.currentValue = this.targetValue;
      this.updateArc(this.currentValue);
      this.rafId = null;
    } else {
      this.updateArc(this.currentValue);
      this.rafId = requestAnimationFrame(() => this.animate());
    }
  }

  updateArc(val) {
    const range = Math.max(1e-5, this.options.max - this.options.min);
    const fraction = Math.max(0, Math.min(1, (val - this.options.min) / range));
    const activeLength = fraction * this.arcLength;

    if (this.activeArc) {
      this.activeArc.setAttribute('stroke-dasharray', `${activeLength} ${this.circumference}`);
    }

    // Posição angular: parte em 135° e percorre 270°
    const angleDeg = 135 + (fraction * 270);
    const angleRad = (angleDeg * Math.PI) / 180;
    const kx = this.cx + this.radius * Math.cos(angleRad);
    const ky = this.cy + this.radius * Math.sin(angleRad);

    if (this.knob) {
      this.knob.setAttribute('cx', kx.toFixed(2));
      this.knob.setAttribute('cy', ky.toFixed(2));
    }

    if (this.valText) {
      this.valText.innerText = val.toFixed(1);
    }
  }
}