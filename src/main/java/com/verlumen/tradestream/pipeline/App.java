package com.verlumen.tradestream.pipeline;

import com.google.inject.Guice;
import com.google.inject.Inject;
import java.util.Arrays;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.StreamingOptions;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;

final class App {
  public interface Options extends StreamingOptions {
    @Description("Input text to print.")
    @Default.String("My input text")
    String getInputText();

    void setInputText(String value);
  }

  @Inject
  App() {}

  static PCollection<String> buildPipeline(Pipeline pipeline, String inputText) {
    return pipeline
        .apply("Create elements", Create.of(Arrays.asList("Hello", "World!", inputText)))
        .apply(
            "Print elements",
            MapElements.into(TypeDescriptors.strings())
                .via(
                    x -> {
                      System.out.println(x);
                      return x;
                    }));
  }

  void runPipeline(String[] args) {
    var options = PipelineOptionsFactory.fromArgs(args).withValidation().as(Options.class);
    var pipeline = Pipeline.create(options);
    App.buildPipeline(pipeline, options.getInputText());
    pipeline.run().waitUntilFinish();
  }

  public static void main(String[] args) {
    App app = Guice.createInjector(PipelineModule.create()).getInstance(App.class);
    app.runPipeline(args);
  }
}
