package com.verlumen.tradestream.ingestion;

import static org.mockito.Mockito.verify;

import com.google.inject.testing.fieldbinder.Bind;
import com.google.inject.testing.fieldbinder.BoundFieldModule;
import com.google.inject.Guice;
import com.google.inject.Inject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.mockito.Mock;
import org.mockito.junit.MockitoJUnitRunner;

@RunWith(MockitoJUnitRunner.class)
public class AppTest {
  
  @Rule public MockitoRule rule = MockitoJUnit.rule().strictness(Strictness.STRICT_STUBS);
  
  @Bind @Mock
  private MarketDataIngestion mockMarketDataIngestion;

  @Inject
  private App app;
  
  @Before
  public void setUp() {
      Guice.createInjector(BoundFieldModule.of(this)).injectMembers(this);
  }
  
  @Test
  public void run_callsMarketDataIngestionStart() {
      // Act
      app.run();
  
      // Assert
      verify(mockMarketDataIngestion).start();
  }

}
