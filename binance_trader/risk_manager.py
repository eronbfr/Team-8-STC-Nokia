"""
Gerenciador de risco para o bot de trading.
Calcula tamanho de posição, stop-loss, take-profit e trailing stop.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Gerencia risco calculando:
    - Tamanho de posição para atingir lucro mínimo de R$1.000
    - Stop-loss baseado em ATR (volatilidade)
    - Take-profit dinâmico
    - Trailing stop para maximizar ganhos
    """

    def __init__(self, config):
        self.config = config
        self.trailing_high = 0.0
        self.in_position = False
        self.entry_price = 0.0
        self.position_size = 0.0

    def calculate_position_size(
        self, current_price: float, balance_brl: float, atr: float
    ) -> float:
        """
        Calcula o tamanho da posição em BTC.
        Garante que o lucro potencial atinja pelo menos R$1.000.
        Nunca excede MAX_POSITION_PCT do saldo.
        """
        if current_price <= 0 or balance_brl <= 0:
            return 0.0

        max_invest = balance_brl * self.config.max_position_pct
        min_invest_for_target = self.config.min_profit_brl / self.config.take_profit_pct

        invest_brl = min(max(min_invest_for_target, 0), max_invest)

        if invest_brl < self.config.min_profit_brl:
            logger.warning(
                "Saldo insuficiente para atingir meta de R$%.2f. "
                "Investimento possível: R$%.2f",
                self.config.min_profit_brl,
                invest_brl,
            )

        position_btc = invest_brl / current_price

        logger.info(
            "Posição calculada: %.8f BTC (R$%.2f) | "
            "Meta lucro: R$%.2f | ATR: %.2f",
            position_btc,
            invest_brl,
            invest_brl * self.config.take_profit_pct,
            atr,
        )

        return position_btc

    def calculate_stop_loss(self, entry_price: float, atr: float) -> float:
        """
        Calcula o preço de stop-loss.
        Usa o maior entre:
        - Stop percentual fixo (config.stop_loss_pct)
        - Stop baseado em 2x ATR
        Isso garante proteção mesmo em mercados voláteis.
        """
        pct_stop = entry_price * (1 - self.config.stop_loss_pct)
        atr_stop = entry_price - (2.0 * atr)

        # Usa o stop mais conservador (mais próximo do preço)
        stop_price = max(pct_stop, atr_stop)

        logger.info(
            "Stop-loss: R$%.2f (pct: R$%.2f, ATR: R$%.2f) | Entrada: R$%.2f",
            stop_price,
            pct_stop,
            atr_stop,
            entry_price,
        )
        return stop_price

    def calculate_take_profit(
        self, entry_price: float, confidence: float, atr: float
    ) -> float:
        """
        Calcula o preço de take-profit.
        Ajusta com base na confiança do sinal:
        - Alta confiança → take-profit mais agressivo
        - Baixa confiança → take-profit conservador
        """
        base_tp_pct = self.config.take_profit_pct
        adjusted_tp_pct = base_tp_pct * (1 + confidence * 0.5)

        # Limita a 10%
        adjusted_tp_pct = min(adjusted_tp_pct, 0.10)

        tp_price = entry_price * (1 + adjusted_tp_pct)

        logger.info(
            "Take-profit: R$%.2f (%.2f%%) | Confiança: %.2f | Entrada: R$%.2f",
            tp_price,
            adjusted_tp_pct * 100,
            confidence,
            entry_price,
        )
        return tp_price

    def update_trailing_stop(self, current_price: float) -> float | None:
        """
        Atualiza o trailing stop.
        Retorna o preço do trailing stop, ou None se não ativo.
        Só ativa após o preço superar o entry + trailing_stop_pct.
        """
        if not self.in_position:
            return None

        if current_price > self.trailing_high:
            self.trailing_high = current_price

        trailing_stop_price = self.trailing_high * (
            1 - self.config.trailing_stop_pct
        )

        # Só ativa o trailing stop se já estiver no lucro
        if trailing_stop_price > self.entry_price:
            return trailing_stop_price

        return None

    def should_exit(
        self,
        current_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> tuple[bool, str]:
        """
        Verifica se deve sair da posição.
        Retorna (deve_sair, motivo).
        """
        if not self.in_position:
            return False, ""

        # Verifica stop-loss
        if current_price <= stop_loss:
            loss_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            return True, f"STOP-LOSS atingido (perda de {loss_pct:.2f}%)"

        # Verifica take-profit
        if current_price >= take_profit:
            profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            return True, f"TAKE-PROFIT atingido (lucro de {profit_pct:.2f}%)"

        # Verifica trailing stop
        trailing = self.update_trailing_stop(current_price)
        if trailing is not None and current_price <= trailing:
            profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            return True, f"TRAILING STOP atingido (lucro de {profit_pct:.2f}%)"

        return False, ""

    def enter_position(self, entry_price: float, position_size: float):
        """Registra a entrada em uma posição."""
        self.in_position = True
        self.entry_price = entry_price
        self.position_size = position_size
        self.trailing_high = entry_price
        logger.info(
            "Entrou em posição: %.8f BTC @ R$%.2f", position_size, entry_price
        )

    def exit_position(self, exit_price: float) -> float:
        """
        Registra a saída de uma posição.
        Retorna o lucro/prejuízo em BRL.
        """
        profit_brl = self.position_size * (exit_price - self.entry_price)
        logger.info(
            "Saiu da posição: %.8f BTC @ R$%.2f | P&L: R$%.2f",
            self.position_size,
            exit_price,
            profit_brl,
        )
        self.in_position = False
        self.entry_price = 0.0
        self.position_size = 0.0
        self.trailing_high = 0.0
        return profit_brl

    def format_trade_summary(
        self,
        entry_price: float,
        exit_price: float,
        position_size: float,
        reason: str,
    ) -> str:
        """Formata um resumo legível do trade."""
        profit_brl = position_size * (exit_price - entry_price)
        profit_pct = ((exit_price - entry_price) / entry_price) * 100
        emoji = "✅" if profit_brl > 0 else "❌"

        return (
            f"{emoji} Trade finalizado\n"
            f"   Motivo: {reason}\n"
            f"   Entrada: R${entry_price:,.2f}\n"
            f"   Saída:   R${exit_price:,.2f}\n"
            f"   Tamanho: {position_size:.8f} BTC\n"
            f"   P&L:     R${profit_brl:,.2f} ({profit_pct:+.2f}%)\n"
        )
