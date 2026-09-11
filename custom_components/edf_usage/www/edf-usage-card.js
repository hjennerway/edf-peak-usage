const EDF_USAGE_CARD_VERSION = "0.1.14";

class EDFUsagePieCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
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
    return 1;
  }

  render() {
    if (!this.config || !this._hass) return;

    const peak = this._readState(this.config.peak_entity, "weekly_peak_usage", "Weekly peak usage");
    const offPeak = this._readState(this.config.off_peak_entity, "weekly_off_peak_usage", "Weekly off-peak usage");
    const missing = [peak, offPeak].filter((item) => !item.state);

    if (missing.length > 0) {
      this._renderMissing(missing);
      return;
    }

    const total = peak.value + offPeak.value;
    const peakPercent = total > 0 ? (peak.value / total) * 100 : 0;
    const offPeakPercent = total > 0 ? 100 - peakPercent : 0;
    const lastUpdated =
      peak.state?.attributes?.last_updated || offPeak.state?.attributes?.last_updated;
    const updated = lastUpdated ? this._formatDate(lastUpdated) : "Waiting for EDF data";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          overflow: hidden;
          padding: 0;
          border-radius: var(--ha-card-border-radius, 12px);
        }
        .bar {
          display: flex;
          width: 100%;
          height: 58px;
          background: var(--divider-color);
        }
        .segment {
          display: flex;
          box-sizing: border-box;
          min-width: 0;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          color: white;
          font-variant-numeric: tabular-nums;
          text-align: center;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
        }
        .off-peak {
          flex: 0 0 ${offPeakPercent}%;
          background: ${this.config.off_peak_color};
        }
        .peak {
          flex: 0 0 ${peakPercent}%;
          background: ${this.config.peak_color};
        }
        .label {
          max-width: 100%;
          font-size: 11px;
          line-height: 15px;
          opacity: 0.92;
          text-overflow: clip;
          white-space: nowrap;
        }
        .value {
          max-width: 100%;
          overflow: hidden;
          font-size: 17px;
          font-weight: 600;
          line-height: 21px;
          white-space: nowrap;
        }
        .compact .label {
          display: none;
        }
      </style>
      <ha-card title="${this._escape(`${this.config.title}: ${this._formatKwh(offPeak.value)} off-peak, ${this._formatKwh(peak.value)} peak. ${updated}`)}">
        <div
          class="bar"
          role="img"
          aria-label="Off-peak ${offPeakPercent.toFixed(1)} percent, peak ${peakPercent.toFixed(1)} percent"
        >
          <div class="segment off-peak${offPeakPercent < 18 ? " compact" : ""}">
            <span class="label">Off-peak</span>
            <span class="value">${offPeakPercent.toFixed(1)}%</span>
          </div>
          <div class="segment peak${peakPercent < 18 ? " compact" : ""}">
            <span class="label">Peak</span>
            <span class="value">${peakPercent.toFixed(1)}%</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderMissing(missing) {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 18px;
          border-radius: 8px;
        }
        h2 {
          margin: 0 0 10px;
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: 0;
          color: var(--primary-text-color);
        }
        .message {
          color: var(--secondary-text-color);
          line-height: 1.45;
        }
        code {
          color: var(--primary-text-color);
          overflow-wrap: anywhere;
        }
      </style>
      <ha-card>
        <h2>${this._escape(this.config.title)}</h2>
        <div class="message">
          Missing EDF usage entities:<br>
          ${missing.map((item) => `<code>${this._escape(item.label)}</code>`).join("<br>")}
        </div>
      </ha-card>
    `;
  }

  _readState(entityId, key, label) {
    const resolvedEntityId = entityId && this._hass.states[entityId]
      ? entityId
      : this._findEntityId(key, label);
    const state = resolvedEntityId ? this._hass.states[resolvedEntityId] : undefined;
    const value = state ? Number.parseFloat(state.state) : 0;
    return {
      entityId: resolvedEntityId,
      label: entityId || label,
      state,
      value: Number.isFinite(value) ? value : 0,
    };
  }

  _findEntityId(key, label) {
    const normalisedLabel = label.toLowerCase();
    return Object.keys(this._hass.states).find((entityId) => {
      if (!entityId.startsWith("sensor.")) return false;
      const state = this._hass.states[entityId];
      const friendlyName = String(state.attributes?.friendly_name || "").toLowerCase();
      return entityId.endsWith(`_${key}`) || friendlyName.endsWith(normalisedLabel);
    });
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
  name: "EDF Usage Card",
  description: "Mushroom-style EDF weekly usage card with a two-section proportional bar",
  version: EDF_USAGE_CARD_VERSION,
});

console.info(`[EDF Usage Card] Version ${EDF_USAGE_CARD_VERSION}`);
