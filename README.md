# EDF Usage for Home Assistant

This repository contains a Home Assistant custom integration for EDF Energy peak/off-peak electricity usage and a Lovelace custom card that renders the last week as a pie chart.

## What it creates

- A config-flow integration named `EDF Usage`.
- Twice-daily polling of EDF's GB Kraken GraphQL API.
- Sensors for weekly peak, off-peak, total usage, percentages, update status, and the estimated 30-day bill.
- A `Refresh usage` button entity and `edf_usage.refresh` service for on-demand updates.
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

HACS needs a GitHub release with a valid version tag, for example `v0.1.10`. If the repository has no releases, HACS may fall back to a commit hash such as `561f66b`, which cannot be used as an integration version.

### Manual

1. Copy `custom_components/edf_usage` into Home Assistant's `/config/custom_components/edf_usage`.
2. Restart Home Assistant.
3. Add the dashboard resource:

```yaml
url: /edf_usage/edf-usage-card.js
type: module
```

4. Add the integration from Settings > Devices & services > Add Integration > EDF Usage.

The integration asks for your EDF customer/account ID and EDF account-user API key. It exchanges that key for a short-lived Kraken token before polling usage. The default API endpoint is `https://api.edfgb-kraken.energy/v1/graphql/`.

The `30-day bill` sensor uses EDF/Kraken cost-of-usage data first, then falls back to posted account energy-charge transactions. It is based on the previous 30 complete days, not necessarily the exact billing statement period. If EDF does not expose costs and no energy charges were posted in that period, the bill may remain unknown.

## Card Example

```yaml
type: custom:edf-usage-pie-card
title: EDF weekly usage
```

The card auto-detects the EDF weekly peak/off-peak sensors. You can still provide `peak_entity` and `off_peak_entity` manually if you have multiple EDF accounts.

## Off-Peak Window

EDF can return explicit usage band labels. When it does, this integration uses those labels. If EDF only returns interval usage, the integration classifies intervals using the configured off-peak window. The default is `23:00` to `06:00` in `Europe/London`, which can be changed in the integration options.
