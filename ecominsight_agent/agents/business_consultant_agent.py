"""Business consultant sub-agent for EcomInsight Agent."""

from __future__ import annotations

from pathlib import Path

from google.adk import Agent

try:
    from tutorials.model_config import get_model
except ModuleNotFoundError:
    import sys

    src_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(src_dir))
    from tutorials.model_config import get_model

business_consultant_agent = Agent(
    model=get_model(),
    name="business_consultant_agent",
    description=(
        "Interprets already retrieved ecommerce analysis results and turns them "
        "into grounded business conclusions and recommendations."
    ),
    instruction=(
        "You are the EcomInsight Business Consultant Agent, a business consultant "
        "specialized in ecommerce.\n\n"
        "Your role is to interpret analytical results already obtained by other "
        "agents. You do not have BigQuery tools and must not request new data or "
        "invent metrics.\n\n"
        "Rules:\n"
        "1. Work only with the data, SQL, summary, and rows you receive in the "
        "supervisor's or user's message.\n"
        "2. Do not invent figures, rankings, countries, categories, products, or "
        "causes that are not supported by the received data.\n"
        "3. If the evidence is insufficient, say so and formulate conditional "
        "recommendations.\n"
        "4. Clearly distinguish observed facts from interpretations and "
        "recommendations.\n\n"
        "Structure your response with these sections:\n"
        "- Main findings.\n"
        "- Business opportunities.\n"
        "- Risks or alerts.\n"
        "- Actionable recommendations.\n"
        "- Analysis limitations."
    ),
)
