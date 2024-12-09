package com.verlumen.tradestream.ingestion;

import static com.google.common.collect.ImmutableList.toImmutableList;

import com.google.common.collect.ImmutableList;
import com.verlumen.tradestream.instruments.CurrencyPair;

/**
 * Interface representing a supply of {@link CurrencyPairMetadata}.
 * 
 * Provides methods to access metadata, currency pairs, and their symbols.
 * Implementations of this interface are expected to supply a list of metadata
 * for various currency pairs, and convenience methods are provided to extract
 * the currency pairs and their symbols.
 */
interface CurrencyPairSupply {
  /**
   * Returns a list of {@link CurrencyPairMetadata} containing information about
   * currency pairs, such as their base and counter currencies and associated metadata.
   *
   * @return an {@link ImmutableList} of {@link CurrencyPairMetadata}.
   */
  ImmutableList<CurrencyPairMetadata> metadataList();

  /**
   * Returns a list of {@link CurrencyPair} extracted from the metadata.
   *
   * This method provides a convenience for accessing only the currency pair
   * objects without their associated metadata.
   *
   * @return an {@link ImmutableList} of {@link CurrencyPair}.
   */
  default ImmutableList<CurrencyPair> currencyPairs() {
    return metadataList()
      .stream()
      .map(CurrencyPairMetadata::currencyPair) // Extract the CurrencyPair from each metadata.
      .collect(toImmutableList());
  }

  /**
   * Returns a list of symbols representing the currency pairs.
   *
   * Each symbol is generated using the {@link CurrencyPair#symbol()} method, 
   * which reconstructs the currency pair in its original symbol format (e.g., "BTC/USD").
   *
   * @return an {@link ImmutableList} of currency pair symbols.
   */
  default ImmutableList<String> symbols() {
    return currencyPairs()
      .stream()
      .map(CurrencyPair::symbol) // Map each CurrencyPair to its symbol.
      .collect(toImmutableList());
  }
}
