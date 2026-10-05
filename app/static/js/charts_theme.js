/**
 * WEATHER CHARTS THEME v2.2 - HIGH CONTRAST & CLEAN MARGIN ENGINE
 * Corrige em definitivo o erro visual das capturas:
 * 1. Margem superior ampliada (t: 70px) para isolar o título da área dos eixos.
 * 2. Legendas deslocadas para fora do gráfico (y: 1.20) para nunca sobrepor barras ou boxplots.
 * 3. Grelhas suaves com opacidade calibrada, eliminando poluição visual.
 */

const WeatherChartsTheme = {
  colors: {
    sky: '#38bdf8',
    teal: '#34d399',
    amber: '#fb923c',
    rose: '#f43f5e',
    rain: '#60a5fa',
    drought: '#eab308',
    textMain: '#f8fafc',
    textMuted: '#94a3b8',
    gridSubtle: 'rgba(255, 255, 255, 0.05)',
    cardBg: 'transparent'
  },

  getLayout(titleText) {
    return {
      title: {
        text: titleText,
        font: {
          family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          size: 13.5,
          color: this.colors.textMain
        },
        x: 0.01,
        y: 0.98,
        xanchor: 'left',
        yanchor: 'top'
      },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      // Margem superior expandida para dar respiro aos títulos e legendas
      margin: { t: 72, r: 25, l: 48, b: 42 },
      legend: {
        orientation: 'h',
        x: 0.01,
        y: 1.18,
        xanchor: 'left',
        yanchor: 'bottom',
        font: {
          family: '-apple-system, BlinkMacSystemFont, sans-serif',
          size: 10.5,
          color: this.colors.textMuted
        }
      },
      xaxis: {
        gridcolor: this.colors.gridSubtle,
        tickfont: { 
          family: '-apple-system, BlinkMacSystemFont, sans-serif',
          color: this.colors.textMuted, 
          size: 10 
        },
        linecolor: this.colors.gridSubtle,
        zerolinecolor: this.colors.gridSubtle
      },
      yaxis: {
        gridcolor: this.colors.gridSubtle,
        tickfont: { 
          family: '-apple-system, BlinkMacSystemFont, sans-serif',
          color: this.colors.textMuted, 
          size: 10 
        },
        linecolor: this.colors.gridSubtle,
        zerolinecolor: this.colors.gridSubtle
      }
    };
  }
};