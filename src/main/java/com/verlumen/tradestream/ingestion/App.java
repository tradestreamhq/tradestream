package com.example.myproject;

import com.google.inject.Guice;
import com.google.inject.Inject;

final class App {
  private final RealTimeDataIngestion realTimeDataIngestion;

  @Inject
  App(RealTimeDataIngestion realTimeDataIngestion) {
    this.realTimeDataIngestion = realTimeDataIngestion;
  }

  public static void main(String... args) throws Exception {
    RealTimeDataIngestion realTimeDataIngestion = new RealTimeDataIngestion();
    App app = new App(realTimeDataIngestion);
    System.out.println("Starting real-time data ingestion...");
  }

}
