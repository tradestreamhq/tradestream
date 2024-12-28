package com.verlumen.tradestream.backtesting.params;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.fail;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class ParamRangeTest {

    /**
     * Test that creating a ParamRange with min < max succeeds.
     */
    @Test
    public void testCreateValidParamRange() {
        ParamConfig.ParamRange<Integer> range = ParamConfig.ParamRange.create(1, 10);
        assertNotNull("ParamRange should not be null", range);
        assertEquals("Min value should be 1", 1, range.min());
        assertEquals("Max value should be 10", 10, range.max());
    }

    /**
     * Test that creating a ParamRange with min == max throws IllegalArgumentException.
     */
    @Test
    public void testCreateInvalidParamRangeEqual() {
        assertThrows(IllegalArgumentException.class, () -> ParamConfig.ParamRange.create(10, 10));
    }

    /**
     * Test that creating a ParamRange with min > max throws IllegalArgumentException.
     */
    @Test
    public void testCreateInvalidParamRangeGreater() {
        assertThrows(IllegalArgumentException.class, () -> ParamConfig.ParamRange.create(20, 10));
    }
}
