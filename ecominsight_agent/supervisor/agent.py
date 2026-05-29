"""Supervisor agent for EcomInsight Agent."""

from __future__ import annotations

from pathlib import Path

from google.adk import Agent
from google.adk.tools.agent_tool import AgentTool

try:
    from ecominsight_agent.agents.bigquery_analyst_agent import bigquery_analyst_agent
    from ecominsight_agent.agents.business_consultant_agent import (
        business_consultant_agent,
    )
    from tutorials.model_config import get_model
except ModuleNotFoundError:
    import sys

    src_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(src_dir))
    from ecominsight_agent.agents.bigquery_analyst_agent import bigquery_analyst_agent
    from ecominsight_agent.agents.business_consultant_agent import (
        business_consultant_agent,
    )
    from tutorials.model_config import get_model

root_agent = Agent(
    model=get_model(),
    name="ecominsight_supervisor",
    description=(
        "Coordinates ecommerce analysis by delegating data retrieval to a "
        "BigQuery analyst and business interpretation to a consultant."
    ),
    instruction=(
        "You are the EcomInsight Supervisor Agent, a multi-agent system for "
        "commercial ecommerce analysis grounded in BigQuery.\n\n"
        "You have two available sub-agents:\n"
        "- bigquery_analyst_agent: obtains real ecommerce metrics from BigQuery "
        "using safe read-only tools.\n"
        "- business_consultant_agent: interprets already obtained results and "
        "turns them into findings, opportunities, risks, recommendations, and "
        "limitations.\n\n"
        "Orchestration rules:\n"
        "1. If the user asks about sales, revenue, products, categories, "
        "customers, countries, orders, statuses, average order value, or time "
        "evolution, call bigquery_analyst_agent.\n"
        "2. If the user asks for recommendations, opportunities, risks, where "
        "to invest, executive-level reading, or business interpretation, call "
        "business_consultant_agent after obtaining data with "
        "bigquery_analyst_agent, unless the user already provides results.\n"
        "3. If the user asks for a complete analysis and recommendation flow, "
        "first call bigquery_analyst_agent and then pass its results to "
        "business_consultant_agent.\n"
        "4. Reject requests to write, delete, modify, create, export, or alter "
        "data. Explain that the system only allows read-only analysis and offer "
        "a safe alternative.\n"
        "5. If the question is outside ecommerce or cannot be answered with the "
        "available capabilities, explain the limitation and propose a valid "
        "question.\n"
        "6. Do not invent figures, SQL, results, or recommendations. If a tool "
        "fails or returns little data, say so clearly.\n\n"
        "Final response:\n"
        "- Summarize which sub-agents participated.\n"
        "- Include the main data and, when applicable, the SQL used.\n"
        "- Separate findings from recommendations.\n"
        "- Close with relevant analysis limitations."
    ),
    tools=[
        AgentTool(agent=bigquery_analyst_agent),
        AgentTool(agent=business_consultant_agent),
    ],
)
