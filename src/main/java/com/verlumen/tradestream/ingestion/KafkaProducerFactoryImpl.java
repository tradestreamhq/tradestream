import ocm.google.inject.Inject;
import ocm.google.inject.Provider;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.Producer;

import java.util.Properties;

final class KafkaProducerProvider implements Provider<KafkaProducer<String, String>> {
  @Inject
  KafkaProducerFactoryImpl() {}

  @Override
  public Producer<String, String> get() {
      Properties props = new Properties();
      props.put("bootstrap.servers", "localhost:9092");
      props.put("acks", "all");
      props.put("retries", 0);
      props.put("batch.size", 16384);
      props.put("linger.ms", 1);
      props.put("buffer.memory", 33554432);
      props.put("key.serializer", "org.apache.kafka.common.serialization.StringSerializer");
      props.put("value.serializer", "org.apache.kafka.common.serialization.StringSerializer");

      return new KafkaProducer<>(props);
  }
}
