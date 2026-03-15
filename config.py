"""
Configuration for AI Cost Monitor plugin.
"""

from dataclasses import dataclass


@dataclass
class AICostConfig:
    """Configuration for AI Cost Monitor."""

    # Daily report settings
    enable_daily_report: bool = False
    report_time: str = "08:00"

    # Azure OpenAI credentials
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""

    # OpenRouter
    openrouter_api_key: str = ""

    # Google Cloud / BigQuery
    google_project_id: str = ""
    google_bq_table: str = ""
    google_service_account_json: str = ""

    # xAI
    xai_api_key: str = ""
    xai_team_id: str = ""
