"""Tests for EcomInsight MCP reporting tools."""

from __future__ import annotations

import json
from pathlib import Path

from ecominsight_agent.mcp_server.reporting_server import (
    create_business_report,
    generate_kpi_card,
    save_analysis_snapshot,
)


def test_create_business_report_writes_markdown_file(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path / "reports"))

    result = create_business_report(
        title="Ventas por pais",
        question="Que pais genera mas ingresos?",
        sql_used="SELECT country, total_revenue FROM sales LIMIT 10",
        key_findings=["Estados Unidos lidera los ingresos."],
        recommendations=["Priorizar mercados con alto ticket medio."],
        limitations=["Dataset publico de demostracion."],
    )

    report_path = Path(result["file_path"])

    assert result["status"] == "ok"
    assert report_path.exists()
    assert report_path.parent == tmp_path / "reports"

    content = report_path.read_text(encoding="utf-8")
    assert "# Ventas por pais" in content
    assert "## SQL used" in content
    assert "Estados Unidos lidera los ingresos." in content
    assert "Dataset publico de demostracion." in content


def test_save_analysis_snapshot_writes_json_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOTS_DIR", str(tmp_path / "snapshots"))

    result = save_analysis_snapshot(
        user_question="Que categorias generan mas ingresos?",
        agent_used="bigquery_analyst_agent",
        sql_used="SELECT category, total_revenue FROM categories LIMIT 10",
        rows_returned=10,
        summary="La categoria A lidera los ingresos.",
        recommendations=["Revisar margen antes de invertir."],
        timestamp="2026-05-28T10:00:00+00:00",
        extra_context={"dataset": "thelook_ecommerce"},
    )

    snapshot_path = Path(result["file_path"])
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert snapshot_path.exists()
    assert snapshot_path.parent == tmp_path / "snapshots"
    assert payload["user_question"] == "Que categorias generan mas ingresos?"
    assert payload["agent_used"] == "bigquery_analyst_agent"
    assert payload["rows_returned"] == 10
    assert payload["recommendations"] == ["Revisar margen antes de invertir."]
    assert payload["extra_context"] == {"dataset": "thelook_ecommerce"}


def test_generate_kpi_card_returns_markdown_without_file_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("KPI_CARDS_DIR", str(tmp_path / "kpis"))

    result = generate_kpi_card(
        kpi_name="Ingresos totales",
        value="1.250.000",
        period="2026",
        interpretation="Los ingresos se concentran en pocas categorias.",
        risk_level="medium",
        recommendation="Analizar margen por categoria.",
    )

    assert result["status"] == "ok"
    assert "## KPI: Ingresos totales" in result["kpi_card"]
    assert "file_path" not in result
    assert not (tmp_path / "kpis").exists()


def test_generate_kpi_card_can_write_markdown_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KPI_CARDS_DIR", str(tmp_path / "kpis"))

    result = generate_kpi_card(
        kpi_name="Ticket medio",
        value="72.40",
        period="2026",
        interpretation="El ticket medio es estable.",
        risk_level="low",
        recommendation="Mantener seguimiento mensual.",
        save_to_file=True,
    )

    kpi_path = Path(result["file_path"])

    assert result["status"] == "ok"
    assert kpi_path.exists()
    assert kpi_path.parent == tmp_path / "kpis"
    assert "## KPI: Ticket medio" in kpi_path.read_text(encoding="utf-8")
