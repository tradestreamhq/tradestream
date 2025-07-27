"""
Strategy Monitor API Service
Provides REST endpoints for strategy monitoring and visualization.
"""

import json
import logging
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import psycopg2
import psycopg2.extras
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from absl import flags
from absl import app as absl_app
from flask import Flask, request, jsonify
from flask_cors import CORS

# Flask configuration
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

FLAGS = flags.FLAGS

# Global database configuration
DB_CONFIG = {}


def decode_base64_parameters(base64_data: str) -> Dict:
    """Decode base64-encoded protobuf parameters."""
    try:
        # Decode base64 data
        protobuf_bytes = base64.b64decode(base64_data)

        # For now, return a simple representation
        # In a full implementation, you would parse the protobuf based on type_url
        return {
            "raw_base64": (
                base64_data[:50] + "..." if len(base64_data) > 50 else base64_data
            ),
            "decoded": True,
            "size_bytes": len(protobuf_bytes),
        }
    except Exception as e:
        return {"error": f"Failed to decode base64 parameters: {str(e)}"}


def decode_hex_parameters(hex_data: str, protobuf_type: str) -> Dict:
    """Decode hex-encoded protobuf parameters with readable names."""
    try:
        # Decode hex data
        protobuf_bytes = bytes.fromhex(hex_data)

        # Strategy parameter decoders
        if protobuf_type == "type.googleapis.com/strategies.SmaEmaCrossoverParameters":
            return decode_sma_ema_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.SmaRsiParameters":
            return decode_sma_rsi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.EmaMacdParameters":
            return decode_ema_macd(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.PivotParameters":
            return decode_pivot(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.AdxStochasticParameters":
            return decode_adx_stochastic(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.AroonMfiParameters":
            return decode_aroon_mfi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.IchimokuCloudParameters":
            return decode_ichimoku_cloud(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.ParabolicSarParameters":
            return decode_parabolic_sar(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.DoubleEmaCrossoverParameters"
        ):
            return decode_double_ema_crossover(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.TripleEmaCrossoverParameters"
        ):
            return decode_triple_ema_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.HeikenAshiParameters":
            return decode_heiken_ashi(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.LinearRegressionChannelsParameters"
        ):
            return decode_linear_regression_channels(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.VwapMeanReversionParameters"
        ):
            return decode_vwap_mean_reversion(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.BbandWRParameters":
            return decode_bband_wr(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.AtrCciParameters":
            return decode_atr_cci(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type == "type.googleapis.com/strategies.DonchianBreakoutParameters"
        ):
            return decode_donchian_breakout(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.VolatilityStopParameters":
            return decode_volatility_stop(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type == "type.googleapis.com/strategies.AtrTrailingStopParameters"
        ):
            return decode_atr_trailing_stop(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.MomentumSmaCrossoverParameters"
        ):
            return decode_momentum_sma_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.KstOscillatorParameters":
            return decode_kst_oscillator(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.StochasticRsiParameters":
            return decode_stochastic_rsi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.RviParameters":
            return decode_rvi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.MassIndexParameters":
            return decode_mass_index(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type == "type.googleapis.com/strategies.MomentumPinballParameters"
        ):
            return decode_momentum_pinball(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.VolumeWeightedMacdParameters"
        ):
            return decode_volume_weighted_macd(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.ObvEmaParameters":
            return decode_obv_ema(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.ChaikinOscillatorParameters"
        ):
            return decode_chaikin_oscillator(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.KlingerVolumeParameters":
            return decode_klinger_volume(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.VolumeBreakoutParameters":
            return decode_volume_breakout(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.PvtParameters":
            return decode_pvt(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.VptParameters":
            return decode_vpt(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.VolumeSpreadAnalysisParameters"
        ):
            return decode_volume_spread_analysis(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.TickVolumeAnalysisParameters"
        ):
            return decode_tick_volume_analysis(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.VolumeProfileDeviationsParameters"
        ):
            return decode_volume_profile_deviations(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.VolumeProfileParameters":
            return decode_volume_profile(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.StochasticEmaParameters":
            return decode_stochastic_ema(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.CmoMfiParameters":
            return decode_cmo_mfi(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type == "type.googleapis.com/strategies.RsiEmaCrossoverParameters"
        ):
            return decode_rsi_ema_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.TrixSignalLineParameters":
            return decode_trix_signal_line(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.CmfZeroLineParameters":
            return decode_cmf_zero_line(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.RainbowOscillatorParameters"
        ):
            return decode_rainbow_oscillator(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.PriceOscillatorSignalParameters"
        ):
            return decode_price_oscillator_signal(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.AwesomeOscillatorParameters"
        ):
            return decode_awesome_oscillator(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.DemaTemaCrossoverParameters"
        ):
            return decode_dema_tema_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.MacdCrossoverParameters":
            return decode_macd_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.VwapCrossoverParameters":
            return decode_vwap_crossover(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.RocMaCrossoverParameters":
            return decode_roc_ma_crossover(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.RegressionChannelParameters"
        ):
            return decode_regression_channel(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.FramaParameters":
            return decode_frama(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type == "type.googleapis.com/strategies.DoubleTopBottomParameters"
        ):
            return decode_double_top_bottom(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.FibonacciRetracementsParameters"
        ):
            return decode_fibonacci_retracements(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.PriceGapParameters":
            return decode_price_gap(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.RenkoChartParameters":
            return decode_renko_chart(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.RangeBarsParameters":
            return decode_range_bars(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.GannSwingParameters":
            return decode_gann_swing(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.SarMfiParameters":
            return decode_sar_mfi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.AdxDmiParameters":
            return decode_adx_dmi(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.ElderRayMAParameters":
            return decode_elder_ray_ma(protobuf_bytes, protobuf_type)
        elif protobuf_type == "type.googleapis.com/strategies.DpoCrossoverParameters":
            return decode_dpo_crossover(protobuf_bytes, protobuf_type)
        elif (
            protobuf_type
            == "type.googleapis.com/strategies.VariablePeriodEmaParameters"
        ):
            return decode_variable_period_ema(protobuf_bytes, protobuf_type)

        # Fallback for unknown types
        return {
            "raw_hex": hex_data[:50] + "..." if len(hex_data) > 50 else hex_data,
            "protobuf_type": protobuf_type,
            "decoded": True,
            "size_bytes": len(protobuf_bytes),
        }
    except Exception as e:
        return {"error": f"Failed to decode hex parameters: {str(e)}"}


# Individual strategy parameter decoders
def decode_sma_ema_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode SMA_EMA_CROSSOVER parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            sma_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            ema_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            return {
                "SMA Period": sma_period,
                "EMA Period": ema_period,
                "strategy_type": "SMA_EMA_CROSSOVER",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "SMA_EMA_CROSSOVER",
    }


def decode_sma_rsi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode SMA_RSI parameters."""
    try:
        if len(protobuf_bytes) >= 2:
            ma_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            rsi_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            overbought = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 70
            oversold = protobuf_bytes[7] if len(protobuf_bytes) > 7 else 30
            return {
                "Moving Average Period": ma_period,
                "RSI Period": rsi_period,
                "Overbought Threshold": overbought,
                "Oversold Threshold": oversold,
                "strategy_type": "SMA_RSI",
            }
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "SMA_RSI"}


def decode_ema_macd(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode EMA_MACD parameters."""
    try:
        if len(protobuf_bytes) >= 6:
            short_ema = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            long_ema = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            signal_period = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 0
            return {
                "Short EMA Period": short_ema,
                "Long EMA Period": long_ema,
                "Signal Period": signal_period,
                "strategy_type": "EMA_MACD",
            }
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "EMA_MACD"}


def decode_pivot(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode PIVOT parameters."""
    try:
        if len(protobuf_bytes) >= 2:
            period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            return {"Period": period, "strategy_type": "PIVOT"}
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "PIVOT"}


def decode_adx_stochastic(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode ADX_STOCHASTIC parameters."""
    try:
        if len(protobuf_bytes) >= 10:
            adx_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            stoch_k_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            stoch_d_period = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 0
            overbought = protobuf_bytes[7] if len(protobuf_bytes) > 7 else 80
            oversold = protobuf_bytes[9] if len(protobuf_bytes) > 9 else 20
            return {
                "ADX Period": adx_period,
                "Stochastic K Period": stoch_k_period,
                "Stochastic D Period": stoch_d_period,
                "Overbought Threshold": overbought,
                "Oversold Threshold": oversold,
                "strategy_type": "ADX_STOCHASTIC",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "ADX_STOCHASTIC",
    }


def decode_aroon_mfi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode AROON_MFI parameters."""
    try:
        if len(protobuf_bytes) >= 8:
            aroon_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            mfi_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            overbought = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 80
            oversold = protobuf_bytes[7] if len(protobuf_bytes) > 7 else 20
            return {
                "Aroon Period": aroon_period,
                "MFI Period": mfi_period,
                "Overbought Threshold": overbought,
                "Oversold Threshold": oversold,
                "strategy_type": "AROON_MFI",
            }
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "AROON_MFI"}


def decode_ichimoku_cloud(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode ICHIMOKU_CLOUD parameters."""
    try:
        if len(protobuf_bytes) >= 8:
            tenkan = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            kijun = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            senkou_b = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 0
            chikou = protobuf_bytes[7] if len(protobuf_bytes) > 7 else 0
            return {
                "Tenkan-sen Period": tenkan,
                "Kijun-sen Period": kijun,
                "Senkou Span B Period": senkou_b,
                "Chikou Span Period": chikou,
                "strategy_type": "ICHIMOKU_CLOUD",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "ICHIMOKU_CLOUD",
    }


def decode_parabolic_sar(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode PARABOLIC_SAR parameters."""
    try:
        if len(protobuf_bytes) >= 6:
            af_start = protobuf_bytes[1] / 100.0 if len(protobuf_bytes) > 1 else 0.02
            af_increment = (
                protobuf_bytes[3] / 100.0 if len(protobuf_bytes) > 3 else 0.02
            )
            af_max = protobuf_bytes[5] / 100.0 if len(protobuf_bytes) > 5 else 0.2
            return {
                "Acceleration Factor Start": f"{af_start:.2f}",
                "Acceleration Factor Increment": f"{af_increment:.2f}",
                "Acceleration Factor Max": f"{af_max:.2f}",
                "strategy_type": "PARABOLIC_SAR",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "PARABOLIC_SAR",
    }


def decode_double_ema_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode DOUBLE_EMA_CROSSOVER parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            short_ema = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            long_ema = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            return {
                "Short EMA Period": short_ema,
                "Long EMA Period": long_ema,
                "strategy_type": "DOUBLE_EMA_CROSSOVER",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "DOUBLE_EMA_CROSSOVER",
    }


def decode_triple_ema_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode TRIPLE_EMA_CROSSOVER parameters."""
    try:
        if len(protobuf_bytes) >= 6:
            short_ema = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            medium_ema = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            long_ema = protobuf_bytes[5] if len(protobuf_bytes) > 5 else 0
            return {
                "Short EMA Period": short_ema,
                "Medium EMA Period": medium_ema,
                "Long EMA Period": long_ema,
                "strategy_type": "TRIPLE_EMA_CROSSOVER",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "TRIPLE_EMA_CROSSOVER",
    }


def decode_heiken_ashi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode HEIKEN_ASHI parameters."""
    try:
        if len(protobuf_bytes) >= 2:
            period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            return {"Period": period, "strategy_type": "HEIKEN_ASHI"}
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "HEIKEN_ASHI",
    }


def decode_linear_regression_channels(
    protobuf_bytes: bytes, protobuf_type: str
) -> Dict:
    """Decode LINEAR_REGRESSION_CHANNELS parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            multiplier = protobuf_bytes[3] / 100.0 if len(protobuf_bytes) > 3 else 2.0
            return {
                "Period": period,
                "Multiplier": f"{multiplier:.2f}",
                "strategy_type": "LINEAR_REGRESSION_CHANNELS",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "LINEAR_REGRESSION_CHANNELS",
    }


def decode_vwap_mean_reversion(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode VWAP_MEAN_REVERSION parameters."""
    try:
        if len(protobuf_bytes) >= 6:
            vwap_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            ma_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            deviation = protobuf_bytes[5] / 100.0 if len(protobuf_bytes) > 5 else 2.0
            return {
                "VWAP Period": vwap_period,
                "Moving Average Period": ma_period,
                "Deviation Multiplier": f"{deviation:.2f}",
                "strategy_type": "VWAP_MEAN_REVERSION",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VWAP_MEAN_REVERSION",
    }


def decode_bband_wr(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode BBAND_WR parameters."""
    try:
        if len(protobuf_bytes) >= 6:
            bbands_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            wr_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            std_dev = protobuf_bytes[5] / 100.0 if len(protobuf_bytes) > 5 else 2.0
            return {
                "Bollinger Bands Period": bbands_period,
                "Williams %R Period": wr_period,
                "Standard Deviation Multiplier": f"{std_dev:.2f}",
                "strategy_type": "BBAND_WR",
            }
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "BBAND_WR"}


def decode_atr_cci(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode ATR_CCI parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            atr_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            cci_period = protobuf_bytes[3] if len(protobuf_bytes) > 3 else 0
            return {
                "ATR Period": atr_period,
                "CCI Period": cci_period,
                "strategy_type": "ATR_CCI",
            }
    except Exception:
        pass
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "ATR_CCI"}


def decode_donchian_breakout(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode DONCHIAN_BREAKOUT parameters."""
    try:
        if len(protobuf_bytes) >= 2:
            period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            return {"Period": period, "strategy_type": "DONCHIAN_BREAKOUT"}
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "DONCHIAN_BREAKOUT",
    }


def decode_volatility_stop(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode VOLATILITY_STOP parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            atr_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            multiplier = protobuf_bytes[3] / 100.0 if len(protobuf_bytes) > 3 else 2.0
            return {
                "ATR Period": atr_period,
                "Multiplier": f"{multiplier:.2f}",
                "strategy_type": "VOLATILITY_STOP",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLATILITY_STOP",
    }


def decode_atr_trailing_stop(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    """Decode ATR_TRAILING_STOP parameters."""
    try:
        if len(protobuf_bytes) >= 4:
            atr_period = protobuf_bytes[1] if len(protobuf_bytes) > 1 else 0
            multiplier = protobuf_bytes[3] / 100.0 if len(protobuf_bytes) > 3 else 2.0
            return {
                "ATR Period": atr_period,
                "Multiplier": f"{multiplier:.2f}",
                "strategy_type": "ATR_TRAILING_STOP",
            }
    except Exception:
        pass
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "ATR_TRAILING_STOP",
    }


# Add more decoder functions for other strategy types...
def decode_momentum_sma_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "MOMENTUM_SMA_CROSSOVER",
    }


def decode_kst_oscillator(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "KST_OSCILLATOR",
    }


def decode_stochastic_rsi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "STOCHASTIC_RSI",
    }


def decode_rvi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "RVI"}


def decode_mass_index(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "MASS_INDEX"}


def decode_momentum_pinball(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "MOMENTUM_PINBALL",
    }


def decode_volume_weighted_macd(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLUME_WEIGHTED_MACD",
    }


def decode_obv_ema(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "OBV_EMA"}


def decode_chaikin_oscillator(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "CHAIKIN_OSCILLATOR",
    }


def decode_klinger_volume(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "KLINGER_VOLUME",
    }


def decode_volume_breakout(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLUME_BREAKOUT",
    }


def decode_pvt(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "PVT"}


def decode_vpt(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "VPT"}


def decode_volume_spread_analysis(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLUME_SPREAD_ANALYSIS",
    }


def decode_tick_volume_analysis(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "TICK_VOLUME_ANALYSIS",
    }


def decode_volume_profile_deviations(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLUME_PROFILE_DEVIATIONS",
    }


def decode_volume_profile(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VOLUME_PROFILE",
    }


def decode_stochastic_ema(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "STOCHASTIC_EMA",
    }


def decode_cmo_mfi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "CMO_MFI"}


def decode_rsi_ema_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "RSI_EMA_CROSSOVER",
    }


def decode_trix_signal_line(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "TRIX_SIGNAL_LINE",
    }


def decode_cmf_zero_line(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "CMF_ZERO_LINE",
    }


def decode_rainbow_oscillator(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "RAINBOW_OSCILLATOR",
    }


def decode_price_oscillator_signal(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "PRICE_OSCILLATOR_SIGNAL",
    }


def decode_awesome_oscillator(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "AWESOME_OSCILLATOR",
    }


def decode_dema_tema_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "DEMA_TEMA_CROSSOVER",
    }


def decode_macd_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "MACD_CROSSOVER",
    }


def decode_vwap_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VWAP_CROSSOVER",
    }


def decode_roc_ma_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "ROC_MA_CROSSOVER",
    }


def decode_regression_channel(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "REGRESSION_CHANNEL",
    }


def decode_frama(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "FRAMA"}


def decode_double_top_bottom(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "DOUBLE_TOP_BOTTOM",
    }


def decode_fibonacci_retracements(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "FIBONACCI_RETRACEMENTS",
    }


def decode_price_gap(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "PRICE_GAP"}


def decode_renko_chart(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "RENKO_CHART",
    }


def decode_range_bars(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "RANGE_BARS"}


def decode_gann_swing(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "GANN_SWING"}


def decode_sar_mfi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "SAR_MFI"}


def decode_adx_dmi(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {"raw_hex": protobuf_bytes.hex()[:50] + "...", "strategy_type": "ADX_DMI"}


def decode_elder_ray_ma(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "ELDER_RAY_MA",
    }


def decode_dpo_crossover(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "DPO_CROSSOVER",
    }


def decode_variable_period_ema(protobuf_bytes: bytes, protobuf_type: str) -> Dict:
    return {
        "raw_hex": protobuf_bytes.hex()[:50] + "...",
        "strategy_type": "VARIABLE_PERIOD_EMA",
    }


# Database configuration flags
flags.DEFINE_string("postgres_host", "localhost", "PostgreSQL host")
flags.DEFINE_integer("postgres_port", 5432, "PostgreSQL port")
flags.DEFINE_string("postgres_database", "tradestream", "PostgreSQL database")
flags.DEFINE_string("postgres_username", "postgres", "PostgreSQL username")
flags.DEFINE_string("postgres_password", "", "PostgreSQL password")
flags.DEFINE_integer("api_port", 8080, "API server port")
flags.DEFINE_string("api_host", "0.0.0.0", "API server host")

# Global database connection parameters
DB_CONFIG = {}

# List of USD-pegged stablecoins to filter out
STABLECOINS = {
    # Major stablecoins
    "USDT",
    "USDC",
    "BUSD",
    "TUSD",
    "DAI",
    "FRAX",
    "USDP",
    "USDD",
    "GUSD",
    "LUSD",
    "USDN",
    "USDK",
    "USDJ",
    "USDK",
    "USDN",
    "USDK",
    "USDJ",
    "USDK",
    "USDN",
    "USDK",
    "PAX",
    "HUSD",
    "USDK",
    "USDJ",
    "USDN",
    "USDK",
    "USDJ",
    "USDK",
    "USDN",
    "USDK",
    # With USD pairs
    "USDT/USD",
    "USDC/USD",
    "BUSD/USD",
    "TUSD/USD",
    "DAI/USD",
    "FRAX/USD",
    "USDP/USD",
    "USDD/USD",
    "GUSD/USD",
    "LUSD/USD",
    "USDN/USD",
    "USDK/USD",
    "USDJ/USD",
    "PAX/USD",
    "HUSD/USD",
    "USDK/USD",
    "USDJ/USD",
    "USDN/USD",
    # With USDT pairs (stablecoin pairs)
    "USDT/USDT",
    "USDC/USDT",
    "BUSD/USDT",
    "TUSD/USDT",
    "DAI/USDT",
    "FRAX/USDT",
    "USDP/USDT",
    "USDD/USDT",
    "GUSD/USDT",
    "LUSD/USDT",
    "USDN/USDT",
    "USDK/USDT",
    "USDJ/USDT",
    "PAX/USDT",
    "HUSD/USDT",
    # With USDC pairs
    "USDT/USDC",
    "USDC/USDC",
    "BUSD/USDC",
    "TUSD/USDC",
    "DAI/USDC",
    "FRAX/USDC",
    "USDP/USDC",
    "USDD/USDC",
    "GUSD/USDC",
    "LUSD/USDC",
    "USDN/USDC",
    "USDK/USDC",
    "USDJ/USDC",
    "PAX/USDC",
    "HUSD/USDC",
}


def is_stablecoin(symbol: str) -> bool:
    """Check if a symbol is a USD-pegged stablecoin."""
    if not symbol:
        return False

    # Convert to uppercase for comparison
    upper_symbol = symbol.upper()

    # First, explicitly check for crypto pairs that are NOT stablecoins
    crypto_pairs = {"BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT", "ADA/BTC", "DOT/ETH"}
    if upper_symbol in crypto_pairs:
        return False

    # Check if the exact symbol is in our stablecoin list
    if upper_symbol in STABLECOINS:
        return True

    # Check if it's a stablecoin pair (e.g., USDT/USD, USDC/USDT)
    if "/" in upper_symbol:
        base, quote = upper_symbol.split("/", 1)
        # Only consider it a stablecoin if BOTH parts are stablecoins
        if base in STABLECOINS and quote in STABLECOINS:
            return True
        # Or if it's a direct USD pair of a stablecoin
        if base in STABLECOINS and quote == "USD":
            return True
        if quote in STABLECOINS and base == "USD":
            return True

    return False


def get_db_connection():
    """Get a database connection."""
    if not DB_CONFIG:
        raise Exception("Database configuration not initialized")

    return psycopg2.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["username"],
        password=DB_CONFIG["password"],
    )


def fetch_all_strategies() -> List[Dict]:
    """Fetch all active strategies from the database."""
    conn = get_db_connection()

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = """
        SELECT 
            strategy_id,
            symbol,
            strategy_type,
            parameters,
            current_score,
            strategy_hash,
            discovery_symbol,
            discovery_start_time,
            discovery_end_time,
            first_discovered_at,
            last_evaluated_at,
            created_at,
            updated_at
        FROM Strategies 
        WHERE is_active = TRUE
        ORDER BY current_score DESC
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        strategies = []
        for row in rows:
            # Skip stablecoins
            if is_stablecoin(row["symbol"]):
                continue

            # Parse parameters if it's a string
            params_field = row["parameters"]
            if isinstance(params_field, str):
                try:
                    params_field = json.loads(params_field)
                except Exception:
                    params_field = {}

            # Decode parameters if they contain base64_data
            decoded_params = {}
            if params_field and isinstance(params_field, dict):
                if "base64_data" in params_field:
                    # This is the format from the database (base64 encoded)
                    decoded_params = decode_base64_parameters(
                        params_field["base64_data"]
                    )
                elif "protobuf_data" in params_field:
                    # This is the format from the strategy consumer (hex encoded)
                    decoded_params = decode_hex_parameters(
                        params_field["protobuf_data"],
                        params_field.get("protobuf_type", ""),
                    )

            # Calculate backtest period in days
            backtest_period_days = None
            if row["discovery_start_time"] and row["discovery_end_time"]:
                delta = row["discovery_end_time"] - row["discovery_start_time"]
                backtest_period_days = delta.days

            strategy = {
                "strategy_id": str(row["strategy_id"]),
                "symbol": row["symbol"],
                "strategy_type": row["strategy_type"],
                "parameters": decoded_params,
                "current_score": float(row["current_score"]),
                "strategy_hash": row["strategy_hash"],
                "discovery_symbol": row["discovery_symbol"],
                "discovery_start_time": (
                    row["discovery_start_time"].isoformat()
                    if row["discovery_start_time"]
                    else None
                ),
                "discovery_end_time": (
                    row["discovery_end_time"].isoformat()
                    if row["discovery_end_time"]
                    else None
                ),
                "backtest_period_days": backtest_period_days,
                "first_discovered_at": (
                    row["first_discovered_at"].isoformat()
                    if row["first_discovered_at"]
                    else None
                ),
                "last_evaluated_at": (
                    row["last_evaluated_at"].isoformat()
                    if row["last_evaluated_at"]
                    else None
                ),
                "created_at": (
                    row["created_at"].isoformat() if row["created_at"] else None
                ),
                "updated_at": (
                    row["updated_at"].isoformat() if row["updated_at"] else None
                ),
            }
            strategies.append(strategy)

        return strategies

    finally:
        conn.close()


def fetch_strategy_metrics() -> Dict:
    """Fetch strategy metrics and aggregated data."""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Get all symbols to filter out stablecoins
        cursor.execute("SELECT DISTINCT symbol FROM Strategies WHERE is_active = TRUE")
        all_symbols = [row[0] for row in cursor.fetchall()]
        non_stablecoin_symbols = [s for s in all_symbols if not is_stablecoin(s)]

        # Build WHERE clause to exclude stablecoins
        if non_stablecoin_symbols:
            symbol_filter = (
                " AND symbol IN ("
                + ",".join(["%s"] * len(non_stablecoin_symbols))
                + ")"
            )
            symbol_params = tuple(non_stablecoin_symbols)
        else:
            symbol_filter = " AND FALSE"  # No non-stablecoin symbols
            symbol_params = ()

        # Basic counts (excluding stablecoins)
        cursor.execute(
            "SELECT COUNT(*) FROM Strategies WHERE is_active = TRUE" + symbol_filter,
            symbol_params,
        )
        total_strategies = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT symbol) FROM Strategies WHERE is_active = TRUE"
            + symbol_filter,
            symbol_params,
        )
        total_symbols = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT strategy_type) FROM Strategies WHERE is_active = TRUE"
            + symbol_filter,
            symbol_params,
        )
        total_strategy_types = cursor.fetchone()[0]

        # Score statistics (excluding stablecoins)
        cursor.execute(
            "SELECT AVG(current_score), MAX(current_score), MIN(current_score) FROM Strategies WHERE is_active = TRUE"
            + symbol_filter,
            symbol_params,
        )
        score_stats = cursor.fetchone()
        if score_stats and score_stats[0] is not None:
            avg_score, max_score, min_score = score_stats
        else:
            avg_score, max_score, min_score = 0.0, 0.0, 0.0

        # Recent strategies (last 24 hours, excluding stablecoins)
        yesterday = datetime.now() - timedelta(days=1)
        cursor.execute(
            "SELECT COUNT(*) FROM Strategies WHERE is_active = TRUE AND created_at > %s"
            + symbol_filter,
            (yesterday,) + symbol_params,
        )
        recent_strategies = cursor.fetchone()[0]

        # Top strategy types by count (excluding stablecoins)
        cursor.execute(
            """
            SELECT strategy_type, COUNT(*) as count, AVG(current_score) as avg_score
            FROM Strategies 
            WHERE is_active = TRUE 
        """
            + symbol_filter
            + """
            GROUP BY strategy_type 
            ORDER BY count DESC 
            LIMIT 10
        """,
            symbol_params,
        )
        strategy_type_counts = cursor.fetchall()

        # Top symbols by count (excluding stablecoins)
        cursor.execute(
            """
            SELECT symbol, COUNT(*) as count, AVG(current_score) as avg_score
            FROM Strategies 
            WHERE is_active = TRUE 
        """
            + symbol_filter
            + """
            GROUP BY symbol 
            ORDER BY count DESC 
            LIMIT 10
        """,
            symbol_params,
        )
        symbol_counts = cursor.fetchall()

        return {
            "total_strategies": total_strategies or 0,
            "total_symbols": total_symbols or 0,
            "total_strategy_types": total_strategy_types or 0,
            "avg_score": float(avg_score) if avg_score else 0.0,
            "max_score": float(max_score) if max_score else 0.0,
            "min_score": float(min_score) if min_score else 0.0,
            "recent_strategies_24h": recent_strategies or 0,
            "top_strategy_types": [
                {"strategy_type": row[0], "count": row[1], "avg_score": float(row[2])}
                for row in strategy_type_counts
            ],
            "top_symbols": [
                {"symbol": row[0], "count": row[1], "avg_score": float(row[2])}
                for row in symbol_counts
            ],
        }

    finally:
        conn.close()


# API Routes


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/api/strategies", methods=["GET"])
def get_strategies():
    """Get all strategies with optional filtering."""
    try:
        # Get query parameters
        symbol = request.args.get("symbol")
        strategy_type = request.args.get("strategy_type")
        limit = request.args.get("limit", type=int)
        min_score = request.args.get("min_score", type=float)

        # Fetch strategies
        strategies = fetch_all_strategies()

        # Apply filters
        if symbol:
            strategies = [
                s for s in strategies if s["symbol"].lower() == symbol.lower()
            ]

        if strategy_type:
            strategies = [
                s
                for s in strategies
                if s["strategy_type"].lower() == strategy_type.lower()
            ]

        if min_score is not None:
            strategies = [s for s in strategies if s["current_score"] >= min_score]

        if limit:
            strategies = strategies[:limit]

        return jsonify(
            {
                "strategies": strategies,
                "count": len(strategies),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error fetching strategies: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategies/<strategy_id>", methods=["GET"])
def get_strategy_by_id(strategy_id):
    """Get a specific strategy by ID."""
    try:
        strategies = fetch_all_strategies()

        strategy = next(
            (s for s in strategies if s["strategy_id"] == strategy_id), None
        )

        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404

        return jsonify(strategy)

    except Exception as e:
        logging.error(f"Error fetching strategy {strategy_id}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Get strategy metrics and aggregated data."""
    try:
        metrics = fetch_strategy_metrics()

        return jsonify({"metrics": metrics, "timestamp": datetime.now().isoformat()})

    except Exception as e:
        logging.error(f"Error fetching metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/symbols", methods=["GET"])
def get_symbols():
    """Get all unique symbols."""
    try:
        strategies = fetch_all_strategies()

        symbols = sorted(list(set(s["symbol"] for s in strategies)))

        return jsonify(
            {
                "symbols": symbols,
                "count": len(symbols),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error fetching symbols: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy-types", methods=["GET"])
def get_strategy_types():
    """Get all unique strategy types."""
    try:
        strategies = fetch_all_strategies()

        strategy_types = sorted(list(set(s["strategy_type"] for s in strategies)))

        return jsonify(
            {
                "strategy_types": strategy_types,
                "count": len(strategy_types),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logging.error(f"Error fetching strategy types: {e}")
        return jsonify({"error": str(e)}), 500


def main(argv):
    """Main function to start the API server."""
    global DB_CONFIG

    # Parse flags
    absl_app.parse_flags_with_usage(argv)

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Check for environment variables (for Kubernetes deployment)
    import os

    # Get database configuration from environment variables or flags
    postgres_host = os.environ.get("POSTGRES_HOST", FLAGS.postgres_host)
    postgres_port = int(os.environ.get("POSTGRES_PORT", str(FLAGS.postgres_port)))
    postgres_database = os.environ.get("POSTGRES_DATABASE", FLAGS.postgres_database)
    postgres_username = os.environ.get("POSTGRES_USERNAME", FLAGS.postgres_username)
    postgres_password = os.environ.get("POSTGRES_PASSWORD", FLAGS.postgres_password)

    # Get API configuration from environment variables or flags
    api_port = int(os.environ.get("API_PORT", str(FLAGS.api_port)))
    api_host = os.environ.get("API_HOST", FLAGS.api_host)

    # Validate required configuration
    if not postgres_password:
        logging.error("PostgreSQL password is required")
        return 1

    # Store database configuration
    DB_CONFIG = {
        "host": postgres_host,
        "port": postgres_port,
        "database": postgres_database,
        "username": postgres_username,
        "password": postgres_password,
    }

    # Test database connection
    try:
        test_conn = get_db_connection()
        test_conn.close()
        logging.info("Database connection test successful")
    except Exception as e:
        logging.error(f"Database connection test failed: {e}")
        return 1

    # Start Flask server
    logging.info(f"Starting Strategy Monitor API on {api_host}:{api_port}")
    app.run(host=api_host, port=api_port, debug=False, threaded=True)


if __name__ == "__main__":
    absl_app.run(main)
