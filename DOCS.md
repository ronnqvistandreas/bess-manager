# BESS Battery Manager

Battery Energy Storage System optimization and management for Home Assistant.

## About

BESS Battery Manager is a comprehensive solution for optimizing battery energy storage systems. It uses dynamic programming algorithms to minimize electricity costs by intelligently scheduling battery charge/discharge cycles based on:

- Electricity spot prices (Nordpool or Octopus Energy)
- Solar production forecasts
- Home consumption patterns
- Battery capacity and efficiency

## Features

- **Intelligent Optimization**: Dynamic programming algorithm for cost-optimal battery scheduling
- **Price-Based Control**: Automatic charge/discharge based on electricity price spreads
- **Solar Integration**: Optimizes for solar self-consumption and grid export
- **Real-Time Monitoring**: Live dashboard with energy flow visualization
- **Decision Intelligence**: Detailed hourly strategy analysis and economic reasoning
- **Savings Analysis**: Historical financial reports and performance tracking
- **Auto-Configuration**: Setup wizard scans Home Assistant and detects Growatt, SolaX, Nordpool, Solcast and other integrations automatically — no manual entity ID lookup required
- **System Health**: Comprehensive diagnostics and sensor validation in the Settings page

## Installation

For detailed installation instructions, see the [Installation Guide](https://github.com/johanzander/bess-manager/blob/main/docs/INSTALLATION.md).

### Quick Start

1. Add this repository to Home Assistant:
   - Settings → Add-ons → Add-on Store → ⋮ → Repositories
   - Add: `https://github.com/johanzander/bess-manager`

2. Install BESS Manager from the add-on store

3. Configure your battery settings, sensors, and pricing parameters

4. Start the add-on and access the web interface

## Configuration

All settings are configured through the web interface — no manual YAML editing required for
battery, pricing, home, or sensor settings.

The only setting that belongs in the add-on configuration (Options tab) is `influxdb`:

```yaml
influxdb:
  url: "http://homeassistant.local:8086/api/v2/query"
  bucket: "homeassistant/autogen"
  username: "bess"
  password: "your_password_here"
```

### First-Time Setup

On first launch, a **Setup Wizard** guides you through auto-discovering your inverter (Growatt or
SolaX), Nordpool, Solcast and other integrations. It fills in sensor entity IDs automatically. The
wizard can be re-run at any time from **Settings → Sensors → Auto-Configure**.

### Settings Page

All other configuration is done in the **Settings** page:

- **Home** — Currency, consumption baseline, fuse, voltage, phase count, safety margin
- **Pricing** — Energy provider (Nordpool/Octopus), price area, VAT, markup, additional costs
- **Battery** — Capacity, power limits, SOC range, cycle cost, min action profit threshold
- **Sensors** — All sensor entity IDs grouped by integration, with live health status per sensor
- **AI Analyst** — Optional Claude, Google Gemini, or GitHub Copilot provider configuration
- **Health** — Full component health check with refresh and debug export

### GitHub Copilot AI Analyst

Select **GitHub Copilot** under **Settings → AI Analyst** to use an existing GitHub Copilot subscription through the official Copilot SDK. Create a fine-grained personal access token in [GitHub settings](https://github.com/settings/personal-access-tokens) and grant it the **Copilot Requests** permission. Paste the token into the AI Analyst settings and use **Test Connection** to verify access and load the models available to your account. Classic `ghp_` tokens are not supported.

The runtime is downloaded and SHA256-verified the first time you test the connection or start a Copilot chat. The download is approximately 136 MB and is stored in `/data` so it can be reused after add-on updates. Choose a model with a `0× premium requests` multiplier to avoid premium-request usage where one is available; otherwise the model selector defaults to **Auto**. Copilot usage and model availability are governed by your GitHub Copilot plan.

### Required Sensors

The add-on requires sensors for:

- Battery: SOC, charge/discharge power, control switches
- Solar: Production, consumption, grid import/export
- Pricing: Electricity spot prices via Nordpool or Octopus Energy (today and tomorrow)
- Consumption: 48-hour average forecast

See the [Installation Guide](https://github.com/johanzander/bess-manager/blob/main/docs/INSTALLATION.md) for full setup instructions.

## Usage

### Web Interface

Access the BESS Manager dashboard via Settings → Add-ons → BESS Manager → Open Web UI.

### Dashboard Pages

1. **Dashboard**: Live monitoring and daily overview
2. **Savings**: Financial analysis and historical reports
3. **Inverter**: Battery schedule management and status
4. **Insights**: Decision intelligence and strategy analysis
5. **Settings**: All configuration — battery, pricing, sensors, and component health

## How It Works

1. **Data Collection**: Gathers real-time data from Home Assistant sensors
2. **Price Optimization**: Analyzes electricity prices from Nordpool or Octopus Energy (today + tomorrow)
3. **Solar Forecast**: Integrates solar production predictions
4. **Battery Optimization**: Dynamic programming algorithm generates optimal 24-hour schedule
5. **Schedule Deployment**: Sends optimization results to the inverter (Growatt TOU intervals or SolaX VPP commands)
6. **Continuous Monitoring**: Hourly updates adapt to changing conditions

## Troubleshooting

### Check System Health

Go to **Settings → Health** in the web interface to verify all sensors and integrations are
working correctly.

### View Logs

Check add-on logs for detailed information:

Settings → Add-ons → BESS Manager → Log

## Support

- **Documentation**: [Full documentation](https://github.com/johanzander/bess-manager)
- **Issues**: [Report bugs](https://github.com/johanzander/bess-manager/issues)
- **User Guide**: [Detailed user guide](https://github.com/johanzander/bess-manager/blob/main/docs/USER_GUIDE.md)

## License

MIT License - see [LICENSE](https://github.com/johanzander/bess-manager/blob/main/LICENSE)
