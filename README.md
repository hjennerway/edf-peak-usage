# EDF Usage for Home Assistant

This repository contains a Home Assistant custom integration for EDF Energy peak/off-peak electricity usage and a Lovelace custom card that renders the last week as a pie chart.

## What it creates

- A config-flow integration named `EDF Usage`.
- Twice-daily polling of EDF's GB Kraken GraphQL API.
- Sensors for weekly peak, off-peak, total usage, and percentages.
- A custom Lovelace card named `custom:edf-usage-pie-card`.

## Install

### HACS

1. Add this repository to HACS as a custom repository with category `Integration`.
2. Install `EDF Usage`.
3. Restart Home Assistant.
4. Add the integration from Settings > Devices & services > Add Integration > EDF Usage.
5. Add the dashboard resource:

```yaml
url: /edf_usage/edf-usage-card.js
type: module
```

HACS needs a GitHub release with a valid version tag, for example `v0.1.4`. If the repository has no releases, HACS may fall back to a commit hash such as `561f66b`, which cannot be used as an integration version.

### Manual

1. Copy `custom_components/edf_usage` into Home Assistant's `/config/custom_components/edf_usage`.
2. Restart Home Assistant.
3. Add the dashboard resource:

```yaml
url: /edf_usage/edf-usage-card.js
type: module
```

4. Add the integration from Settings > Devices & services > Add Integration > EDF Usage.

The integration asks for your EDF customer/account ID and EDF API token. The default API endpoint is `https://api.edfgb-kraken.energy/v1/graphql/`.

## Card Example

```yaml
type: custom:edf-usage-pie-card
title: EDF weekly usage
peak_entity: sensor.edf_usage_weekly_peak_usage
off_peak_entity: sensor.edf_usage_weekly_off_peak_usage
```

Entity IDs may differ depending on the account name Home Assistant assigns.

## Off-Peak Window

EDF can return explicit usage band labels. When it does, this integration uses those labels. If EDF only returns interval usage, the integration classifies intervals using the configured off-peak window. The default is `23:00` to `06:00` in `Europe/London`, which can be changed in the integration options.
