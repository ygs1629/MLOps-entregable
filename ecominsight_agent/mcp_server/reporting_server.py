"""MCP reporting server for EcomInsight Agent.

Run from the repository root:

    uv run python -m ecominsight_agent.mcp_server.reporting_server

The server exposes reporting tools over SSE at http://127.0.0.1:9003/sse by
default. It creates Markdown reports, JSON snapshots, and compact KPI cards for
the ecommerce analysis workflow.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports" / "generated"
DEFAULT_SNAPSHOTS_DIR = REPO_ROOT / "reports" / "snapshots"
DEFAULT_KPI_DIR = REPO_ROOT / "reports" / "kpi_cards"

mcp = FastMCP(
    name="ecominsight-reporting-mcp-server",
    host=os.getenv("ECOMINSIGHT_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("ECOMINSIGHT_MCP_PORT", "9003")),
)


def _load_env_file() -> None:
    """Load `.env` values if they are not already exported."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _output_dir(env_name: str, default_dir: Path) -> Path:
    _load_env_file()
    configured_dir = os.getenv(env_name, str(default_dir))
    output_dir = Path(configured_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _reports_dir() -> Path:
    return _output_dir("REPORTS_DIR", DEFAULT_REPORTS_DIR)


def _snapshots_dir() -> Path:
    return _output_dir("SNAPSHOTS_DIR", DEFAULT_SNAPSHOTS_DIR)


def _kpi_dir() -> Path:
    return _output_dir("KPI_CARDS_DIR", DEFAULT_KPI_DIR)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return _utc_now().strftime("%Y%m%dT%H%M%SZ")


def _safe_slug(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or fallback


def _safe_output_path(output_dir: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    output_path = (output_dir / safe_name).resolve()
    if output_dir.resolve() not in output_path.parents:
        raise ValueError("Output file must stay inside the configured directory.")
    return output_path


def _coerce_string_list(value: list[str] | None) -> list[str]:
    if value is None:
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _markdown_list(items: list[str], empty_text: str) -> str:
    clean_items = _coerce_string_list(items)
    if not clean_items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in clean_items)


def _metadata_block(metadata: dict[str, Any]) -> str:
    return (
        "<!-- metadata\n"
        f"{json.dumps(metadata, ensure_ascii=False, indent=2)}\n"
        "-->"
    )


@mcp.tool(description="Create a Markdown executive business report for an ecommerce analysis.")
def create_business_report(
    title: str,
    question: str,
    sql_used: str = "",
    key_findings: list[str] | None = None,
    recommendations: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, str]:
    """Create a Markdown report with findings, recommendations, and limitations."""
    clean_title = title.strip() or "EcomInsight business report"
    created_at = _utc_now().isoformat()
    filename = f"{_timestamp()}-{_safe_slug(clean_title, 'business-report')}.md"
    report_path = _safe_output_path(_reports_dir(), filename)

    metadata = {
        "title": clean_title,
        "created_at": created_at,
        "question": question,
        "tool": "create_business_report",
    }
    sql_block = sql_used.strip() or "No SQL provided."
    content = (
        f"{_metadata_block(metadata)}\n\n"
        f"# {clean_title}\n\n"
        f"**Created at:** {created_at}\n\n"
        "## Business question\n\n"
        f"{question.strip() or 'No question provided.'}\n\n"
        "## SQL used\n\n"
        "```sql\n"
        f"{sql_block}\n"
        "```\n\n"
        "## Key findings\n\n"
        f"{_markdown_list(key_findings, 'No key findings were provided.')}\n\n"
        "## Recommendations\n\n"
        f"{_markdown_list(recommendations, 'No recommendations were provided.')}\n\n"
        "## Limitations\n\n"
        f"{_markdown_list(limitations, 'No limitations were provided.')}\n"
    )
    report_path.write_text(content, encoding="utf-8")

    return {
        "status": "ok",
        "file_path": str(report_path),
        "message": "Business report created successfully.",
    }


@mcp.tool(description="Save a JSON snapshot with traceability for an ecommerce analysis.")
def save_analysis_snapshot(
    user_question: str,
    agent_used: str,
    sql_used: str = "",
    rows_returned: int = 0,
    summary: str = "",
    recommendations: list[str] | None = None,
    timestamp: str = "",
    extra_context: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Save a JSON snapshot of the analysis question, SQL, result summary, and advice."""
    created_at = timestamp.strip() or _utc_now().isoformat()
    slug_source = user_question or summary or "analysis"
    filename = f"{_timestamp()}-{_safe_slug(slug_source, 'analysis-snapshot')}.json"
    snapshot_path = _safe_output_path(_snapshots_dir(), filename)

    payload = {
        "created_at": created_at,
        "user_question": user_question,
        "agent_used": agent_used,
        "sql_used": sql_used,
        "rows_returned": int(rows_returned),
        "summary": summary,
        "recommendations": _coerce_string_list(recommendations),
        "extra_context": extra_context or {},
    }
    snapshot_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "file_path": str(snapshot_path),
        "message": "Analysis snapshot saved successfully.",
    }


@mcp.tool(description="Generate a compact Markdown KPI card for an ecommerce metric.")
def generate_kpi_card(
    kpi_name: str,
    value: str,
    period: str,
    interpretation: str,
    risk_level: str = "medium",
    recommendation: str = "",
    save_to_file: bool = False,
) -> dict[str, str]:
    """Generate a concise KPI card and optionally persist it as Markdown."""
    clean_kpi_name = kpi_name.strip() or "Unnamed KPI"
    clean_risk = risk_level.strip().lower() or "medium"
    card = (
        f"## KPI: {clean_kpi_name}\n\n"
        f"- Value: {value.strip() or 'Not provided'}\n"
        f"- Period: {period.strip() or 'Not provided'}\n"
        f"- Risk level: {clean_risk}\n"
        f"- Interpretation: {interpretation.strip() or 'No interpretation provided.'}\n"
        f"- Recommendation: {recommendation.strip() or 'No recommendation provided.'}"
    )

    result = {
        "status": "ok",
        "kpi_card": card,
        "message": "KPI card generated successfully.",
    }

    if save_to_file:
        filename = f"{_timestamp()}-{_safe_slug(clean_kpi_name, 'kpi-card')}.md"
        kpi_path = _safe_output_path(_kpi_dir(), filename)
        metadata = {
            "kpi_name": clean_kpi_name,
            "created_at": _utc_now().isoformat(),
            "period": period,
            "risk_level": clean_risk,
            "tool": "generate_kpi_card",
        }
        kpi_path.write_text(
            f"{_metadata_block(metadata)}\n\n{card}\n",
            encoding="utf-8",
        )
        result["file_path"] = str(kpi_path)

    return result


def main() -> None:
    """Run the MCP server over SSE."""
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
