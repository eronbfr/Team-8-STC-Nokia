"""
Bot de trading principal.
Conecta na Binance, coleta dados de mercado, analisa e executa trades.
"""

import logging
import time
from datetime import datetime, timezone

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

from .config import TradingConfig
from .risk_manager import RiskManager
from .strategy import Signal, TradingStrategy

logger = logging.getLogger(__name__)


class BinanceTrader:
    """
    Bot de trading automatizado para Bitcoin na Binance.
    Opera no par BTCBRL visando lucro mínimo de R$1.000 por trade.
    """

    def __init__(self, config: TradingConfig | None = None):
        self.config = config or TradingConfig()
        self.strategy = TradingStrategy(self.config)
        self.risk_manager = RiskManager(self.config)
        self.client: Client | None = None
        self.total_pnl = 0.0
        self.trade_count = 0
        self.win_count = 0

    def connect(self):
        """Conecta à API da Binance."""
        if not self.config.validate():
            raise ValueError("Configuração inválida. Verifique as variáveis de ambiente.")

        logger.info("Conectando à Binance...")
        self.client = Client(self.config.api_key, self.config.api_secret)

        # Testa a conexão
        try:
            server_time = self.client.get_server_time()
            logger.info(
                "Conectado à Binance. Server time: %s",
                datetime.fromtimestamp(
                    server_time["serverTime"] / 1000, tz=timezone.utc
                ),
            )
        except BinanceAPIException as e:
            raise ConnectionError(f"Falha ao conectar na Binance: {e}") from e

    def get_candles(self, interval: str, limit: int | None = None) -> pd.DataFrame:
        """Obtém candles (klines) da Binance e retorna como DataFrame."""
        if self.client is None:
            raise RuntimeError("Cliente não conectado. Chame connect() primeiro.")

        limit = limit or self.config.candle_limit
        klines = self.client.get_klines(
            symbol=self.config.symbol, interval=interval, limit=limit
        )

        df = pd.DataFrame(
            klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        return df

    def get_balance(self, asset: str) -> float:
        """Retorna o saldo disponível de um ativo."""
        if self.client is None:
            raise RuntimeError("Cliente não conectado.")

        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance["free"]) if balance else 0.0
        except BinanceAPIException as e:
            logger.error("Erro ao obter saldo de %s: %s", asset, e)
            return 0.0

    def get_current_price(self) -> float:
        """Retorna o preço atual do par de trading."""
        if self.client is None:
            raise RuntimeError("Cliente não conectado.")

        ticker = self.client.get_symbol_ticker(symbol=self.config.symbol)
        return float(ticker["price"])

    def execute_buy(self, quantity_btc: float) -> dict | None:
        """Executa uma ordem de compra."""
        if self.config.dry_run:
            price = self.get_current_price()
            logger.info(
                "[DRY RUN] COMPRA: %.8f BTC @ R$%.2f (total: R$%.2f)",
                quantity_btc,
                price,
                quantity_btc * price,
            )
            return {
                "symbol": self.config.symbol,
                "side": "BUY",
                "quantity": quantity_btc,
                "price": price,
                "status": "DRY_RUN",
            }

        try:
            order = self.client.order_market_buy(
                symbol=self.config.symbol, quantity=f"{quantity_btc:.8f}"
            )
            logger.info("Ordem de COMPRA executada: %s", order)
            return order
        except BinanceAPIException as e:
            logger.error("Erro ao executar compra: %s", e)
            return None

    def execute_sell(self, quantity_btc: float) -> dict | None:
        """Executa uma ordem de venda."""
        if self.config.dry_run:
            price = self.get_current_price()
            logger.info(
                "[DRY RUN] VENDA: %.8f BTC @ R$%.2f (total: R$%.2f)",
                quantity_btc,
                price,
                quantity_btc * price,
            )
            return {
                "symbol": self.config.symbol,
                "side": "SELL",
                "quantity": quantity_btc,
                "price": price,
                "status": "DRY_RUN",
            }

        try:
            order = self.client.order_market_sell(
                symbol=self.config.symbol, quantity=f"{quantity_btc:.8f}"
            )
            logger.info("Ordem de VENDA executada: %s", order)
            return order
        except BinanceAPIException as e:
            logger.error("Erro ao executar venda: %s", e)
            return None

    def run_cycle(self):
        """
        Executa um ciclo de análise e decisão.
        Este é o coração do bot.
        """
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        logger.info("═" * 60)
        logger.info("Ciclo de análise - %s", now)
        logger.info("═" * 60)

        # 1. Coleta dados
        try:
            df = self.get_candles(self.config.analysis_interval)
            df_trend = self.get_candles(self.config.trend_interval, limit=50)
            current_price = self.get_current_price()
        except Exception as e:
            logger.error("Erro ao coletar dados: %s", e)
            return

        # 2. Analisa tendência geral
        trend = self.strategy.get_trend(df_trend)
        logger.info("Tendência geral (1h): %s", trend)

        # 3. Se estiver em posição, verifica saída
        if self.risk_manager.in_position:
            self._check_exit(current_price, df)
            return

        # 4. Se não estiver em posição, verifica entrada
        self._check_entry(current_price, df, trend)

    def _check_entry(self, current_price: float, df: pd.DataFrame, trend: str):
        """Verifica se deve abrir uma nova posição."""
        signal, confidence, details = self.strategy.analyze(df)

        logger.info("Sinal: %s | Confiança: %.2f", signal.value, confidence)
        for key, value in details.items():
            logger.info("  %s: %s", key, value)

        if signal != Signal.BUY:
            logger.info("Sem sinal de compra. Aguardando...")
            return

        # Verifica se a tendência confirma
        if trend == "BAIXA":
            logger.info("Tendência de baixa no timeframe maior. Ignorando sinal de compra.")
            return

        # Calcula posição
        balance_brl = self.get_balance(self.config.quote_asset)
        logger.info("Saldo disponível: R$%.2f", balance_brl)

        atr = df["atr"].iloc[-1] if "atr" in df.columns else current_price * 0.02

        if pd.isna(atr):
            atr = current_price * 0.02

        position_size = self.risk_manager.calculate_position_size(
            current_price, balance_brl, atr
        )

        if position_size <= 0:
            logger.info("Posição calculada é zero. Saldo insuficiente.")
            return

        # Verifica lucro potencial
        potential_profit = position_size * current_price * self.config.take_profit_pct
        if potential_profit < self.config.min_profit_brl:
            logger.warning(
                "Lucro potencial R$%.2f < meta R$%.2f. Aumentando posição ou aguardando.",
                potential_profit,
                self.config.min_profit_brl,
            )

        # Executa compra
        order = self.execute_buy(position_size)
        if order:
            exec_price = float(order.get("price", current_price))
            self.risk_manager.enter_position(exec_price, position_size)

            stop_loss = self.risk_manager.calculate_stop_loss(exec_price, atr)
            take_profit = self.risk_manager.calculate_take_profit(
                exec_price, confidence, atr
            )

            logger.info(
                "Posição aberta: %.8f BTC @ R$%.2f | "
                "SL: R$%.2f | TP: R$%.2f",
                position_size,
                exec_price,
                stop_loss,
                take_profit,
            )

    def _check_exit(self, current_price: float, df: pd.DataFrame):
        """Verifica se deve fechar a posição atual."""
        from .indicators import build_indicators

        df = build_indicators(df, self.config)
        atr = df["atr"].iloc[-1] if "atr" in df.columns else current_price * 0.02

        if pd.isna(atr):
            atr = current_price * 0.02

        stop_loss = self.risk_manager.calculate_stop_loss(
            self.risk_manager.entry_price, atr
        )
        take_profit = self.risk_manager.calculate_take_profit(
            self.risk_manager.entry_price, 0.5, atr
        )

        should_exit, reason = self.risk_manager.should_exit(
            current_price, stop_loss, take_profit
        )

        # Também verifica sinal de venda da estratégia
        if not should_exit:
            signal, _, _ = self.strategy.analyze(df)
            if signal == Signal.SELL:
                # Só vende por sinal se estiver no lucro
                if current_price > self.risk_manager.entry_price:
                    should_exit = True
                    reason = "Sinal de VENDA com lucro"

        if should_exit:
            entry = self.risk_manager.entry_price
            size = self.risk_manager.position_size

            order = self.execute_sell(size)
            if order:
                exit_price = float(order.get("price", current_price))
                pnl = self.risk_manager.exit_position(exit_price)

                self.total_pnl += pnl
                self.trade_count += 1
                if pnl > 0:
                    self.win_count += 1

                summary = self.risk_manager.format_trade_summary(
                    entry, exit_price, size, reason
                )
                logger.info("\n%s", summary)
                self._log_stats()
        else:
            unrealized = self.risk_manager.position_size * (
                current_price - self.risk_manager.entry_price
            )
            logger.info(
                "Em posição | Preço: R$%.2f | Entrada: R$%.2f | "
                "P&L não realizado: R$%.2f | SL: R$%.2f | TP: R$%.2f",
                current_price,
                self.risk_manager.entry_price,
                unrealized,
                stop_loss,
                take_profit,
            )

    def _log_stats(self):
        """Loga estatísticas gerais."""
        win_rate = (self.win_count / self.trade_count * 100) if self.trade_count > 0 else 0
        logger.info(
            "📊 Estatísticas | Trades: %d | Win rate: %.1f%% | P&L total: R$%.2f",
            self.trade_count,
            win_rate,
            self.total_pnl,
        )

    def run(self):
        """
        Loop principal do bot.
        Executa ciclos de análise continuamente.
        """
        self.connect()

        logger.info("=" * 60)
        logger.info("🤖 Bot de Trading Bitcoin iniciado")
        logger.info("   Par: %s", self.config.symbol)
        logger.info("   Meta por trade: R$%.2f", self.config.min_profit_brl)
        logger.info("   Stop-loss: %.2f%%", self.config.stop_loss_pct * 100)
        logger.info("   Take-profit: %.2f%%", self.config.take_profit_pct * 100)
        logger.info("   Trailing stop: %.2f%%", self.config.trailing_stop_pct * 100)
        logger.info("   Intervalo análise: %s", self.config.analysis_interval)
        logger.info("   Modo: %s", "DRY RUN (simulação)" if self.config.dry_run else "LIVE")
        logger.info("=" * 60)

        while True:
            try:
                self.run_cycle()
            except KeyboardInterrupt:
                logger.info("Bot interrompido pelo usuário.")
                break
            except Exception as e:
                logger.error("Erro no ciclo: %s", e, exc_info=True)

            logger.info(
                "Próximo ciclo em %d segundos...",
                self.config.check_interval_seconds,
            )
            time.sleep(self.config.check_interval_seconds)

        self._log_stats()
        logger.info("Bot encerrado.")
