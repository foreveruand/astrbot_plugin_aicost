"""
AI Cost Query Plugin for AstrBot.
Supports Azure OpenAI, OpenRouter, Google AI (BigQuery), and xAI cost queries.
"""

import asyncio
from datetime import datetime

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.message.components import Image

from .config import AICostConfig
from .providers import (
    query_google_ai_cost,
    query_openrouter_balance,
    query_xai_cost,
)
from .report import generate_html_report, html_to_image


class Main(star.Star):
    """AI Cost Monitor Plugin."""

    def __init__(self, context: star.Context) -> None:
        self.context = context
        self.config = AICostConfig()
        self._cron_job_id: str | None = None

    async def initialize(self) -> None:
        """Initialize the plugin and register cron job if enabled."""
        cfg = self.context.get_config()
        plugin_config = cfg.get("astrbot_plugin_aicost", {})
        self.config = AICostConfig(**plugin_config)

        if self.config.enable_daily_report:
            await self._register_cron_job()
            logger.info("AI Cost daily report cron job registered")

    async def terminate(self) -> None:
        """Cleanup when plugin is disabled."""
        if self._cron_job_id:
            try:
                await self.context.cron_manager.delete_job(self._cron_job_id)
                logger.info("AI Cost cron job removed")
            except Exception as e:
                logger.warning(f"Failed to remove cron job: {e}")

    async def _register_cron_job(self) -> None:
        """Register the daily report cron job."""
        try:
            # Parse report time (default 08:00)
            hour, minute = 8, 0
            if self.config.report_time:
                parts = self.config.report_time.split(":")
                if len(parts) == 2:
                    hour = int(parts[0])
                    minute = int(parts[1])

            cron_expr = f"{minute} {hour} * * *"

            job = await self.context.cron_manager.add_basic_job(
                name="AI Cost Daily Report",
                cron_expression=cron_expr,
                timezone="Asia/Shanghai",
                handler=self._send_daily_report,
                description="Daily AI service cost report",
                enabled=True,
                persistent=False,
            )

            self._cron_job_id = job.job_id
            logger.info(f"Cron job registered with ID: {self._cron_job_id}")

        except Exception as e:
            logger.error(f"Failed to register cron job: {e}")

    async def _query_all_costs(self) -> tuple:
        """Query all provider costs in parallel."""
        return await asyncio.gather(
            query_openrouter_balance(self.config),
            query_google_ai_cost(self.config),
            query_xai_cost(self.config),
        )

    async def _generate_report_image(self) -> bytes:
        """Generate the cost report as image bytes."""
        openrouter_data, google_data, xai_data = await self._query_all_costs()
        html_content = generate_html_report(google_data, xai_data, openrouter_data)
        return await html_to_image(html_content)

    async def _send_daily_report(self) -> None:
        """Send the scheduled daily report."""
        try:
            logger.info("Generating daily AI cost report...")
            img_bytes = await self._generate_report_image()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"Daily AI cost report generated at {timestamp}")
            # Note: For scheduled reports, implement broadcasting
            # via context.send_message to specific sessions
        except Exception as e:
            logger.exception(f"Failed to generate daily AI cost report: {e}")

    @filter.command("aicost")
    async def aicost(self, event: AstrMessageEvent):
        """Query AI service costs and generate a report.

        Usage: /aicost
        """
        try:
            logger.info("Generating AI cost report...")
            img_bytes = await self._generate_report_image()

            # Send image using Image component
            image = Image.fromBytes(img_bytes)
            result = event.make_result()
            result.chain.append(image)
            await event.send(result)

            logger.info("AI cost report sent successfully")
        except Exception as e:
            logger.exception(f"Failed to generate AI cost report: {e}")
            await event.send(
                event.make_result().message(f"Failed to generate report: {e}")
            )
