"""
Configurações do bot de trading.
Todas as credenciais são lidas de variáveis de ambiente para segurança.
"""

import os
import logging

logger = logging.getLogger(__name__)


class TradingConfig:
    """Configuração central do bot de trading."""

    def __init__(self):
        # ── Credenciais Binance (NUNCA hardcode) ──
        self.api_key = os.environ.get("BINANCE_API_KEY", "")
        self.api_secret = os.environ.get("BINANCE_API_SECRET", "")

        # ── Par de trading ──
        self.symbol = os.environ.get("TRADING_SYMBOL", "BTCBRL")
        self.base_asset = "BTC"
        self.quote_asset = "BRL"

        # ── Metas financeiras ──
        self.min_profit_brl = float(os.environ.get("MIN_PROFIT_BRL", "1000.0"))
        self.max_position_pct = float(
            os.environ.get("MAX_POSITION_PCT", "0.25")
        )  # máx 25% do saldo por trade

        # ── Stop-loss / Take-profit (%) ──
        self.stop_loss_pct = float(os.environ.get("STOP_LOSS_PCT", "0.02"))  # 2%
        self.take_profit_pct = float(
            os.environ.get("TAKE_PROFIT_PCT", "0.04")
        )  # 4% (risk:reward 1:2)
        self.trailing_stop_pct = float(
            os.environ.get("TRAILING_STOP_PCT", "0.015")
        )  # trailing 1.5%

        # ── Indicadores técnicos ──
        self.rsi_period = int(os.environ.get("RSI_PERIOD", "14"))
        self.rsi_oversold = float(os.environ.get("RSI_OVERSOLD", "30"))
        self.rsi_overbought = float(os.environ.get("RSI_OVERBOUGHT", "70"))
        self.ema_fast = int(os.environ.get("EMA_FAST", "9"))
        self.ema_slow = int(os.environ.get("EMA_SLOW", "21"))
        self.macd_fast = int(os.environ.get("MACD_FAST", "12"))
        self.macd_slow = int(os.environ.get("MACD_SLOW", "26"))
        self.macd_signal = int(os.environ.get("MACD_SIGNAL", "9"))
        self.bb_period = int(os.environ.get("BB_PERIOD", "20"))
        self.bb_std = float(os.environ.get("BB_STD", "2.0"))

        # ── Timeframes ──
        self.analysis_interval = os.environ.get("ANALYSIS_INTERVAL", "15m")
        self.trend_interval = os.environ.get("TREND_INTERVAL", "1h")
        self.candle_limit = int(os.environ.get("CANDLE_LIMIT", "100"))

        # ── Controle do loop ──
        self.check_interval_seconds = int(
            os.environ.get("CHECK_INTERVAL_SECONDS", "60")
        )
        self.dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"

    def validate(self):
        """Valida se as configurações essenciais estão presentes."""
        errors = []
        if not self.api_key:
            errors.append("BINANCE_API_KEY não configurada")
        if not self.api_secret:
            errors.append("BINANCE_API_SECRET não configurada")
        if self.stop_loss_pct <= 0 or self.stop_loss_pct >= 1:
            errors.append("STOP_LOSS_PCT deve estar entre 0 e 1")
        if self.take_profit_pct <= 0 or self.take_profit_pct >= 1:
            errors.append("TAKE_PROFIT_PCT deve estar entre 0 e 1")
        if self.min_profit_brl <= 0:
            errors.append("MIN_PROFIT_BRL deve ser positivo")

        if errors:
            for err in errors:
                logger.error("Erro de configuração: %s", err)
            return False
        return True
