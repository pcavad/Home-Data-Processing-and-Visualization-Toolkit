# Home-Data-Processing-and-Visualization-Toolkit

A robust, production-grade Python utility designed for aggregating, processing, validating, and visualizing home financial transactions. The toolkit standardizes raw bank/credit card data, cross-references transaction classifications using a local NoSQL metadata engine, tracks dataset drift through statistical validation, and features a built-in Model Context Protocol (MCP) server to allow direct integration with AI assistants.

## 🚀 Key Features

* **Advanced Data Management & Storage**: Powered by a central SQLite database (`transazioni.db`) for structured transactions, complemented by a lightweight TinyDB NoSQL database (`metadata_tinydb.json`) for dynamic text standardization and category mapping.
* **Strict Type & Data Validation**: Leverages `pydantic` schemas for runtime verification of application states, date contexts (`DateContext`), and defensive configuration management.
* **Analytical Dashboards & Reporting**: 
  * Generates multi-dimensional text-based financial summaries and historical budget comparisons (`reports.txt`).
  * Plots automated visual trends (such as line, bar, or cumulative sum metrics) saved natively as high-resolution graphics (`dashboard.png`).
* **Predictive Financial Forecasting (Optional)**: Integrates advanced time-series predictive modeling directly within the reporting suite (`support/reporter.py`). Utilizing Meta's **Prophet** library, the toolkit can optionally process historical transactional trajectories to project expense trends and baseline spending behaviors into the upcoming months.
* **Data Slicing & Statistical Validation**: Includes statistical profiling tools to track data distributions over custom date intervals (e.g., base periods vs. evaluation periods), isolating new categorical values and structural changes in spending habits.
* **AI-Native Integrations (MCP Server)**: Features a dedicated Model Context Protocol interface via `FastMCP`. This exposes financial resources and analytical capabilities as tools directly consumable by modern AI clients (like Claude Desktop, Cursor, or Gemini), enabling natural language queries over personal spending data.

---

## 📂 Project Directory Structure

```text
/Casa
├── data/
│   ├── transazioni.db          # Main SQLite storage engine for financial records
│   ├── data_dict.json          # Dictionary schema configuration mapping transaction states
│   └── metadata_tinydb.json    # TinyDB NoSQL file managing merchant/category classification rules
├── env/                        # Python virtual environment
├── report/                     # Automated analysis output directory
│   ├── dashboard.png           # Graphic dashboard visualizations
│   ├── numeric_diff.png        # Statistical validation data delta plots
│   ├── validation.txt          # Text summaries of data consistency checks
│   └── reports.txt             # Financial budget summaries, operational logs, and forecasts
├── support/                    # Modular subsystem package
│   ├── __init__.py             # Static manager interface initialization (DataManager & Reporter facades)
│   ├── config.py               # Application and extraction hyperparameters
│   ├── data_manager.py         # SQLite connection layer, loading logic, and preprocessing routines
│   ├── metadata_manager.py     # TinyDB interface for cleaning, aliasing, and mapping descriptions
│   ├── reporter.py             # Analytical engines, matplotlib plot factories, and Prophet forecasting
│   ├── utils.py                # Time-series utility frameworks and operational context handlers
│   ├── validators.py           # Integrity evaluation and validation rules
├── main.py                     # Standard execution entry point for local pipeline generation
└── mcp_server.py               # FastMCP Server implementation exporting tools/resources to AI agents
```

## 📦 Core Python Dependencies

The system leverages a modern Python ecosystem centered around performance, rigorous validation, predictive analysis, and developer ergonomics:

* **pandas**: Coordinates heavy data manipulation, time-series indexing, aggregation, and tabular alignment.

* **pydantic**: Enforces strict parsing and runtime validation for dates, metrics, and state management.

* **tinydb**: Serves as a lightweight document database optimized for storing schema mapping and fuzzy description lookups.

* **matplotlib**: Powers the underlying data visualization pipeline, compiling financial matrices into diagnostic plots.

* **prophet**: (Optional) Handles additive non-linear time-series forecasting to predict upcoming monthly financial data patterns and trends.

* **mcp / fastmcp**: Implements the Model Context Protocol framework to safely expose resources and tools to AI workflows.

* **sqlite3 (Standard Library)**: Manages low-latency relational transactions.

## 🛠️ Usage

**Local Analytical Pipeline**

Execute the main script to step through structural metadata checks, update relational tables, generate the monthly performance summaries (including optional predictive forecasting updates), and compile statistical verification metrics:

```
python main.py
```

**Exposing to AI Assistants via MCP**

Launch the FastMCP protocol server instance. Once active, compatible clients (e.g., Cursor, Claude Desktop) can fetch data directly via native tool hooks like run_report() and run_dashboard():

```
mcp dev mcp_server.py
```

**🪵 Project Evolution & AI Heritage**

**Development Note**

This toolkit represents a hybrid approach to software engineering. The foundational framework, business logic rules, custom core data parsers, and financial ledger mathematics were completely architected and written manually without the assistance of AI.

As the ecosystem matured, the project was systematically refactored, robust validation loops were introduced, and the platform was upgraded into an AI-agent utility using Cursor alongside various Google Gemini models. This collaborative optimization phase introduced strict Pydantic definitions, automated NoSQL mapping, advanced time-series forecasting integrations via Prophet, and the implementation of the Model Context Protocol (MCP) server layer
