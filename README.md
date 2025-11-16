# Renfe MCP Server 🚄

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for querying **Renfe** (Spanish national railway) train schedules using official GTFS data. Integrates seamlessly with Claude Desktop and other MCP-compatible clients.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-v0.7+-green.svg)](https://github.com/jlowin/fastmcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🔍 **Search trains** between any two Spanish cities on a specific date with pagination
- 💰 **Check prices** - real-time price scraping from Renfe website with pagination support
- 🚉 **Find stations** in any city (Madrid has 7 stations!)
- 📅 **Flexible date parsing** - accepts ISO, European, and written date formats
- 🔄 **Auto-updates** - automatically downloads latest GTFS schedules from Renfe
- ⚡ **Fast & accurate** - uses official Renfe GTFS data with complete timetables
- 🎯 **Smart filtering** - handles service calendars, holidays, and exceptions
- 🛠️ **Claude Desktop ready** - works out of the box with MCP clients

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/renfe_mcp.git
   cd renfe_mcp
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Download GTFS data** (automatic on first run)
   ```bash
   uv run python update_data.py
   ```

4. **Test the server**
   ```bash
   uv run python main.py
   ```

## 📖 Usage

### Standalone Testing

Test the search functionality directly:

```python
from main import load_gtfs_data, search_trains_with_context

load_gtfs_data()
result = search_trains_with_context("Madrid", "Barcelona", "2025-11-20")
print(result)
```

Or use the included Jupyter notebook (`test.ipynb`) for interactive testing.

### Claude Desktop Integration

Add to your Claude Desktop config file:

**Windows** (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "renfe": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\YourName\\path\\to\\renfe_mcp",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

**macOS** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "renfe": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/renfe_mcp",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

**Linux** (`~/.config/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "renfe": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/renfe_mcp",
        "run",
        "python",
        "main.py"
      ]
    }
  }
}
```

Restart Claude Desktop, and you can ask:
- *"Show me trains from Madrid to Barcelona tomorrow"*
- *"What's the earliest train from Barcelona to Valencia on December 1st?"*
- *"What train stations are in Madrid?"*
- *"How many trains run between Madrid and Sevilla in the afternoon?"*
- *"Check prices for trains from Madrid to Barcelona on December 1st"*
- *"What are the ticket prices for the first 5 trains?"*

## 🛠️ MCP Tools

### 1. `search_trains`

Find trains between two cities on a specific date with pagination support.

**Parameters:**
- `origin` (string): Origin city name (e.g., "Madrid", "Barcelona")
- `destination` (string): Destination city name (e.g., "Valencia", "Sevilla")
- `date` (string, optional): Travel date in flexible formats:
  - ISO: `"2025-11-28"`
  - European: `"28/11/2025"`
  - Written: `"November 28, 2025"`
  - Default: today's date
- `page` (integer, optional): Page number to display (default: 1)
- `per_page` (integer, optional): Results per page (default: 10, max: 50)

**Example Output:**
```
Found 36 train(s) total
Showing page 1 of 4 (10 trains)

  1. AVE
     Madrid Pta.Atocha - Almudena Grandes → Barcelona-Sants
     Departs: 6:16:00 | Arrives: 9:05:00
     Duration: 2h 49min

  2. AVE
     Madrid Pta.Atocha - Almudena Grandes → Barcelona-Sants
     Departs: 6:27:00 | Arrives: 9:25:00
     Duration: 2h 58min
  ...

─────────────────────────────────
To see more trains, use page=2
Total pages: 4
```

### 2. `find_station`

Search for train stations in a city.

**Parameters:**
- `city_name` (string): City name to search (e.g., "Madrid")

**Example Output:**
```
Found 7 stations:

All stations found:
  1. Madrid-Chamartín-Clara Campoamor (ID: 17000)
  2. Madrid - Atocha Cercanías (ID: 18000)
  3. Madrid Pta.Atocha - Almudena Grandes (ID: 60000)
  ...
```

### 3. `get_train_prices`

Check actual ticket prices by scraping the Renfe website with pagination support.

**Parameters:**
- `origin` (string): Origin city name (e.g., "Madrid", "Barcelona")
- `destination` (string): Destination city name (e.g., "Valencia", "Sevilla")
- `date` (string, optional): Travel date (same formats as `search_trains`)
- `page` (integer, optional): Page number to display (default: 1)
- `per_page` (integer, optional): Results per page (default: 5, max: 20)

**Example Output:**
```
PRICE CHECK RESULTS
From: Madrid -> Barcelona
Date: 2025-11-17
Showing 5 train(s)

  1. AVE
     Departs: 06:16 | Arrives: 09:05
     Duration: 2h 49min
     Price: 94.90 EUR | [Available]

  2. AVE
     Departs: 06:27 | Arrives: 09:25
     Duration: 2h 58min
     Price: 118.60 EUR | [Available]
  ...

To see more prices, try page=2
```

**Note:** This tool scrapes the Renfe website and may take a few seconds to complete. Pagination now matches `search_trains` so you can get prices for trains on any page (e.g., page 2 shows prices for trains 6-10).

## 📊 Data Updates

The server includes automatic GTFS data updates from Renfe's open data portal.

### Automatic Updates

On server startup, it checks for new data and downloads if needed:

```bash
uv run python main.py
# [CHECK] Checking data versions:
#         Server: 2025-11-15T00:40:21
#         Local:  2025-11-10T00:30:15
# [UPDATE] Server has newer data
# [DOWNLOAD] Downloading GTFS data...
# [OK] GTFS data updated successfully!
```

### Manual Updates

**Check and update if needed:**
```bash
uv run python update_data.py
```

**Force update (download regardless of version):**
```bash
uv run python update_data.py --force
```

The update system:
- ✅ Compares server version with local version
- ✅ Only downloads when new data is available
- ✅ Stores version info in `renfe_schedule/.last_updated`
- ✅ Automatically extracts GTFS CSV files

## 🏗️ Architecture

```
renfe_mcp/
├── main.py              # FastMCP server implementation
├── price_checker.py     # Price checking module
├── update_data.py       # GTFS data updater
├── pyproject.toml       # Dependencies & project config
├── test.ipynb          # Jupyter notebook for testing
├── README.md           # This file
├── renfe_scraper/      # Custom price scraper package
│   ├── __init__.py      # Package exports
│   ├── scraper.py       # RenfeScraper with DWR protocol
│   ├── dwr.py           # DWR utilities & payload builders
│   ├── models.py        # Pydantic models (Station, TrainRide)
│   ├── exceptions.py    # Custom exceptions
│   └── stations.json    # Station code database
├── tests/              # Test suite
│   ├── test_custom_scraper.py
│   ├── test_final_integration.py
│   ├── test_pagination.py
│   ├── test_price_checker.py
│   ├── test_price_pagination.py
│   └── test_updated_price_checker.py
└── renfe_schedule/     # GTFS data (auto-downloaded)
    ├── stops.txt        # Station information
    ├── routes.txt       # Train routes (AVE, ALVIA, etc.)
    ├── trips.txt        # Trip schedules
    ├── stop_times.txt   # Arrival/departure times
    ├── calendar.txt     # Service schedules
    ├── calendar_dates.txt # Holiday exceptions
    └── .last_updated    # Version tracking
```

### How It Works

1. **City to Station Mapping**: Fuzzy matches city names to station IDs
2. **Date Filtering**:
   - Checks `calendar.txt` for service schedules (day of week)
   - Applies exceptions from `calendar_dates.txt` (holidays, special dates)
3. **Route Finding**:
   - Joins trips, stop_times, and stops tables
   - Validates stop sequences and pickup/dropoff permissions
   - Ensures origin comes before destination
4. **Results**: Returns all trains sorted chronologically with proper numeric time sorting

### Key Implementation Details

- ✅ Handles multiple stations per city (e.g., Madrid has 7)
- ✅ Respects service exceptions (holidays, maintenance)
- ✅ Validates passenger boarding/alighting permissions (`pickup_type`, `drop_off_type`)
- ✅ **Fixed sorting bug**: Proper numeric time sorting (not lexicographic!)
- ✅ CSV column whitespace handling (strips on load)
- ✅ Complete result sets (no truncation)

## 🗺️ Supported Routes

The server supports **any route** in the Renfe network:

- **High-Speed (AVE)**: Madrid-Barcelona, Madrid-Sevilla, Madrid-Valencia
- **Long-Distance (ALVIA, Intercity)**: Major city connections
- **International (AVE INT)**: Cross-border services
- **Regional**: Local routes across Spain
- **Commuter (Cercanías)**: Urban networks

**Popular Cities:**
- Madrid (7 stations), Barcelona, Valencia
- Sevilla, Málaga, Bilbao, Zaragoza
- Alicante, Córdoba, Granada, Murcia
- **100+ cities** across Spain!

Use `find_station` to discover available stations in any city.

## 🔧 Development

### Project Setup

```bash
# Clone and install
git clone https://github.com/yourusername/renfe_mcp.git
cd renfe_mcp
uv sync

# Run the server
uv run python main.py

# Update GTFS data
uv run python update_data.py
```

### Dependencies

- **fastmcp** (>=0.7.0) - MCP server framework
- **pandas** (>=2.3.3) - GTFS data processing
- **python-dateutil** (>=2.8.2) - Flexible date parsing
- **httpx** (>=0.27.0) - Modern HTTP client for price scraping
- **json5** (>=0.12.0) - JavaScript object parsing for DWR responses
- **pydantic** (>=2.11.7) - Data validation and models
- **python-dotenv** (>=1.0.0) - Environment variables

### File Structure

- `main.py` - MCP server with search_trains and find_station tools
- `price_checker.py` - Price checking wrapper using custom scraper
- `update_data.py` - GTFS data download and update module
- `test.ipynb` - Interactive Jupyter notebook for testing
- `renfe_scraper/` - Custom DWR-based price scraper implementation
  - `scraper.py` - Main RenfeScraper class with DWR protocol
  - `dwr.py` - DWR protocol utilities and payload builders
  - `models.py` - Pydantic data models (Station, TrainRide)
  - `exceptions.py` - Custom exception hierarchy
  - `stations.json` - Station code database
- `tests/` - Comprehensive test suite
  - Integration tests, pagination tests, and scraper tests
- `renfe_schedule/` - GTFS data directory (auto-populated)

## 📝 Data Source

GTFS data from [Renfe's Open Data Portal](https://data.renfe.com):
- **API Endpoint**: `https://data.renfe.com/api/3/action/resource_show`
- **Resource ID**: `25d6b043-9e47-4f99-bd91-edd51d782450`
- **Update Frequency**: Updated regularly by Renfe (checked on server startup)
- **Format**: GTFS (General Transit Feed Specification)
- **Size**: ~800 KB compressed, ~40 MB extracted

## 🐛 Known Issues

- Windows console may show encoding errors with Unicode characters (functionality not affected)
- Very large result sets (100+ trains) can be verbose but complete

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Ideas for Contributions

- [x] ~~Add price information~~ (✅ Implemented via web scraping)
- [ ] Support for train status/delays
- [ ] Multi-leg journey planning
- [ ] Visualization of routes on maps
- [ ] Additional query filters (train type, duration, etc.)
- [ ] Return trip price checking

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Renfe Operadora](https://www.renfe.com) for providing open GTFS data
- [FastMCP](https://github.com/jlowin/fastmcp) by [@jlowin](https://github.com/jlowin) for the excellent MCP framework
- [Anthropic](https://www.anthropic.com) for Claude and the Model Context Protocol
- The GTFS community for standardizing transit data

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/belgrano9/renfe_mcp_server/issues)
- **Discussions**: [GitHub Discussions](https://github.com/belgrano9/renfe_mcp_server/discussions)
- **MCP Docs**: [Model Context Protocol](https://modelcontextprotocol.io)

## 🔗 Related Projects

- [SNCF MCP Server](https://github.com/belgrano9/sncf_mcp_server) - Similar server for French railways
- [FastMCP](https://github.com/jlowin/fastmcp) - The framework powering this server
- [MCP Servers](https://github.com/modelcontextprotocol/servers) - Official MCP server implementations

## 🙏 Sources & Inspiration

- **[renfe-bot](https://github.com/emartinez-dev/renfe-bot)** by [@emartinez-dev](https://github.com/emartinez-dev) - Telegram bot for Renfe train ticket monitoring. The DWR (Direct Web Remoting) protocol reverse-engineering and price scraping techniques were inspired by renfe-bot's implementation. This MCP server features a custom-built scraper using modern Python (httpx, pydantic) while preserving the core DWR protocol logic.

---

**Built with ❤️ using [FastMCP](https://github.com/jlowin/fastmcp) and [Claude](https://claude.ai)**

*Travel smart, travel by train! 🚄*
