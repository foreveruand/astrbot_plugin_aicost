"""
API clients for querying AI service costs.
Supports Azure OpenAI, OpenRouter, Google AI (BigQuery), and xAI.
"""

import asyncio
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiohttp

from astrbot.api import AstrBotConfig
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account

    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False


def get_provider_specs() -> list[dict]:
    """Return provider metadata in display order."""
    return [
        {
            "id": "google",
            "name": "Google Gemini",
            "enabled": lambda config: bool(
                config.get("google_project_id") and config.get("google_bq_table")
            ),
            "query": query_google_ai_cost,
        },
        {
            "id": "xai",
            "name": "xAI Grok",
            "enabled": lambda config: bool(
                config.get("xai_api_key") and config.get("xai_team_id")
            ),
            "query": query_xai_cost,
        },
        {
            "id": "openrouter",
            "name": "OpenRouter",
            "enabled": lambda config: bool(config.get("openrouter_api_key")),
            "query": query_openrouter_balance,
        },
        {
            "id": "azure",
            "name": "Azure OpenAI",
            "enabled": lambda config: bool(
                config.get("azure_tenant_id")
                and config.get("azure_client_id")
                and config.get("azure_client_secret")
                and config.get("azure_subscription_id")
            ),
            "query": query_azure_cost,
        },
    ]


def format_number(num: float) -> str:
    """Format large numbers, e.g., 12345 -> 12.3k."""
    if num >= 1000000:
        return f"{num / 1000000:.2f}M"
    if num >= 1000:
        return f"{num / 1000:.1f}k"
    return str(int(num))


def clean_azure_name(name: str) -> str:
    """Clean up Azure's verbose model names."""
    # Remove common prefixes
    name = re.sub(
        r"^(Cognitive Services|AI Services|Azure OpenAI) - ", "", name, flags=re.I
    )
    # Extract key model name (e.g., from "Global Provisioned Managed - GPT-4o" get "GPT-4o")
    parts = name.split(" - ")
    return parts[-1] if parts else name


async def query_azure_cost(config: "AstrBotConfig") -> dict:
    """Query Azure OpenAI costs via Cost Management API."""
    if not all(
        [
            config.get("azure_tenant_id"),
            config.get("azure_client_id"),
            config.get("azure_client_secret"),
            config.get("azure_subscription_id"),
        ]
    ):
        return {
            "success": False,
            "error": "Please configure Azure credentials (tenant_id, client_id, client_secret, subscription_id)",
        }

    scope = f"/subscriptions/{config.get('azure_subscription_id')}"
    token_url = (
        f"https://login.microsoftonline.com/{config.get('azure_tenant_id')}/oauth2/v2.0/token"
    )
    data = {
        "client_id": config.get("azure_client_id"),
        "scope": "https://management.azure.com/.default",
        "client_secret": config.get("azure_client_secret"),
        "grant_type": "client_credentials",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Get token
            async with session.post(token_url, data=data) as token_resp:
                if token_resp.status != 200:
                    error_text = await token_resp.text()
                    return {
                        "success": False,
                        "error": f"Failed to get token: HTTP {token_resp.status}\n{error_text[:300]}...",
                    }
                token_json = await token_resp.json()
                access_token = token_json["access_token"]

            # Query cost with details
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }
            query_url = f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query?api-version=2025-03-01"
            body = {
                "type": "Usage",
                "timeframe": "MonthToDate",
                "dataset": {
                    "granularity": "None",
                    "aggregation": {
                        "totalCost": {"name": "PreTaxCost", "function": "Sum"}
                    },
                    "grouping": [
                        {"name": "MeterCategory", "type": "Dimension"},
                        {"name": "MeterSubCategory", "type": "Dimension"},
                        {"name": "ServiceName", "type": "Dimension"},
                        {"name": "ResourceType", "type": "Dimension"},
                    ],
                },
            }
            async with session.post(
                query_url, headers=headers, json=body
            ) as query_resp:
                if query_resp.status != 200:
                    error_text = await query_resp.text()
                    raise ValueError(
                        f"Azure query failed: {query_resp.status} {error_text}"
                    )
                result = await query_resp.json()
                properties = result.get("properties", {})
                columns = {
                    col["name"]: i
                    for i, col in enumerate(properties.get("columns", []))
                }
                rows = properties.get("rows", [])

                if not rows:
                    raise ValueError("No cost data for this period")

                # Indices
                cost_idx = columns.get("PreTaxCost")
                cat_idx = columns.get("MeterCategory")
                subcat_idx = columns.get("MeterSubCategory")
                currency_idx = columns.get("Currency", -1)

                total_cost = 0.0
                details = []
                for row in rows[:15]:
                    cost = abs(float(row[cost_idx]))
                    total_cost += cost

                    raw_label = row[subcat_idx] or row[cat_idx] or "Unknown"
                    model_name = clean_azure_name(raw_label)

                    details.append(
                        {
                            "model": model_name,
                            "cost": round(cost, 4),
                            "is_ai": "Models" in (row[cat_idx] or ""),
                        }
                    )
                details.sort(key=lambda x: x["cost"], reverse=True)
                currency = "USD"
                if (
                    currency_idx is not None
                    and currency_idx >= 0
                    and rows
                    and len(rows[0]) > currency_idx
                ):
                    currency = rows[0][currency_idx] or "USD"

        return {
            "success": True,
            "total_cost": round(total_cost, 2),
            "currency": currency,
            "models": details[:20],
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


async def query_openrouter_balance(config: AstrBotConfig) -> dict:
    """Query OpenRouter balance."""
    if not config.get("openrouter_api_key"):
        return {"success": False, "error": "Please configure OpenRouter API Key"}

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config.get('openrouter_api_key')}"}

            async with session.get(
                "https://openrouter.ai/api/v1/credits", headers=headers
            ) as resp:
                if resp.status != 200:
                    return {
                        "success": False,
                        "error": f"Query failed: HTTP {resp.status}",
                    }

                result = await resp.json()
                data = result.get("data", {})
                total_credits = data.get("total_credits", 0)
                total_used = data.get("total_usage", 0)
                remaining = total_credits - total_used

                return {
                    "success": True,
                    "remaining": remaining,
                    "total": total_credits,
                    "used": total_used,
                    "usage_percent": (
                        (total_used / total_credits * 100) if total_credits > 0 else 0
                    ),
                }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def query_google_ai_cost(config: "AstrBotConfig") -> dict:
    """Query Google AI / Gemini API costs, grouped by model with input/output token breakdown."""
    if not GOOGLE_CLOUD_AVAILABLE:
        return {
            "success": False,
            "error": "google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery",
        }

    if not config.get("google_project_id"):
        return {"success": False, "error": "Please configure google_project_id"}

    if not config.get("google_bq_table"):
        return {"success": False, "error": "Please configure google_bq_table"}

    try:
        # Initialize BigQuery client
        if config.get("google_service_account_json"):
            credentials = service_account.Credentials.from_service_account_file(
                Path(get_astrbot_plugin_data_path()) / "astrbot_plugin_aicost" / config.get("google_service_account_json")[0],  # Get the first file path
                scopes=["https://www.googleapis.com/auth/bigquery"],
            )
            client = bigquery.Client(
                credentials=credentials, project=config.get("google_project_id")
            )
        else:
            client = bigquery.Client(project=config.get("google_project_id"))

        # Query SQL - grouped by model and token type
        query = f"""
            SELECT
                CASE
                    WHEN LOWER(sku.description) LIKE '%gemini 2.5 flash native image generation%' THEN 'Nano Banana Pro'
                    WHEN LOWER(sku.description) LIKE '%gemini 3 pro native image generation%' THEN 'Nano Banana'
                    WHEN LOWER(sku.description) LIKE '%gemini 2.5 flash lite%' THEN 'Gemini 2.5 Flash Lite'
                    WHEN LOWER(sku.description) LIKE '%gemini 3.1 flash lite%' THEN 'Gemini 3.1 Flash Lite'
                    WHEN LOWER(sku.description) LIKE '%gemini 2.5 flash%' THEN 'Gemini 2.5 Flash'
                    WHEN LOWER(sku.description) LIKE '%gemini 3 pro%' THEN 'Gemini 3 Pro'
                    WHEN LOWER(sku.description) LIKE '%gemini 3.0 pro%' THEN 'Gemini 3 Pro'
                    WHEN LOWER(sku.description) LIKE '%gemini 3.1 pro%' THEN 'Gemini 3.1 Pro'
                    WHEN LOWER(sku.description) LIKE '%gemini 3 flash%' THEN 'Gemini 3 Flash'
                    WHEN LOWER(sku.description) LIKE '%gemini-embedding-2%' THEN 'Gemini Embedding 2'
                    WHEN LOWER(sku.description) LIKE '%gemini-embedding%' THEN 'Gemini Embedding'
                    ELSE 'Other AI Services'
                END as model_name,
                CASE
                    WHEN LOWER(sku.description) LIKE '%input%'
                        OR LOWER(sku.description) LIKE '%prompt%'
                        OR LOWER(sku.description) LIKE '%request%'
                        THEN 'input'
                    WHEN LOWER(sku.description) LIKE '%output%'
                        OR LOWER(sku.description) LIKE '%response%'
                        OR LOWER(sku.description) LIKE '%candidate%'
                        OR LOWER(sku.description) LIKE '%generation%'
                        THEN 'output'
                    ELSE 'other'
                END as token_type,
                SUM(cost) as total_cost,
                SUM(usage.amount) as total_usage,
                usage.unit,
                currency
            FROM `{config.get('google_bq_table')}`
            WHERE
                (
                    service.description LIKE '%Generative Language API%'
                    OR service.description LIKE '%Vertex AI%'
                    OR LOWER(sku.description) LIKE '%gemini%'
                    OR LOWER(sku.description) LIKE '%palm%'
                )
                AND usage_start_time >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH)
                AND cost > 0
            GROUP BY
                model_name,
                token_type,
                usage.unit,
                currency
            ORDER BY total_cost DESC
        """

        loop = asyncio.get_event_loop()
        query_job = await loop.run_in_executor(None, client.query, query)
        results = await loop.run_in_executor(None, lambda: list(query_job.result()))

        # Organize data: aggregate by model
        models_dict: dict = {}
        total_cost = 0.0
        currency = "USD"

        for row in results:
            model_name = row.model_name
            token_type = row.token_type
            cost = float(row.total_cost)
            # Handle units: Google often bills per 1000 units
            usage_amount = float(row.total_usage)
            actual_tokens = usage_amount
            if row.unit and "1000" in row.unit:
                actual_tokens = usage_amount * 1000

            total_cost += cost
            currency = row.currency or "USD"

            if model_name not in models_dict:
                models_dict[model_name] = {
                    "model": model_name,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "input_cost": 0.0,
                    "output_cost": 0.0,
                    "other_cost": 0.0,
                    "total_cost": 0.0,
                }

            m = models_dict[model_name]
            m["total_cost"] += cost

            if token_type == "input":
                m["input_tokens"] += actual_tokens
                m["input_cost"] += cost
            elif token_type == "output":
                m["output_tokens"] += actual_tokens
                m["output_cost"] += cost
            else:
                m["other_cost"] += cost

        # Convert to list and sort
        models = list(models_dict.values())
        models.sort(key=lambda x: x["total_cost"], reverse=True)

        if not models:
            return {
                "success": True,
                "total_cost": 0.0,
                "currency": currency,
                "models": [],
                "warning": "No usage records this month (data has 24-48 hour delay)",
            }

        return {
            "success": True,
            "total_cost": total_cost,
            "currency": currency,
            "models": models,
            "warning": "BigQuery data has 24-48 hour delay",
        }

    except Exception as e:
        error_msg = str(e)

        if "404" in error_msg or "not found" in error_msg.lower():
            error_msg = f"Table not found: {config.google_bq_table}"
        elif "403" in error_msg or "permission" in error_msg.lower():
            error_msg = (
                "Permission denied, need BigQuery Data Viewer and Job User permissions"
            )
        elif "credentials" in error_msg.lower():
            error_msg = (
                "Credential error, check google_service_account_json configuration"
            )

        return {"success": False, "error": error_msg}


async def query_xai_cost(config: "AstrBotConfig") -> dict:
    """Query xAI billing info and balance."""
    if not config.get("xai_api_key") or not config.get("xai_team_id"):
        return {
            "success": False,
            "error": "Please configure xAI API Key and Team ID",
        }

    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config.get('xai_api_key')}"}
            base_url = (
                f"https://management-api.x.ai/v1/billing/teams/{config.get('xai_team_id')}"
            )

            # 1. Query balance (Prepaid Balance)
            async with session.get(
                f"{base_url}/prepaid/balance", headers=headers
            ) as resp:
                if resp.status != 200:
                    return {
                        "success": False,
                        "error": f"xAI balance query failed: HTTP {resp.status}",
                    }
                balance_data = await resp.json()
                balance_cents = balance_data.get("balance", 0)
                balance_usd = balance_cents / 100.0

            # 2. Query historical usage
            now = datetime.now(timezone.utc)
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            def fmt(dt: datetime) -> str:
                return dt.strftime("%Y-%m-%d %H:%M:%S")

            usage_payload = {
                "analyticsRequest": {
                    "timeRange": {
                        "startTime": fmt(start),
                        "endTime": fmt(now),
                        "timezone": "Etc/GMT",
                    },
                    "timeUnit": "TIME_UNIT_MONTH",
                    "values": [{"name": "usd", "aggregation": "AGGREGATION_SUM"}],
                    "groupBy": ["description"],
                }
            }
            async with session.post(
                f"{base_url}/usage", headers=headers, json=usage_payload
            ) as resp:
                if resp.status != 200:
                    # If usage query fails, return balance at least
                    return {
                        "success": True,
                        "balance": balance_usd,
                        "total_cost": 0.0,
                        "models": [],
                        "warning": f"Usage data fetch failed: HTTP {resp.status}",
                    }

                usage_data = await resp.json()
                models = []
                total_cost = 0.0

                time_series = usage_data.get("timeSeries", [])
                for ts in time_series:
                    model_name = ts.get("groupLabels", ["Unknown"])[0]
                    model_cost_usd = sum(
                        item.get("values", [])[0] for item in ts.get("dataPoints", [])
                    )
                    total_cost += model_cost_usd

                    if model_cost_usd > 0:
                        models.append(
                            {
                                "model": model_name,
                                "cost": round(model_cost_usd, 4),
                            }
                        )

                models.sort(key=lambda x: x["cost"], reverse=True)

                return {
                    "success": True,
                    "balance": balance_usd,
                    "total_cost": round(total_cost, 2),
                    "models": models,
                }

    except Exception as e:
        return {"success": False, "error": str(e)}
