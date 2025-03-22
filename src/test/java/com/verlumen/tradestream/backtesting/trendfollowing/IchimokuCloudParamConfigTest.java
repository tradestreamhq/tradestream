package com.verlumen.tradestream.backtesting.trendfollowing;

import static com.google.common.truth.Truth.assertThat;

import com.google.common.collect.ImmutableList;
import com.google.protobuf.Any;
import com.verlumen.tradestream.backtesting.ChromosomeSpec;
import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import io.jenetics.IntegerChromosome;
import io.jenetics.NumericChromosome;
import java.util.List;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class IchimokuCloudParamConfigTest {
      private IchimokuCloudParamConfig config;

      @Before
      public void setUp() {
        config = IchimokuCloudParamConfig.create();
      }

      @Test
      public void testGetChromosomeSpecs_returnsExpectedSpecs() {
        ImmutableList<ChromosomeSpec<?>> specs = config.getChromosomeSpecs();
        assertThat(specs).hasSize(4);
      }
    
      @Test
      public void testCreateParameters_validChromosomes_returnsPackedParameters() throws Exception {
        // Create chromosomes with correct parameter order: min, max, value
        List<NumericChromosome<?, ?>> chromosomes = List.of(
            IntegerChromosome.of(5, 60, 9),     // tenkanSenPeriod
            IntegerChromosome.of(10, 120, 26),   // kijunSenPeriod
            IntegerChromosome.of(20, 240, 52),   // senkouSpanBPeriod
            IntegerChromosome.of(10, 120, 26)    // chikouSpanPeriod
        );
    
        Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
        assertThat(packedParams.is(IchimokuCloudParameters.class)).isTrue();
    
        IchimokuCloudParameters params = packedParams.unpack(IchimokuCloudParameters.class);
        assertThat(params.getTenkanSenPeriod()).isEqualTo(9);
        assertThat(params.getKijunSenPeriod()).isEqualTo(26);
        assertThat(params.getSenkouSpanBPeriod()).isEqualTo(52);
        assertThat(params.getChikouSpanPeriod()).isEqualTo(26);
      }

      @Test(expected = IllegalArgumentException.class)
      public void testCreateParameters_invalidChromosomeSize_throwsException() {
        // Create a single chromosome with correct parameter order: min, max, value
        List<NumericChromosome<?, ?>> chromosomes =
            List.of(IntegerChromosome.of(5, 60, 9)); // Only one chromosome
    
        config.createParameters(ImmutableList.copyOf(chromosomes));
      }

      @Test
      public void testInitialChromosomes_returnsExpectedSize() {
        ImmutableList<? extends NumericChromosome<?, ?>> chromosomes = config.initialChromosomes();
        assertThat(chromosomes).hasSize(4);
        assertThat(chromosomes.get(0)).isInstanceOf(IntegerChromosome.class);
        assertThat(chromosomes.get(1)).isInstanceOf(IntegerChromosome.class);
        assertThat(chromosomes.get(2)).isInstanceOf(IntegerChromosome.class);
        assertThat(chromosomes.get(3)).isInstanceOf(IntegerChromosome.class);

        // Verify ranges
        IntegerChromosome tenkanSenPeriod = (IntegerChromosome) chromosomes.get(0);
        assertThat(tenkanSenPeriod.min()).isEqualTo(5);
        assertThat(tenkanSenPeriod.max()).isEqualTo(60);
      }
    
      @Test
      public void testGetStrategyType_returnsExpectedType() {
        assertThat(config.getStrategyType()).isEqualTo(StrategyType.ICHIMOKU_CLOUD);
      }
}
