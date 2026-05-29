"""BigQuery analyst sub-agent for EcomInsight Agent."""

from __future__ import annotations

from pathlib import Path

from google.adk import Agent

try:
    from ecominsight_agent.retrieval.bigquery_tools import (
        get_average_order_value_by_category,
        get_customers_by_country,
        get_monthly_revenue,
        get_order_status_breakdown,
        get_revenue_by_category,
        get_sales_by_country,
        get_top_products_by_revenue,
    )
    from tutorials.model_config import get_model
except ModuleNotFoundError:
    import sys

    src_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(src_dir))
    from ecominsight_agent.retrieval.bigquery_tools import (
        get_average_order_value_by_category,
        get_customers_by_country,
        get_monthly_revenue,
        get_order_status_breakdown,
        get_revenue_by_category,
        get_sales_by_country,
        get_top_products_by_revenue,
    )
    from tutorials.model_config import get_model

bigquery_analyst_agent = Agent(
    model=get_model(),
    name="bigquery_analyst_agent",
    description=(
        "Analyzes ecommerce sales, customers, products, orders, countries, "
        "categories, revenue, and average order value using safe BigQuery tools."
    ),
    instruction=(
        "You are the EcomInsight BigQuery Analyst Agent, a sub-agent specialized "
        "in ecommerce analysis with BigQuery.\n\n"
        "Scope:\n"
        "- Answer only ecommerce questions related to sales, orders, products, "
        "categories, customers, countries, revenue, average order value, and "
        "time evolution.\n"
        "- Use only the available BigQuery tools. Do not invent metrics, tables, "
        "SQL, or results.\n"
        "- The tools already apply security controls: read-only queries, allowed "
        "tables, row limits, and maximum billed bytes.\n\n"
        "Security rules:\n"
        "1. Reject any request to create, modify, delete, truncate, export, or "
        "alter data.\n"
        "2. If the user asks for a dangerous operation, explain that you can only "
        "perform read-only analysis and offer a safe alternative, such as "
        "analyzing cancelled orders without modifying them.\n"
        "3. If the question is outside the ecommerce domain, say so clearly and "
        "do not call tools.\n\n"
        "Response format:\n"
        "- SQL used: include the query returned by the tool.\n"
        "- Main rows: show the most relevant rows without inventing data.\n"
        "- Summary: briefly explain what the results indicate.\n"
        "- Limitations: mention any limited scope, missing data, or necessary "
        "caution."
    ),
    tools=[
        get_revenue_by_category,
        get_top_products_by_revenue,
        get_sales_by_country,
        get_order_status_breakdown,
        get_monthly_revenue,
        get_customers_by_country,
        get_average_order_value_by_category,
    ],
)
