package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;

/**
 * A PTransform that runs backtests by wrapping the BacktestRunner.
 */
public class RunBacktest extends PTransform<PCollection<BacktestRunner.BacktestRequest>, PCollection<BacktestResult>> {

  private final RunBacktestDoFn runBacktestDoFn;

  @Inject
  RunBacktest(RunBacktestDoFn runBacktestDoFn) {
    this.runBacktestDoFn = runBacktestDoFn;
  }

  @Override
  public PCollection<BacktestResult> expand(PCollection<BacktestRunner.BacktestRequest> input) {
    return input.apply("Run Backtest", ParDo.of(runBacktestDoFn));
  }

  /**
   * A DoFn that invokes the BacktestRunner for each backtest request.
   */
  private static class RunBacktestDoFn extends DoFn<BacktestRunner.BacktestRequest, BacktestResult> {
    private final BacktestRunner backtestRunner;

    @Inject
    RunBacktestDoFn(BacktestRunner backtestRunner) {
      this.backtestRunner = backtestRunner;
    }

    @ProcessElement
    public void processElement(ProcessContext context) {
      BacktestRunner.BacktestRequest request = context.element();
      BacktestResult result = backtestRunner.runBacktest(request);
      context.output(result);
    }
  }
}
