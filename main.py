"""
AI Cost Query Plugin for AstrBot.
Supports Azure OpenAI, OpenRouter, Google AI (BigQuery), and xAI cost queries.
"""

import asyncio
from datetime import datetime

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.message.components import Image, Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.api import AstrBotConfig
from .providers import (
    get_provider_specs,
)
from .report import generate_report_image


class Main(star.Star):
    """AI Cost Monitor Plugin."""

    def __init__(self, context: star.Context, config: AstrBotConfig) -> None:
        self.context = context
        self.config = config
        self._cron_job_id: str | None = None

    async def initialize(self) -> None:
        """Initialize the plugin and register cron job if enabled."""

        if self.config.get("enable_daily_report", False):
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
            if self.config.get("report_time"):
                parts = self.config.get("report_time","").split(":")
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

    async def _query_enabled_costs(self) -> list[dict]:
        """Query enabled provider costs in parallel."""
        enabled_specs = [
            spec for spec in get_provider_specs() if spec["enabled"](self.config)
        ]
        if not enabled_specs:
            raise RuntimeError("No provider modules are enabled in plugin config")

        results = await asyncio.gather(
            *(spec["query"](self.config) for spec in enabled_specs)
        )
        return [
            {
                "id": spec["id"],
                "name": spec["name"],
                "data": result,
            }
            for spec, result in zip(enabled_specs, results)
        ]

    async def _generate_report_image(self) -> bytes:
        """Generate the cost report as image bytes."""
        provider_cards = await self._query_enabled_costs()
        return generate_report_image(
            provider_cards, self.config.get("report_style", "midnight")
        )

    async def _send_daily_report(self) -> None:
        """Send the scheduled daily report to configured targets."""
        try:
            logger.info("Generating daily AI cost report...")
            img_bytes = await self._generate_report_image()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            logger.info(f"Daily AI cost report generated at {timestamp}")

            if not self.config.get("report_targets"):
                logger.warning(
                    "No report targets configured. Set 'report_targets' in config."
                )
                return

            platform_manager = self.context.platform_manager
            if not platform_manager or not platform_manager.platform_insts:
                logger.warning("No platform instances available for sending report")
                return
            
            image = Image.fromBytes(img_bytes)
            message_chain = MessageChain([image])
            for target in self.config.get("report_targets", []):
                target = target.strip()
                if not target:
                    continue
                session = MessageSession.from_str(target)
                try:
                    await self.context.send_message(session, message_chain)
                    logger.info(
                        f"Daily report sent to {target} via {session.platform_id}"
                    )
                    break
                except Exception as e:
                    logger.warning(
                        f"Failed to send report to {target} via {session.platform_id}: {e}"
                    )
                    continue
        except Exception as e:
            logger.exception(f"Failed to generate daily AI cost report: {e}")

    @filter.command("aicost")
    @filter.permission_type(filter.PermissionType.ADMIN)
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
