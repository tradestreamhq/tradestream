package com.verlumen.tradestream.backtesting;

import java.util.Locale;

/** Generates human-readable reports from backtest results. */
public final class BacktestReport {

  private BacktestReport() {}

  /** Formats a BacktestResult into a multi-line summary string. */
  public static String generate(String strategyName, BacktestResult result) {
    StringBuilder sb = new StringBuilder();
    sb.append("========================================\n");
    sb.append(String.format("  Backtest Report: %s%n", strategyName));
    sb.append("========================================\n");
    sb.append("\n--- Performance ---\n");
    sb.append(String.format(Locale.US, "  Cumulative Return:   %+.4f%n", result.getCumulativeReturn()));
    sb.append(String.format(Locale.US, "  Annualized Return:   %+.4f%n", result.getAnnualizedReturn()));
    sb.append(String.format(Locale.US, "  Strategy Score:      %.4f%n", result.getStrategyScore()));
    sb.append("\n--- Risk Metrics ---\n");
    sb.append(String.format(Locale.US, "  Sharpe Ratio:        %+.4f%n", result.getSharpeRatio()));
    sb.append(String.format(Locale.US, "  Sortino Ratio:       %+.4f%n", result.getSortinoRatio()));
    sb.append(String.format(Locale.US, "  Max Drawdown:        %.4f%n", result.getMaxDrawdown()));
    sb.append(String.format(Locale.US, "  Volatility:          %.4f%n", result.getVolatility()));
    sb.append("\n--- Trade Statistics ---\n");
    sb.append(String.format(Locale.US, "  Number of Trades:    %d%n", result.getNumberOfTrades()));
    sb.append(String.format(Locale.US, "  Win Rate:            %.2f%%%n", result.getWinRate() * 100));
    sb.append(String.format(Locale.US, "  Profit Factor:       %.4f%n", result.getProfitFactor()));
    sb.append(String.format(Locale.US, "  Avg Trade Duration:  %.1f bars%n", result.getAverageTradeDuration()));
    sb.append("========================================\n");
    return sb.toString();
  }

  /** Generates a compact one-line summary for comparison tables. */
  public static String generateOneLine(String strategyName, BacktestResult result) {
    return String.format(
        Locale.US,
        "%-25s | Return: %+.4f | Sharpe: %+.4f | MaxDD: %.4f | WinRate: %.1f%% | Trades: %d",
        strategyName,
        result.getCumulativeReturn(),
        result.getSharpeRatio(),
        result.getMaxDrawdown(),
        result.getWinRate() * 100,
        result.getNumberOfTrades());
  }
}
