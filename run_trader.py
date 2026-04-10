#!/usr/bin/env python3
"""
Script principal para executar o bot de trading Bitcoin na Binance.

Uso:
    # Modo simulação (padrão):
    python run_trader.py

    # Modo live (cuidado!):
    DRY_RUN=false python run_trader.py

Variáveis de ambiente necessárias:
    BINANCE_API_KEY     - Chave da API Binance
    BINANCE_API_SECRET  - Secret da API Binance

Variáveis opcionais:
    DRY_RUN             - true/false (padrão: true)
    MIN_PROFIT_BRL      - Meta de lucro mínimo por trade (padrão: 1000)
    STOP_LOSS_PCT       - Stop-loss percentual (padrão: 0.02 = 2%)
    TAKE_PROFIT_PCT     - Take-profit percentual (padrão: 0.04 = 4%)
    TRAILING_STOP_PCT   - Trailing stop percentual (padrão: 0.015 = 1.5%)
    MAX_POSITION_PCT    - Máximo do saldo por trade (padrão: 0.25 = 25%)
    CHECK_INTERVAL_SECONDS - Intervalo entre análises (padrão: 60)
"""

import logging
import sys

from binance_trader.config import TradingConfig
from binance_trader.trader import BinanceTrader


def setup_logging():
    """Configura o sistema de logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("trader.log", encoding="utf-8"),
        ],
    )


def main():
    """Ponto de entrada principal."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Inicializando bot de trading...")

    config = TradingConfig()

    if not config.validate():
        logger.error(
            "Configuração inválida. Defina BINANCE_API_KEY e BINANCE_API_SECRET."
        )
        sys.exit(1)

    if not config.dry_run:
        logger.warning("⚠️  MODO LIVE - Operações reais serão executadas!")
        logger.warning("⚠️  Pressione Ctrl+C nos próximos 10 segundos para cancelar...")
        import time

        try:
            time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Cancelado pelo usuário.")
            sys.exit(0)

    bot = BinanceTrader(config)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot encerrado pelo usuário.")
    except Exception as e:
        logger.error("Erro fatal: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
