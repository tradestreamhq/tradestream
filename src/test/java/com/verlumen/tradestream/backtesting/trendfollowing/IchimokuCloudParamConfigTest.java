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
        // Define test values to use
        final int TEST_TENKAN_SEN = 11;
        final int TEST_KIJUN_SEN = 26;  
        final int TEST_SENKOU_SPAN_B = 52;
        final int TEST_CHIKOU_SPAN = 26;
        
        // Create single-gene chromosomes with known values
        IntegerChromosome tenkanSenChromosome = IntegerChromosome.of(5, 60, TEST_TENKAN_SEN);
        IntegerChromosome kijunSenChromosome = IntegerChromosome.of(10, 120, TEST_KIJUN_SEN);
        IntegerChromosome senkouSpanBChromosome = IntegerChromosome.of(20, 240, TEST_SENKOU_SPAN_B);
        IntegerChromosome chikouSpanChromosome = IntegerChromosome.of(10, 120, TEST_CHIKOU_SPAN);
        
        // Create the list of chromosomes
        List<NumericChromosome<?, ?>> chromosomes = List.of(
            tenkanSenChromosome,
            kijunSenChromosome,
            senkouSpanBChromosome,
            chikouSpanChromosome
        );
    
        Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
        assertThat(packedParams.is(IchimokuCloudParameters.class)).isTrue();
    
        IchimokuCloudParameters params = packedParams.unpack(IchimokuCloudParameters.class);
        assertThat(params.getTenkanSenPeriod()).isEqualTo(TEST_TENKAN_SEN);
        assertThat(params.getKijunSenPeriod()).isEqualTo(TEST_KIJUN_SEN);
        assertThat(params.getSenkouSpanBPeriod()).isEqualTo(TEST_SENKOU_SPAN_B);
        assertThat(params.getChikouSpanPeriod()).isEqualTo(TEST_CHIKOU_SPAN);
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
