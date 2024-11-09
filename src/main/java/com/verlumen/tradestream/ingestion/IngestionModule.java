final class IngestionModule extends AbstractModule {
  @Override
  protected void configure() {
    bind(MarketDataIngestion.class).to(RealTimeDataIngestion.class);
  }
}
