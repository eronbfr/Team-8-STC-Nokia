"""
Estratégia de trading baseada em múltiplos indicadores técnicos.
Combina RSI, MACD, Bollinger Bands e EMA para gerar sinais de compra/venda.
Utiliza sistema de pontuação para aumentar a confiança dos sinais.
"""

import logging
from enum import Enum

import pandas as pd

from .indicators import build_indicators

logger = logging.getLogger(__name__)


class Signal(Enum):
    """Sinais de trading."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradingStrategy:
    """
    Estratégia multi-indicador com sistema de pontuação.
    Cada indicador contribui com uma pontuação.
    A decisão final depende da pontuação agregada.
    """

    # Limiar mínimo de pontos para gerar sinal
    BUY_THRESHOLD = 3
    SELL_THRESHOLD = -3

    def __init__(self, config):
        self.config = config

    def analyze(self, df: pd.DataFrame) -> tuple[Signal, float, dict]:
        """
        Analisa os candles e retorna (sinal, confiança, detalhes).
        confiança: 0.0 a 1.0
        detalhes: dicionário com scores individuais
        """
        df = build_indicators(df, self.config)

        if len(df) < 2:
            return Signal.HOLD, 0.0, {"reason": "Dados insuficientes"}

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        score = 0
        details = {}

        # ── 1. RSI ──
        rsi = latest["rsi"]
        if pd.notna(rsi):
            if rsi < self.config.rsi_oversold:
                score += 2
                details["rsi"] = f"Sobrevendido ({rsi:.1f}) → +2"
            elif rsi < 40:
                score += 1
                details["rsi"] = f"Baixo ({rsi:.1f}) → +1"
            elif rsi > self.config.rsi_overbought:
                score -= 2
                details["rsi"] = f"Sobrecomprado ({rsi:.1f}) → -2"
            elif rsi > 60:
                score -= 1
                details["rsi"] = f"Alto ({rsi:.1f}) → -1"
            else:
                details["rsi"] = f"Neutro ({rsi:.1f}) → 0"

        # ── 2. MACD crossover ──
        if pd.notna(latest["macd"]) and pd.notna(prev["macd"]):
            macd_cross_up = (
                prev["macd"] <= prev["macd_signal"]
                and latest["macd"] > latest["macd_signal"]
            )
            macd_cross_down = (
                prev["macd"] >= prev["macd_signal"]
                and latest["macd"] < latest["macd_signal"]
            )

            if macd_cross_up:
                score += 2
                details["macd"] = "Cruzamento altista → +2"
            elif macd_cross_down:
                score -= 2
                details["macd"] = "Cruzamento baixista → -2"
            elif latest["macd_hist"] > 0:
                score += 1
                details["macd"] = f"Histograma positivo ({latest['macd_hist']:.2f}) → +1"
            else:
                score -= 1
                details["macd"] = f"Histograma negativo ({latest['macd_hist']:.2f}) → -1"

        # ── 3. EMA crossover ──
        if pd.notna(latest["ema_fast"]) and pd.notna(prev["ema_fast"]):
            ema_cross_up = (
                prev["ema_fast"] <= prev["ema_slow"]
                and latest["ema_fast"] > latest["ema_slow"]
            )
            ema_cross_down = (
                prev["ema_fast"] >= prev["ema_slow"]
                and latest["ema_fast"] < latest["ema_slow"]
            )

            if ema_cross_up:
                score += 2
                details["ema"] = "Cruzamento altista → +2"
            elif ema_cross_down:
                score -= 2
                details["ema"] = "Cruzamento baixista → -2"
            elif latest["ema_fast"] > latest["ema_slow"]:
                score += 1
                details["ema"] = "Tendência de alta → +1"
            else:
                score -= 1
                details["ema"] = "Tendência de baixa → -1"

        # ── 4. Bollinger Bands ──
        if pd.notna(latest["bb_lower"]):
            close = latest["close"]
            bb_width = latest["bb_upper"] - latest["bb_lower"]
            if bb_width > 0:
                bb_position = (close - latest["bb_lower"]) / bb_width
                if bb_position < 0.1:
                    score += 2
                    details["bb"] = f"Próximo da banda inferior ({bb_position:.2f}) → +2"
                elif bb_position < 0.3:
                    score += 1
                    details["bb"] = f"Região inferior ({bb_position:.2f}) → +1"
                elif bb_position > 0.9:
                    score -= 2
                    details["bb"] = f"Próximo da banda superior ({bb_position:.2f}) → -2"
                elif bb_position > 0.7:
                    score -= 1
                    details["bb"] = f"Região superior ({bb_position:.2f}) → -1"
                else:
                    details["bb"] = f"Região central ({bb_position:.2f}) → 0"

        # ── 5. Volume ──
        if pd.notna(latest["vol_sma"]) and latest["vol_sma"] > 0:
            vol_ratio = latest["volume"] / latest["vol_sma"]
            if vol_ratio > 1.5:
                # Volume alto confirma a tendência
                if score > 0:
                    score += 1
                    details["volume"] = f"Volume alto confirmando ({vol_ratio:.1f}x) → +1"
                elif score < 0:
                    score -= 1
                    details["volume"] = f"Volume alto confirmando ({vol_ratio:.1f}x) → -1"
                else:
                    details["volume"] = f"Volume alto sem direção ({vol_ratio:.1f}x) → 0"
            else:
                details["volume"] = f"Volume normal ({vol_ratio:.1f}x) → 0"

        # ── Decisão final ──
        max_score = 9  # pontuação máxima teórica
        confidence = min(abs(score) / max_score, 1.0)
        details["score_total"] = score

        if score >= self.BUY_THRESHOLD:
            signal = Signal.BUY
        elif score <= self.SELL_THRESHOLD:
            signal = Signal.SELL
        else:
            signal = Signal.HOLD

        logger.info(
            "Análise: sinal=%s, score=%d, confiança=%.2f",
            signal.value,
            score,
            confidence,
        )
        return signal, confidence, details

    def get_trend(self, df_trend: pd.DataFrame) -> str:
        """
        Determina a tendência geral usando timeframe maior.
        Retorna 'ALTA', 'BAIXA' ou 'LATERAL'.
        """
        df_trend = build_indicators(df_trend, self.config)

        if len(df_trend) < 2:
            return "LATERAL"

        latest = df_trend.iloc[-1]

        if pd.notna(latest["ema_fast"]) and pd.notna(latest["ema_slow"]):
            if latest["ema_fast"] > latest["ema_slow"] * 1.005:
                return "ALTA"
            elif latest["ema_fast"] < latest["ema_slow"] * 0.995:
                return "BAIXA"

        return "LATERAL"
