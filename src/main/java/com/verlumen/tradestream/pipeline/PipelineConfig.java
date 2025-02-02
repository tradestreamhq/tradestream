package com.verlumen.tradestream.pipeline;

record PipelineConfig(String bootstrapServers, String tradeTopic, String runMode) {}
