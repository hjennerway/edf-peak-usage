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
          position: relative;
          overflow: hidden;
          padding: 12px;
          border-radius: var(--ha-card-border-radius, 12px);
          background: linear-gradient(
            90deg,
            ${this.config.off_peak_color} 0%,
            ${this.config.off_peak_color} ${offPeakPercent}%,
            ${this.config.peak_color} ${offPeakPercent}%,
            ${this.config.peak_color} 100%
          );
          color: white;
        }
        .content {
          display: flex;
          align-items: center;
          gap: 12px;
          min-height: 52px;
        }
        .icon {
          display: grid;
          flex: 0 0 40px;
          width: 40px;
          height: 40px;
          place-items: center;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.22);
        }
        ha-icon {
          --mdc-icon-size: 24px;
          color: white;
        }
        .info {
          flex: 1 1 auto;
          min-width: 0;
        }
        .primary {
          overflow: hidden;
          font-size: 14px;
          font-weight: 500;
          line-height: 20px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .secondary {
          overflow: hidden;
          font-size: 12px;
          line-height: 18px;
          opacity: 0.9;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .percentage {
          flex: 0 0 auto;
          text-align: right;
          font-variant-numeric: tabular-nums;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
        }
        .percentage strong {
          display: block;
          font-size: 22px;
          line-height: 24px;
        }
        .percentage span {
          display: block;
          font-size: 11px;
          line-height: 16px;
          opacity: 0.9;
        }
        @media (max-width: 360px) {
          .secondary {
            display: none;
          }
        }
      </style>
      <ha-card title="Off-peak ${offPeakPercent.toFixed(1)}%, peak ${peakPercent.toFixed(1)}%">
        <div class="content">
          <div class="icon"><ha-icon icon="mdi:lightning-bolt"></ha-icon></div>
          <div class="info">
            <div class="primary">${this._escape(this.config.title)}</div>
            <div class="secondary">
              ${this._formatKwh(offPeak.value)} off-peak · ${this._formatKwh(peak.value)} peak · ${this._formatKwh(total)} total<br>
              ${this._escape(updated)}
            </div>
          </div>
          <div class="percentage">
            <strong>${offPeakPercent.toFixed(1)}%</strong>
            <span>off-peak</span>
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
  description: "Mushroom-style EDF weekly usage card with an off-peak/peak background",
});
