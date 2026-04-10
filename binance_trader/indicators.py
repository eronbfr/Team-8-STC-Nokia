"""
Indicadores técnicos para análise de mercado.
Implementa RSI, MACD, Bollinger Bands, EMA e ATR.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Calcula a Média Móvel Exponencial (EMA)."""
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Calcula a Média Móvel Simples (SMA)."""
    return series.rolling(window=period).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calcula o Índice de Força Relativa (RSI).
    RSI < 30 → sobrevendido (possível compra)
    RSI > 70 → sobrecomprado (possível venda)
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula MACD, linha de sinal e histograma.
    Cruzamento MACD > Sinal → sinal de compra
    Cruzamento MACD < Sinal → sinal de venda
    """
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calcula as Bandas de Bollinger.
    Preço próximo da banda inferior → possível compra
    Preço próximo da banda superior → possível venda
    """
    sma = compute_sma(close, period)
    std = close.rolling(window=period).std()
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band, sma, lower_band


def compute_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """
    Calcula o Average True Range (ATR).
    Usado para definir stop-loss dinâmico baseado em volatilidade.
    """
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


def compute_volume_sma(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calcula a SMA do volume para confirmar sinais."""
    return compute_sma(volume, period)


def build_indicators(df: pd.DataFrame, config) -> pd.DataFrame:
    """
    Adiciona todos os indicadores técnicos ao DataFrame de candles.
    Espera colunas: open, high, low, close, volume.
    """
    df = df.copy()

    # EMA
    df["ema_fast"] = compute_ema(df["close"], config.ema_fast)
    df["ema_slow"] = compute_ema(df["close"], config.ema_slow)

    # RSI
    df["rsi"] = compute_rsi(df["close"], config.rsi_period)

    # MACD
    df["macd"], df["macd_signal"], df["macd_hist"] = compute_macd(
        df["close"], config.macd_fast, config.macd_slow, config.macd_signal
    )

    # Bollinger Bands
    df["bb_upper"], df["bb_middle"], df["bb_lower"] = compute_bollinger_bands(
        df["close"], config.bb_period, config.bb_std
    )

    # ATR para stop-loss dinâmico
    df["atr"] = compute_atr(df["high"], df["low"], df["close"])

    # Volume médio
    df["vol_sma"] = compute_volume_sma(df["volume"])

    return df
