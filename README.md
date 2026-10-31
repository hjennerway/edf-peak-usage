# EDF Usage for Home Assistant

This repository contains a Home Assistant custom integration for EDF Energy peak/off-peak electricity usage and a compact Lovelace card for the last week's usage.

## What it creates

- A config-flow integration named `EDF Usage`.
- Twice-daily polling of EDF's GB Kraken GraphQL API.
- Sensors for weekly peak, off-peak, total usage, percentages, update status, and the estimated 30-day bill.
- A `Refresh usage` button entity and `edf_usage.refresh` service for on-demand updates.
- A custom Lovelace card named `custom:edf-usage-pie-card` with a Mushroom-style proportional background.

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

The integration asks for your EDF account number and EDF account-user API key or a temporary Kraken access token. See [Credentials and API access](#credentials-and-api-access) below. The default API endpoint is `https://api.edfgb-kraken.energy/v1/graphql/`.

The `30-day bill` sensor uses EDF/Kraken cost-of-usage data first, then falls back to posted account energy-charge transactions. It is based on the previous 30 complete days, not necessarily the exact billing statement period. If EDF does not expose costs and no energy charges were posted in that period, the bill may remain unknown.

## Credentials and API access

### Account number

Sign in to [EDF MyAccount](https://www.edfenergy.com/myaccount) and copy your account number from your account or a bill. Enter it exactly as shown, including any prefix. This is not your meter serial number, MPAN, or email address.

### Account-user API key (recommended)

If EDF has provided you with an account-user API key, paste it into **EDF API key or temporary access token**. The integration exchanges it for a short-lived Kraken token and automatically obtains a replacement when EDF rejects an expired token. You do not need to obtain these access tokens yourself.

If you do not have an API key, contact EDF about account-user API access. Availability depends on your account; this integration cannot issue or enable an EDF API key. EDF documents this credential as `APIKey` in [ObtainJSONWebTokenInput](https://developer.edfgb-kraken.energy/graphql/reference/input-objects/#obtainjsonwebtokeninput).

### Temporary browser token (manual fallback)

The integration also accepts an already-issued Kraken JWT. If EDF MyAccount exposes one in your browser's network requests, you can use it temporarily:

1. On a desktop browser, sign in to [EDF MyAccount](https://www.edfenergy.com/myaccount).
2. Open Developer tools (usually **F12** or **Ctrl+Shift+I**) and choose **Network**, then **Fetch/XHR**.
3. With Network recording, reload or open your electricity usage page. Filter for `graphql` and look for requests to `api.edfgb-kraken.energy`.
4. Select a request and inspect **Headers > Request headers > Authorization**. If the value contains a token beginning with `eyJ`, copy it into the integration's credential field. A leading `Bearer ` or `Authorization:` is handled automatically.
5. Enter the EDF account number and submit the form.

MyAccount's implementation can change. If no such request or header is visible, this method is unavailable for that session; contact EDF about API access. Do not paste browser cookies, a refresh token, or your EDF password into this field.

**A browser access token expires.** This integration cannot renew a pasted JWT. When Home Assistant asks you to reconnect, repeat these steps for a fresh token or replace it with an account-user API key. Treat keys and tokens like passwords; do not include them in screenshots, issue reports, or shared network logs.

### Why there is no automatic EDF sign-in yet

[EDF's authentication server](https://auth.edfgb-kraken.energy/) supports OAuth authorization with PKCE and device authorization. EDF requires developers to request an OAuth application, specifying its client type, grant type, redirect URIs, and required API resources. This integration has no EDF OAuth client configured, so it cannot currently offer a working **Sign in with EDF** button.

To enable that flow, the integration maintainer would first need EDF to approve a client and the required account/usage access, then implement authorization and token renewal in Home Assistant. The setup page uses manual credentials until that is available. EDF has also deprecated email/password inputs to `obtainKrakenToken` in favour of its auth server, so collecting an EDF password in this integration is not a supported replacement.

## Card Example

```yaml
type: custom:edf-usage-pie-card
title: EDF weekly usage
```

The card auto-detects the EDF weekly peak/off-peak sensors. You can still provide `peak_entity` and `off_peak_entity` manually if you have multiple EDF accounts.

The card is a single horizontal bar with two proportional sections: green off-peak on the left and red peak on the right. Each section shows its percentage. Hover over the card for the kWh totals and last update time. Use `off_peak_color` and `peak_color` to override the default colours.

## Off-Peak Window

EDF can return explicit usage band labels. When it does, this integration uses those labels. If EDF only returns interval usage, the integration classifies intervals using the configured off-peak window. The default is `23:00` to `06:00` in `Europe/London`, which can be changed in the integration options.
