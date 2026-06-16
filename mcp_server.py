# mcp_server.py

from numpy import save
from support import DataManager, Reporter
import os
import base64
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # deve stare prima di ogni altro import matplotlib
from mcp.server.fastmcp import FastMCP, Context
from pathlib import Path

# ── Ancora la cwd alla root del progetto Casa/ ──────────────────────────────
# Funziona ovunque venga lanciato il server MCP, indipendentemente dalla
# working directory del client (Claude Desktop, Cursor, ecc.)
# oppure .parent.parent a seconda di dove sta server.py
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
SAVE_PATH = PROJECT_ROOT / "report"
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("casa-spese")


def _load_dataset() -> pd.DataFrame:
    """Funzione interna condivisa — non esposta come tool né resource."""
    cfg = DataManager.cfg(
        with_update=False,
        upload_data_dict=False,
        load_from_sql=True,
        in_place=False,
        save_to_sql=False,
        de_duplicate=False,
        include_personal_expenses=True,
    )
    return DataManager.load(cfg)


# ── RISORSA ───────────────────────────────────────────────────────────────────

@mcp.resource("casa://dataset")
def get_dataset() -> str:
    """
    Carica e restituisce il dataset delle spese di casa come JSON.
    Usare questa risorsa come fonte dati per tutti i tool.
    """
    return _load_dataset().to_json(orient="records", date_format="iso", force_ascii=False)


# ── TOOL ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def run_report() -> str:
    """
    Genera il report testuale delle spese e lo salva in ./report/reports.txt.
    Legge i dati dalla risorsa casa://dataset.
    """
    save_path = Path(os.path.join(SAVE_PATH, "reports.txt"))
    
    df = _load_dataset()
    df["data_operazione"] = pd.to_datetime(df["data_operazione"])
    Reporter.report(df, save_path=save_path)
    
    # Legge il file appena generato per restituirlo all'utente
    report_conteuto = save_path.read_text(encoding="utf-8")
    return f"Report generato con successo!\n\nEcco il contenuto di {save_path.name}:\n\n{report_conteuto}"


@mcp.tool()
def run_dashboard() -> list:
    """
    Genera la dashboard grafica delle spese e la salva come PNG.
    Percorso output: /Users/paolo/Casa/report/dashboard.png
    Ritorna l'immagine codificata in base64 così Claude può visualizzarla.
    """
    save_path = Path(os.path.join(SAVE_PATH, "dashboard.png"))
    save_path.parent.mkdir(parents=True, exist_ok=True)

    df = _load_dataset()
    df["data_operazione"] = pd.to_datetime(df["data_operazione"])

    Reporter.dashboard(df=df, save_path=save_path)

    img_data = base64.standard_b64encode(save_path.read_bytes()).decode("utf-8")

    return [
        {
            "type": "text",
            "text": f"Dashboard generata in: {save_path.resolve()}"
        },
        {
            "type": "image",
            "data": img_data,
            "mimeType": "image/png"
        }
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")