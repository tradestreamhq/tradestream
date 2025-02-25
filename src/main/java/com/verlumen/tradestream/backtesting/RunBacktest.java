package com.verlumen.tradestream.backtesting;

import com.google.inject.Inject;
import com.google.protobuf.InvalidProtocolBufferException;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;

import java.io.Serializable;

/**
 * A PTransform that runs backtests by wrapping the BacktestRunner.
 */
public class RunBacktest extends PTransform<PCollection<BacktestRequest>, PCollection<BacktestResult>> {

    private final SerializableBacktestRunnerFactory backtestRunnerFactory;

    @Inject
    RunBacktest(SerializableBacktestRunnerFactory backtestRunnerFactory) {
        this.backtestRunnerFactory = backtestRunnerFactory;
    }

    @Override
    public PCollection<BacktestResult> expand(PCollection<BacktestRequest> input) {
        return input.apply("Run Backtest", ParDo.of(new RunBacktestDoFn(backtestRunnerFactory)));
    }

    /**
     * A factory for creating BacktestRunner instances that must be serializable.
     */
    public interface SerializableBacktestRunnerFactory extends Serializable {
        BacktestRunner create();
    }

    /**
     * A DoFn that invokes the BacktestRunner for each backtest request.
     */
    private static class RunBacktestDoFn extends DoFn<BacktestRequest, BacktestResult> {
        private final SerializableBacktestRunnerFactory backtestRunnerFactory;
        private transient BacktestRunner backtestRunner;

        RunBacktestDoFn(SerializableBacktestRunnerFactory factory) {
            this.backtestRunnerFactory = factory;
        }

        @Setup
        public void setup() {
            backtestRunner = backtestRunnerFactory.create();
        }

        @ProcessElement
        public void processElement(ProcessContext context) throws InvalidProtocolBufferException {
            BacktestRequest request = context.element();
            if (request == null) {
                throw new NullPointerException("BacktestRequest cannot be null");
            }
            BacktestResult result = backtestRunner.runBacktest(request);
            context.output(result);
        }
    }
}
