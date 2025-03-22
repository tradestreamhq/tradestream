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
        // Create chromosomes (we won't try to control their values anymore)
        IntegerChromosome tenkanSenChromosome = IntegerChromosome.of(5, 60);
        IntegerChromosome kijunSenChromosome = IntegerChromosome.of(10, 120);
        IntegerChromosome senkouSpanBChromosome = IntegerChromosome.of(20, 240);
        IntegerChromosome chikouSpanChromosome = IntegerChromosome.of(10, 120);
        
        // Create the list of chromosomes
        List<NumericChromosome<?, ?>> chromosomes = List.of(
            tenkanSenChromosome,
            kijunSenChromosome,
            senkouSpanBChromosome,
            chikouSpanChromosome
        );
    
        Any packedParams = config.createParameters(ImmutableList.copyOf(chromosomes));
        assertThat(packedParams.is(IchimokuCloudParameters.class)).isTrue();
    
        // Extract the expected values directly from chromosomes
        int expectedTenkanSen = tenkanSenChromosome.get(0).allele();
        int expectedKijunSen = kijunSenChromosome.get(0).allele();
        int expectedSenkouSpanB = senkouSpanBChromosome.get(0).allele();
        int expectedChikouSpan = chikouSpanChromosome.get(0).allele();
        
        IchimokuCloudParameters params = packedParams.unpack(IchimokuCloudParameters.class);
        assertThat(params.getTenkanSenPeriod()).isEqualTo(expectedTenkanSen);
        assertThat(params.getKijunSenPeriod()).isEqualTo(expectedKijunSen);
        assertThat(params.getSenkouSpanBPeriod()).isEqualTo(expectedSenkouSpanB);
        assertThat(params.getChikouSpanPeriod()).isEqualTo(expectedChikouSpan);
      }

      @Test(expected = IllegalArgumentException.class)
      public void testCreateParameters_invalidChromosomeSize_throwsException() {
        // Create a single chromosome
        List<NumericChromosome<?, ?>> chromosomes =
            List.of(IntegerChromosome.of(5, 60));
    
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
