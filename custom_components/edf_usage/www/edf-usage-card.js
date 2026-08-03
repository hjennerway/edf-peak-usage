class EDFUsagePieCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.peak_entity || !config.off_peak_entity) {
      throw new Error("Define peak_entity and off_peak_entity");
    }
    this.config = {
      title: "EDF weekly usage",
      peak_color: "#e04f3f",
      off_peak_color: "#22a699",
      ...config,
    };
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 3;
  }

  render() {
    if (!this.config || !this._hass) return;

    const peak = this._readState(this.config.peak_entity);
    const offPeak = this._readState(this.config.off_peak_entity);
    const total = peak.value + offPeak.value;
    const peakPercent = total > 0 ? (peak.value / total) * 100 : 0;
    const offPeakPercent = total > 0 ? 100 - peakPercent : 0;
    const periodEnd =
      peak.state?.attributes?.period_end || offPeak.state?.attributes?.period_end;
    const updated = periodEnd ? this._formatDate(periodEnd) : "Waiting for EDF data";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          padding: 18px;
          border-radius: 8px;
        }
        .header {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: start;
          margin-bottom: 18px;
        }
        h2 {
          margin: 0;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: 0;
          color: var(--primary-text-color);
        }
        .updated {
          color: var(--secondary-text-color);
          font-size: 0.78rem;
          text-align: right;
          line-height: 1.3;
        }
        .content {
          display: grid;
          grid-template-columns: 132px 1fr;
          gap: 18px;
          align-items: center;
        }
        .pie {
          width: 132px;
          aspect-ratio: 1;
          border-radius: 50%;
          background:
            radial-gradient(circle at center, var(--card-background-color) 0 47%, transparent 48%),
            conic-gradient(
              ${this.config.peak_color} 0 ${peakPercent}%,
              ${this.config.off_peak_color} ${peakPercent}% 100%
            );
          box-shadow: inset 0 0 0 1px var(--divider-color);
        }
        .legend {
          display: grid;
          gap: 12px;
          min-width: 0;
        }
        .row {
          display: grid;
          grid-template-columns: 12px minmax(0, 1fr) auto;
          gap: 9px;
          align-items: center;
        }
        .swatch {
          width: 12px;
          height: 12px;
          border-radius: 50%;
        }
        .label {
          color: var(--primary-text-color);
          min-width: 0;
          overflow-wrap: anywhere;
        }
        .value {
          color: var(--primary-text-color);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        .total {
          margin-top: 4px;
          padding-top: 12px;
          border-top: 1px solid var(--divider-color);
          display: flex;
          justify-content: space-between;
          gap: 12px;
          color: var(--secondary-text-color);
          font-size: 0.9rem;
        }
        @media (max-width: 420px) {
          .content {
            grid-template-columns: 112px 1fr;
            gap: 14px;
          }
          .pie {
            width: 112px;
          }
          ha-card {
            padding: 14px;
          }
        }
      </style>
      <ha-card>
        <div class="header">
          <h2>${this._escape(this.config.title)}</h2>
          <div class="updated">${this._escape(updated)}</div>
        </div>
        <div class="content">
          <div class="pie" title="Peak ${peakPercent.toFixed(1)}%, off-peak ${offPeakPercent.toFixed(1)}%"></div>
          <div class="legend">
            ${this._legendRow("Peak", peak.value, peakPercent, this.config.peak_color)}
            ${this._legendRow("Off-peak", offPeak.value, offPeakPercent, this.config.off_peak_color)}
            <div class="total">
              <span>Total</span>
              <strong>${this._formatKwh(total)}</strong>
            </div>
          </div>
        </div>
      </ha-card>
    `;
  }

  _legendRow(label, value, percent, color) {
    return `
      <div class="row">
        <span class="swatch" style="background:${this._escape(color)}"></span>
        <span class="label">${this._escape(label)}</span>
        <span class="value">${this._formatKwh(value)} - ${percent.toFixed(1)}%</span>
      </div>
    `;
  }

  _readState(entityId) {
    const state = this._hass.states[entityId];
    const value = state ? Number.parseFloat(state.state) : 0;
    return {
      state,
      value: Number.isFinite(value) ? value : 0,
    };
  }

  _formatKwh(value) {
    return `${value.toFixed(2)} kWh`;
  }

  _formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.valueOf())) return value;
    return `Updated ${date.toLocaleString()}`;
  }

  _escape(value) {
    return String(value).replace(/[&<>"']/g, (char) => {
      const replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      };
      return replacements[char];
    });
  }
}

customElements.define("edf-usage-pie-card", EDFUsagePieCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "edf-usage-pie-card",
  name: "EDF Usage Pie Card",
  description: "Pie chart for EDF peak and off-peak weekly usage",
});
