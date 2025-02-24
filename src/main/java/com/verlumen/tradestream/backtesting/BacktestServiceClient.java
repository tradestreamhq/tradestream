package com.verlumen.tradestream.backtesting;

import com.verlumen.tradestream.backtesting.BacktestRequest;
import com.verlumen.tradestream.backtesting.BacktestResult;

interface BacktestServiceClient {
    BacktestResult runBacktest(BacktestRequest request);
}
