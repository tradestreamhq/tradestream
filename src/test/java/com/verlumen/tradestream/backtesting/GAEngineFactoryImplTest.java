package com.verlumen.tradestream;

import com.google.inject.Guice;
import com.google.inject.Injector;
import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;


public class GAEngineFactoryImplTest {

    private GAEngineFactory factory;

    @Before
    public void setUp() {
        // Arrange: Set up the Guice injector with the necessary modules.
        Injector injector = Guice.createInjector(new GAEngineModule());
        factory = injector.getInstance(GAEngineFactory.class);
    }

    @Test
    public void testCreate_ReturnsGAEngineInstance() {
        // Act: Call the create() method.
        GAEngine engine = factory.create();

        // Assert: Verify that the returned object is not null and is an instance of GAEngine.
        assertNotNull("GAEngine instance should not be null", engine);
        assertTrue("Returned object should be an instance of GAEngine", engine instanceof GAEngine);
    }

    @Test
    public void testCreate_ReturnsNewInstanceEachTime() {
        // Act: Call create() multiple times
        GAEngine engine1 = factory.create();
        GAEngine engine2 = factory.create();

        // Assert: Verify that different instances are returned each time.
        assertNotSame("create() should return a new instance each time", engine1, engine2);
    }
    
    @Test(expected = NullPointerException.class) // Expecting an exception
      public void testCreate_whenFactoryIsNull_throwsException() {
          // Arrange: Set up a scenario where a necessary dependency is null
          GAEngineFactory factoryWithNull = null;
          // Act: Call the create() method
          factoryWithNull.create();
      }
}
