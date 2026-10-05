/**
 * WEATHER FX - CONTINOUS ATMOSPHERIC CLOUD & SKY ENGINE
 * Renderiza em Canvas puro uma transição orgânica e contínua de:
 * 1. Nuvens volumétricas em deslocamento horizontal constante (deriva eólica).
 * 2. Feixes de luz / radiação solar difusa com efeito Tyndall suave.
 * 3. Partículas microscópicas de orvalho e névoa suspensas.
 * Sem botões manuais, sem vazamento de memória e mantendo o contraste do texto 100% nítido.
 */

class WeatherFXEngine {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;

    this.ctx = this.canvas.getContext('2d', { alpha: true });
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.rafId = null;
    this.time = 0;

    // Camadas de Nuvens Volumétricas
    this.clouds = [];
    this.numClouds = 14;

    // Partículas de névoa / aerossóis térmicos
    this.mists = [];
    this.numMists = 35;

    this.init();
  }

  init() {
    this.resize();
    this.spawnEntities();
    window.addEventListener('resize', () => this.resize(), { passive: true });
    this.start();
  }

  resize() {
    this.width = window.innerWidth;
    this.height = window.innerHeight;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
  }

  spawnEntities() {
    this.clouds = [];
    for (let i = 0; i < this.numClouds; i++) {
      this.clouds.push({
        x: Math.random() * (this.width + 400) - 200,
        y: Math.random() * (this.height * 0.7),
        radiusX: 180 + Math.random() * 260,
        radiusY: 80 + Math.random() * 130,
        speedX: 0.25 + Math.random() * 0.45,
        opacity: 0.03 + Math.random() * 0.055,
        colorTone: Math.random() > 0.4 ? '56, 189, 248' : '30, 64, 110' // Azul celeste suave ou azul profundo
      });
    }

    this.mists = [];
    for (let j = 0; j < this.numMists; j++) {
      this.mists.push({
        x: Math.random() * this.width,
        y: Math.random() * this.height,
        r: 1.5 + Math.random() * 3,
        speedX: (Math.random() - 0.2) * 0.35,
        speedY: (Math.random() - 0.5) * 0.2,
        alpha: 0.08 + Math.random() * 0.18
      });
    }
  }

  render() {
    this.time += 0.01;
    this.ctx.clearRect(0, 0, this.width, this.height);

    // 1. FEIXE DE LUZ SOLAR DIFUSA / AURORA PSICROMÉTRICA NO TOPO
    const sunX = this.width * 0.75 + Math.sin(this.time * 0.5) * 60;
    const sunY = 50 + Math.cos(this.time * 0.3) * 20;
    const sunGrad = this.ctx.createRadialGradient(sunX, sunY, 10, sunX, sunY, this.width * 0.55);
    sunGrad.addColorStop(0, 'rgba(56, 189, 248, 0.08)');
    sunGrad.addColorStop(0.35, 'rgba(2, 132, 199, 0.035)');
    sunGrad.addColorStop(1, 'transparent');

    this.ctx.fillStyle = sunGrad;
    this.ctx.fillRect(0, 0, this.width, this.height);

    // 2. PASSAGEM CONTÍNUA DE NUVENS VOLUMÉTRICAS
    for (let c of this.clouds) {
      c.x += c.speedX;

      // Reseta a nuvem quando sai completamente pela direita
      if (c.x - c.radiusX > this.width) {
        c.x = -c.radiusX - 100;
        c.y = Math.random() * (this.height * 0.7);
      }

      this.ctx.save();
      this.ctx.beginPath();
      // Elipse orgânica representando a formação da nuvem
      this.ctx.ellipse(c.x, c.y, c.radiusX, c.radiusY, 0, 0, Math.PI * 2);
      
      const cloudGrad = this.ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.radiusX);
      cloudGrad.addColorStop(0, `rgba(${c.colorTone}, ${c.opacity})`);
      cloudGrad.addColorStop(0.65, `rgba(${c.colorTone}, ${c.opacity * 0.45})`);
      cloudGrad.addColorStop(1, 'transparent');

      this.ctx.fillStyle = cloudGrad;
      this.ctx.fill();
      this.ctx.restore();
    }

    // 3. MICRO-PARTÍCULAS DE CONDENSAÇÃO E NÉVOA
    this.ctx.fillStyle = '#38bdf8';
    for (let m of this.mists) {
      m.x += m.speedX;
      m.y += m.speedY;

      if (m.x > this.width) m.x = 0;
      if (m.x < 0) m.x = this.width;
      if (m.y > this.height) m.y = 0;
      if (m.y < 0) m.y = this.height;

      this.ctx.globalAlpha = m.alpha;
      this.ctx.beginPath();
      this.ctx.arc(m.x, m.y, m.r, 0, Math.PI * 2);
      this.ctx.fill();
    }
    this.ctx.globalAlpha = 1.0;

    this.rafId = requestAnimationFrame(() => this.render());
  }

  start() {
    if (!this.rafId) {
      this.rafId = requestAnimationFrame(() => this.render());
    }
  }

  stop() {
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new WeatherFXEngine('weatherCanvasBackdrop');
});