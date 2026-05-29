"""Safe BigQuery helpers for EcomInsight Agent.

This module is the grounded data layer for the ecommerce assignment. It exposes
deterministic analysis functions over BigQuery's public `thelook_ecommerce`
dataset and a guarded SQL runner for read-only exploratory queries.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_MAX_BYTES_BILLED = 100_000_000
DEFAULT_LIMIT = 10
MAX_LIMIT = 1_000

DATASET = "bigquery-public-data.thelook_ecommerce"
ORDERS_TABLE = f"{DATASET}.orders"
ORDER_ITEMS_TABLE = f"{DATASET}.order_items"
PRODUCTS_TABLE = f"{DATASET}.products"
USERS_TABLE = f"{DATASET}.users"
EVENTS_TABLE = f"{DATASET}.events"

ALLOWED_TABLES = frozenset(
    {
        ORDERS_TABLE,
        ORDER_ITEMS_TABLE,
        PRODUCTS_TABLE,
        USERS_TABLE,
        EVENTS_TABLE,
    }
)

FORBIDDEN_SQL_KEYWORDS = (
    "ALTER",
    "CALL",
    "CREATE",
    "DELETE",
    "DROP",
    "EXPORT",
    "GRANT",
    "INSERT",
    "MERGE",
    "REPLACE",
    "REVOKE",
    "TRUNCATE",
    "UPDATE",
)


class BigQueryToolError(RuntimeError):
    """Raised when the BigQuery retrieval layer cannot run safely."""


def _load_env_file() -> None:
    """Load `.env` values without overriding exported environment variables."""
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _get_bigquery_module():
    try:
        from google.cloud import bigquery
    except ModuleNotFoundError as exc:
        raise BigQueryToolError(
            "google-cloud-bigquery is not installed. Run `uv sync --extra adk` "
            "or add google-cloud-bigquery to the project dependencies."
        ) from exc
    return bigquery


def _bigquery_client():
    _load_env_file()
    bigquery = _get_bigquery_module()
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip() or None
    return bigquery.Client(project=project)


def _max_bytes_billed() -> int:
    _load_env_file()
    raw_value = os.getenv("BIGQUERY_MAX_BYTES_BILLED", str(DEFAULT_MAX_BYTES_BILLED))
    try:
        max_bytes = int(raw_value)
    except ValueError as exc:
        raise ValueError("BIGQUERY_MAX_BYTES_BILLED must be an integer.") from exc

    if max_bytes < 1:
        raise ValueError("BIGQUERY_MAX_BYTES_BILLED must be greater than zero.")
    return max_bytes


def _bigquery_location() -> str | None:
    _load_env_file()
    return os.getenv("BIGQUERY_LOCATION", "US").strip() or None


def _validate_limit(limit: int) -> int:
    try:
        safe_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer.") from exc

    if safe_limit < 1:
        raise ValueError("limit must be at least 1.")
    return min(safe_limit, MAX_LIMIT)


def _strip_sql_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--.*?$", " ", without_block_comments, flags=re.MULTILINE)


def _mask_sql_literals(sql: str) -> str:
    """Replace quoted SQL literal and identifier contents with spaces."""
    result: list[str] = []
    index = 0

    while index < len(sql):
        char = sql[index]
        if char not in {"'", '"', "`"}:
            result.append(char)
            index += 1
            continue

        quote = char
        result.append(quote)
        index += 1

        while index < len(sql):
            current = sql[index]

            if current == "\\" and quote in {"'", '"'} and index + 1 < len(sql):
                result.extend("  ")
                index += 2
                continue

            if current == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    result.extend("  ")
                    index += 2
                    continue

                result.append(quote)
                index += 1
                break

            result.append(" ")
            index += 1

    return "".join(result)


def _extract_table_references(sql: str) -> set[str]:
    """Extract fully-qualified BigQuery table references from SQL."""
    normalized = _strip_sql_comments(sql)
    references = set()

    for identifier in re.findall(r"`([^`]+)`", normalized):
        if identifier.count(".") >= 2:
            references.add(identifier)

    table_pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+`?([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)`?",
        flags=re.IGNORECASE,
    )
    references.update(table_pattern.findall(normalized))
    return references


def _validate_allowed_tables(sql: str) -> None:
    table_references = _extract_table_references(sql)
    blocked_tables = sorted(table_references - ALLOWED_TABLES)

    if blocked_tables:
        allowed = ", ".join(sorted(ALLOWED_TABLES))
        blocked = ", ".join(blocked_tables)
        raise ValueError(
            f"SQL references tables outside the allowed ecommerce dataset: "
            f"{blocked}. Allowed tables: {allowed}."
        )


def _contains_limit(sql: str) -> bool:
    masked_sql = _mask_sql_literals(_strip_sql_comments(sql))
    return bool(re.search(r"\bLIMIT\b", masked_sql, flags=re.IGNORECASE))


def _ensure_limit(sql: str, limit: int) -> str:
    cleaned_sql = sql.strip().rstrip(";")
    if _contains_limit(cleaned_sql):
        return cleaned_sql
    return f"{cleaned_sql}\nLIMIT {limit}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def validate_read_only_sql(sql: str) -> None:
    """Validate that SQL is a single read-only query over allowed tables.

    The validator is intentionally independent from the LLM prompt. It accepts
    only `SELECT` or `WITH`, rejects multi-statement SQL, blocks write/DDL
    keywords, and verifies that fully-qualified table references stay inside
    `bigquery-public-data.thelook_ecommerce`.
    """
    if not sql or not sql.strip():
        raise ValueError("SQL cannot be empty.")

    normalized = _strip_sql_comments(sql).strip()
    masked_sql = _mask_sql_literals(normalized)
    upper_sql = masked_sql.upper()

    if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
        raise ValueError("Only SELECT or WITH queries are allowed.")

    if ";" in masked_sql.rstrip(";"):
        raise ValueError("Only one SQL statement is allowed.")

    keyword_pattern = r"\b(" + "|".join(FORBIDDEN_SQL_KEYWORDS) + r")\b"
    if re.search(keyword_pattern, upper_sql):
        raise ValueError("SQL contains a forbidden write, DDL, or procedure keyword.")

    _validate_allowed_tables(normalized)


def run_read_only_query(
    sql: str,
    *,
    query_parameters: list[Any] | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Run validated read-only SQL and return BigQuery rows as dictionaries."""
    safe_limit = _validate_limit(limit)
    limited_sql = _ensure_limit(sql, safe_limit)
    validate_read_only_sql(limited_sql)

    bigquery = _get_bigquery_module()
    client = _bigquery_client()

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=_max_bytes_billed(),
        query_parameters=query_parameters or [],
        use_query_cache=True,
    )
    rows = client.query(
        limited_sql,
        job_config=job_config,
        location=_bigquery_location(),
    ).result(max_results=safe_limit)

    return [_json_safe(dict(row.items())) for row in rows]


def run_safe_bigquery_sql(sql: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """ADK-friendly wrapper for guarded exploratory SQL queries."""
    safe_limit = _validate_limit(limit)
    limited_sql = _ensure_limit(sql, safe_limit)
    rows = run_read_only_query(limited_sql, limit=safe_limit)
    return {
        "status": "ok",
        "dataset": DATASET,
        "sql": limited_sql,
        "rows_returned": len(rows),
        "rows": rows,
        "maximum_bytes_billed": _max_bytes_billed(),
    }


def get_revenue_by_category(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return completed-order revenue by product category."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      p.category,
      COUNT(DISTINCT oi.order_id) AS total_orders,
      COUNT(*) AS units_sold,
      ROUND(SUM(oi.sale_price), 2) AS total_revenue,
      ROUND(AVG(oi.sale_price), 2) AS avg_item_price
    FROM `{ORDER_ITEMS_TABLE}` AS oi
    JOIN `{PRODUCTS_TABLE}` AS p
      ON oi.product_id = p.id
    WHERE oi.status = 'Complete'
    GROUP BY p.category
    ORDER BY total_revenue DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_category = rows[0]["category"] if rows else None
    return {
        "question": "Revenue by product category",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The top category by completed-order revenue is {top_category}."
            if top_category
            else "No completed category revenue rows were returned."
        ),
    }


def get_top_products_by_revenue(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return products ranked by completed-order revenue."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      p.name AS product_name,
      p.category,
      p.brand,
      COUNT(*) AS units_sold,
      ROUND(SUM(oi.sale_price), 2) AS total_revenue
    FROM `{ORDER_ITEMS_TABLE}` AS oi
    JOIN `{PRODUCTS_TABLE}` AS p
      ON oi.product_id = p.id
    WHERE oi.status = 'Complete'
    GROUP BY product_name, p.category, p.brand
    ORDER BY total_revenue DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_product = rows[0]["product_name"] if rows else None
    return {
        "question": "Top products by revenue",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The top product by completed-order revenue is {top_product}."
            if top_product
            else "No completed product revenue rows were returned."
        ),
    }


def get_sales_by_country(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return completed-order revenue, orders, customers, and AOV by country."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      u.country,
      COUNT(DISTINCT oi.order_id) AS total_orders,
      COUNT(DISTINCT u.id) AS total_customers,
      ROUND(SUM(oi.sale_price), 2) AS total_revenue,
      ROUND(SAFE_DIVIDE(SUM(oi.sale_price), COUNT(DISTINCT oi.order_id)), 2)
        AS avg_order_value
    FROM `{ORDER_ITEMS_TABLE}` AS oi
    JOIN `{USERS_TABLE}` AS u
      ON oi.user_id = u.id
    WHERE oi.status = 'Complete'
    GROUP BY u.country
    ORDER BY total_revenue DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_country = rows[0]["country"] if rows else None
    return {
        "question": "Sales by country",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The highest-revenue country is {top_country}."
            if top_country
            else "No completed country sales rows were returned."
        ),
    }


def get_order_status_breakdown(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return item counts and percentages by order item status."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      status,
      COUNT(*) AS total_items,
      ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS percentage
    FROM `{ORDER_ITEMS_TABLE}`
    GROUP BY status
    ORDER BY total_items DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_status = rows[0]["status"] if rows else None
    return {
        "question": "Order status breakdown",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The most common order item status is {top_status}."
            if top_status
            else "No order status rows were returned."
        ),
    }


def get_monthly_revenue(limit: int = 24) -> dict[str, Any]:
    """Return completed-order monthly revenue and order volume."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      FORMAT_DATE('%Y-%m', DATE(created_at)) AS month,
      ROUND(SUM(sale_price), 2) AS total_revenue,
      COUNT(DISTINCT order_id) AS total_orders
    FROM `{ORDER_ITEMS_TABLE}`
    WHERE status = 'Complete'
    GROUP BY month
    ORDER BY month DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    return {
        "question": "Monthly revenue trend",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": f"Returned {len(rows)} monthly revenue rows.",
    }


def get_customers_by_country(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return customer counts by country."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      country,
      COUNT(*) AS total_customers,
      ROUND(AVG(age), 2) AS avg_age
    FROM `{USERS_TABLE}`
    GROUP BY country
    ORDER BY total_customers DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_country = rows[0]["country"] if rows else None
    return {
        "question": "Customers by country",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The country with the largest customer count is {top_country}."
            if top_country
            else "No customer country rows were returned."
        ),
    }


def get_average_order_value_by_category(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Return average completed order value by product category."""
    safe_limit = _validate_limit(limit)
    sql = f"""
    SELECT
      category,
      COUNT(*) AS total_orders,
      ROUND(AVG(order_revenue), 2) AS avg_order_value,
      ROUND(SUM(order_revenue), 2) AS total_revenue
    FROM (
      SELECT
        p.category,
        oi.order_id,
        SUM(oi.sale_price) AS order_revenue
      FROM `{ORDER_ITEMS_TABLE}` AS oi
      JOIN `{PRODUCTS_TABLE}` AS p
        ON oi.product_id = p.id
      WHERE oi.status = 'Complete'
      GROUP BY p.category, oi.order_id
    )
    GROUP BY category
    ORDER BY avg_order_value DESC
    LIMIT {safe_limit}
    """
    rows = run_read_only_query(sql, limit=safe_limit)
    top_category = rows[0]["category"] if rows else None
    return {
        "question": "Average order value by category",
        "dataset": DATASET,
        "sql": sql.strip(),
        "rows_returned": len(rows),
        "rows": rows,
        "summary": (
            f"The category with the highest average order value is {top_category}."
            if top_category
            else "No average order value rows were returned."
        ),
    }
