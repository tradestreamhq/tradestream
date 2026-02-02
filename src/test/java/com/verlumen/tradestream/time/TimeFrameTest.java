package com.verlumen.tradestream.time;

import static com.google.common.truth.Truth.assertThat;
import static org.junit.Assert.assertThrows;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;

@RunWith(JUnit4.class)
public class TimeFrameTest {

  @Test
  public void fiveMin_hasCorrectLabel() {
    assertThat(TimeFrame.FIVE_MIN.getLabel()).isEqualTo("5m");
  }

  @Test
  public void fiveMin_hasCorrectMinutes() {
    assertThat(TimeFrame.FIVE_MIN.getMinutes()).isEqualTo(5);
  }

  @Test
  public void fifteenMin_hasCorrectLabel() {
    assertThat(TimeFrame.FIFTEEN_MIN.getLabel()).isEqualTo("15m");
  }

  @Test
  public void fifteenMin_hasCorrectMinutes() {
    assertThat(TimeFrame.FIFTEEN_MIN.getMinutes()).isEqualTo(15);
  }

  @Test
  public void oneHour_hasCorrectLabel() {
    assertThat(TimeFrame.ONE_HOUR.getLabel()).isEqualTo("1h");
  }

  @Test
  public void oneHour_hasCorrectMinutes() {
    assertThat(TimeFrame.ONE_HOUR.getMinutes()).isEqualTo(60);
  }

  @Test
  public void oneDay_hasCorrectLabel() {
    assertThat(TimeFrame.ONE_DAY.getLabel()).isEqualTo("1d");
  }

  @Test
  public void oneWeek_hasCorrectLabel() {
    assertThat(TimeFrame.ONE_WEEK.getLabel()).isEqualTo("1w");
  }

  @Test
  public void oneMonth_hasCorrectLabel() {
    assertThat(TimeFrame.ONE_MONTH.getLabel()).isEqualTo("1M");
  }

  @Test
  public void oneYear_hasCorrectLabel() {
    assertThat(TimeFrame.ONE_YEAR.getLabel()).isEqualTo("1Y");
  }

  @Test
  public void fromMinutes_fiveMin_returnsFiveMin() {
    assertThat(TimeFrame.fromMinutes(5)).isEqualTo(TimeFrame.FIVE_MIN);
  }

  @Test
  public void fromMinutes_fifteenMin_returnsFifteenMin() {
    assertThat(TimeFrame.fromMinutes(15)).isEqualTo(TimeFrame.FIFTEEN_MIN);
  }

  @Test
  public void fromMinutes_sixtyMin_returnsOneHour() {
    assertThat(TimeFrame.fromMinutes(60)).isEqualTo(TimeFrame.ONE_HOUR);
  }

  @Test
  public void fromMinutes_invalidMinutes_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> TimeFrame.fromMinutes(7));
  }

  @Test
  public void fromMinutes_zeroMinutes_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> TimeFrame.fromMinutes(0));
  }

  @Test
  public void fromMinutes_negativeMinutes_throwsException() {
    assertThrows(IllegalArgumentException.class, () -> TimeFrame.fromMinutes(-1));
  }

  @Test
  public void allTimeFrames_havePositiveMinutes() {
    for (TimeFrame tf : TimeFrame.values()) {
      assertThat(tf.getMinutes()).isGreaterThan(0);
    }
  }

  @Test
  public void allTimeFrames_haveNonEmptyLabel() {
    for (TimeFrame tf : TimeFrame.values()) {
      assertThat(tf.getLabel()).isNotEmpty();
    }
  }

  @Test
  public void values_containsExpectedCount() {
    // 20 time frames defined
    assertThat(TimeFrame.values()).hasLength(20);
  }

  @Test
  public void fourHour_hasCorrectMinutes() {
    assertThat(TimeFrame.FOUR_HOUR.getMinutes()).isEqualTo(240);
  }

  @Test
  public void sixMonth_hasCorrectLabel() {
    assertThat(TimeFrame.SIX_MONTH.getLabel()).isEqualTo("6M");
  }
}
