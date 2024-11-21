package com.verlumen.tradestream.ingestion;

import com.google.common.collect.ImmutableSet;

import java.util.function.Supplier;

interface CurrencyPairSupplier extends Supplier<ImmutableSet<CurrencyPairMetadata>> {}
