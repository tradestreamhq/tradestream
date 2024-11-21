package com.verlumen.tradestream.ingestion;

import java.util.function.Supplier;

interface CurrencyPairSupplier extends Supplier<ImmutableSet<CurrencyPairMetadata>> {}
