import asyncio
import logging
import threading

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import Settings
from app.services.orchestrator_service import OrchestratorService


class TelegramBridge:
    def __init__(self, settings: Settings, orchestrator: OrchestratorService):
        self._settings = settings
        self._orchestrator = orchestrator
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._logger = logging.getLogger("orbitflow.runtime")

    def start(self) -> None:
        if not self._settings.telegram_bot_token:
            self._logger.info("[bold yellow]telegram[/bold yellow] disabled (no TELEGRAM_BOT_TOKEN configured).")
            return
        if self._thread and self._thread.is_alive():
            return
        self._logger.info("[bold blue]telegram[/bold blue] bridge starting in polling mode.")
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="telegram-bridge")
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._run_polling())
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"[bold red]telegram[/bold red] bridge crashed: {exc}")

    async def _run_polling(self) -> None:
        app = ApplicationBuilder().token(self._settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self._on_start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        try:
            while not self._stop_flag.is_set():
                await asyncio.sleep(0.5)
        finally:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Synapse Flow Telegram Agent is live. Send any message and I will route it to the configured agent."
        )

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None or update.message.text is None:
            return
        user_text = update.message.text.strip()
        response = await self._orchestrator.run_telegram_agent(user_text)
        await update.message.reply_text(response)
