"""Security tests for EcomInsight BigQuery SQL validation."""

from __future__ import annotations

import pytest

from ecominsight_agent.retrieval.bigquery_tools import (
    _ensure_limit,
    validate_read_only_sql,
)


def test_validate_read_only_sql_allows_select_on_allowed_table():
    sql = "SELECT * FROM `bigquery-public-data.thelook_ecommerce.orders` LIMIT 10"

    validate_read_only_sql(sql)


def test_validate_read_only_sql_allows_with_on_allowed_table():
    sql = """
    WITH completed_items AS (
      SELECT *
      FROM `bigquery-public-data.thelook_ecommerce.order_items`
      WHERE status = 'Complete'
    )
    SELECT COUNT(*) AS total_completed_items
    FROM completed_items
    """

    validate_read_only_sql(sql)


@pytest.mark.parametrize(
    "keyword",
    [
        "ALTER",
        "CALL",
        "CREATE",
        "DELETE",
        "DROP",
        "EXPORT",
        "INSERT",
        "MERGE",
        "TRUNCATE",
        "UPDATE",
    ],
)
def test_validate_read_only_sql_rejects_write_and_ddl_keywords(keyword):
    sql = (
        "SELECT * "
        "FROM `bigquery-public-data.thelook_ecommerce.orders` "
        f"WHERE status = 'Complete'; {keyword} something"
    )

    with pytest.raises(ValueError):
        validate_read_only_sql(sql)


def test_validate_read_only_sql_rejects_non_select_statement():
    sql = "DELETE FROM `bigquery-public-data.thelook_ecommerce.orders` WHERE TRUE"

    with pytest.raises(ValueError, match="Only SELECT or WITH queries are allowed"):
        validate_read_only_sql(sql)


def test_validate_read_only_sql_rejects_multiple_statements():
    sql = (
        "SELECT * FROM `bigquery-public-data.thelook_ecommerce.orders`; "
        "SELECT * FROM `bigquery-public-data.thelook_ecommerce.users`"
    )

    with pytest.raises(ValueError, match="Only one SQL statement"):
        validate_read_only_sql(sql)


def test_validate_read_only_sql_rejects_tables_outside_ecommerce_dataset():
    sql = "SELECT * FROM `bigquery-public-data.stackoverflow.posts_questions` LIMIT 10"

    with pytest.raises(ValueError, match="outside the allowed ecommerce dataset"):
        validate_read_only_sql(sql)


def test_validate_read_only_sql_allows_semicolon_inside_string_literal():
    sql = """
    SELECT '; DROP TABLE orders;' AS suspicious_text
    FROM `bigquery-public-data.thelook_ecommerce.orders`
    LIMIT 1
    """

    validate_read_only_sql(sql)


def test_validate_read_only_sql_ignores_forbidden_words_inside_string_literal():
    sql = """
    SELECT 'please delete this text, not data' AS user_text
    FROM `bigquery-public-data.thelook_ecommerce.orders`
    LIMIT 1
    """

    validate_read_only_sql(sql)


def test_ensure_limit_adds_limit_when_missing():
    sql = "SELECT * FROM `bigquery-public-data.thelook_ecommerce.orders`"

    limited_sql = _ensure_limit(sql, 25)

    assert limited_sql.endswith("LIMIT 25")


def test_ensure_limit_keeps_existing_limit():
    sql = "SELECT * FROM `bigquery-public-data.thelook_ecommerce.orders` LIMIT 5"

    limited_sql = _ensure_limit(sql, 25)

    assert limited_sql == sql
