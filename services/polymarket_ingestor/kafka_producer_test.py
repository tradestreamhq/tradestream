"""Tests for the Polymarket Kafka producer."""

from unittest import mock
from absl.testing import absltest
import kafka

from services.polymarket_ingestor.kafka_producer import PolymarketKafkaProducer


class PolymarketKafkaProducerTest(absltest.TestCase):
    def test_init_ssl_missing_cafile_raises(self):
        with self.assertRaises(ValueError) as ctx:
            PolymarketKafkaProducer(
                bootstrap_servers="localhost:9092",
                security_protocol="SSL",
                ssl_cafile=None,
            )
        self.assertIn("ssl_cafile is required", str(ctx.exception))

    def test_init_sasl_ssl_missing_cafile_raises(self):
        with self.assertRaises(ValueError) as ctx:
            PolymarketKafkaProducer(
                bootstrap_servers="localhost:9092",
                security_protocol="SASL_SSL",
                ssl_cafile=None,
            )
        self.assertIn("ssl_cafile is required", str(ctx.exception))

    def test_init_plaintext_no_cafile_ok(self):
        with mock.patch("kafka.KafkaProducer"):
            producer = PolymarketKafkaProducer(
                bootstrap_servers="localhost:9092",
                security_protocol="PLAINTEXT",
            )
            self.assertIsNotNone(producer.producer)
            producer.close()

    @mock.patch("kafka.KafkaProducer")
    def test_publish_sends_message(self, mock_kafka_cls):
        mock_producer = mock.MagicMock()
        mock_future = mock.MagicMock()
        mock_metadata = mock.MagicMock()
        mock_metadata.partition = 0
        mock_metadata.offset = 42
        mock_future.get.return_value = mock_metadata
        mock_producer.send.return_value = mock_future
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.publish("test-topic", b"test-message", key="key1")

        mock_producer.send.assert_called_once_with(
            "test-topic", value=b"test-message", key=b"key1"
        )

    @mock.patch("kafka.KafkaProducer")
    def test_publish_without_key(self, mock_kafka_cls):
        mock_producer = mock.MagicMock()
        mock_future = mock.MagicMock()
        mock_metadata = mock.MagicMock()
        mock_metadata.partition = 0
        mock_metadata.offset = 1
        mock_future.get.return_value = mock_metadata
        mock_producer.send.return_value = mock_future
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.publish("test-topic", b"msg")

        mock_producer.send.assert_called_once_with("test-topic", value=b"msg", key=None)

    @mock.patch("kafka.KafkaProducer")
    def test_close_flushes_and_closes(self, mock_kafka_cls):
        mock_producer = mock.MagicMock()
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.close()

        mock_producer.flush.assert_called_once_with(timeout=10)
        mock_producer.close.assert_called_once_with(timeout=10)

    @mock.patch("kafka.KafkaProducer")
    def test_close_when_producer_is_none(self, mock_kafka_cls):
        """close() is safe when producer was never initialized."""
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.producer = None

        producer.close()  # Should not raise

    @mock.patch("kafka.KafkaProducer")
    def test_close_handles_flush_error(self, mock_kafka_cls):
        """close() still calls close on producer even if flush raises."""
        mock_producer = mock.MagicMock()
        mock_producer.flush.side_effect = kafka.errors.KafkaError("flush failed")
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.close()

        mock_producer.flush.assert_called_once()
        mock_producer.close.assert_called_once_with(timeout=10)

    @mock.patch("kafka.KafkaProducer")
    def test_close_sets_producer_to_none(self, mock_kafka_cls):
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.close()
        self.assertIsNone(producer.producer)

    @mock.patch("kafka.KafkaProducer")
    def test_build_ssl_kwargs_with_ssl(self, mock_kafka_cls):
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="SSL",
            ssl_cafile="/path/ca.crt",
            ssl_certfile="/path/cert.crt",
            ssl_keyfile="/path/key.pem",
        )
        kwargs = producer._build_ssl_kwargs()
        self.assertEqual(kwargs["security_protocol"], "SSL")
        self.assertEqual(kwargs["ssl_cafile"], "/path/ca.crt")
        self.assertEqual(kwargs["ssl_certfile"], "/path/cert.crt")
        self.assertEqual(kwargs["ssl_keyfile"], "/path/key.pem")
        producer.close()

    @mock.patch("kafka.KafkaProducer")
    def test_build_ssl_kwargs_with_password(self, mock_kafka_cls):
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="SSL",
            ssl_cafile="/path/ca.crt",
            ssl_password="secret123",
        )
        kwargs = producer._build_ssl_kwargs()
        self.assertEqual(kwargs["ssl_password"], "secret123")
        producer.close()

    @mock.patch("kafka.KafkaProducer")
    def test_build_ssl_kwargs_plaintext_empty(self, mock_kafka_cls):
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        kwargs = producer._build_ssl_kwargs()
        self.assertEqual(kwargs, {})
        producer.close()

    @mock.patch("kafka.KafkaProducer")
    def test_build_ssl_kwargs_sasl_ssl(self, mock_kafka_cls):
        mock_kafka_cls.return_value = mock.MagicMock()
        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="SASL_SSL",
            ssl_cafile="/path/ca.crt",
        )
        kwargs = producer._build_ssl_kwargs()
        self.assertEqual(kwargs["security_protocol"], "SASL_SSL")
        self.assertEqual(kwargs["ssl_cafile"], "/path/ca.crt")
        producer.close()

    @mock.patch("kafka.KafkaProducer")
    def test_connect_no_brokers_available_raises(self, mock_kafka_cls):
        mock_kafka_cls.side_effect = kafka.errors.NoBrokersAvailable()

        with self.assertRaises(kafka.errors.NoBrokersAvailable):
            PolymarketKafkaProducer(
                bootstrap_servers="localhost:9092",
                security_protocol="PLAINTEXT",
            )

    @mock.patch("kafka.KafkaProducer")
    def test_connect_generic_exception_raises(self, mock_kafka_cls):
        mock_kafka_cls.side_effect = RuntimeError("unexpected")

        with self.assertRaises(RuntimeError):
            PolymarketKafkaProducer(
                bootstrap_servers="localhost:9092",
                security_protocol="PLAINTEXT",
            )

    @mock.patch("kafka.KafkaProducer")
    def test_publish_kafka_send_error_does_not_raise(self, mock_kafka_cls):
        """publish() catches exceptions after retries are exhausted."""
        mock_producer = mock.MagicMock()
        mock_future = mock.MagicMock()
        mock_future.get.side_effect = kafka.errors.KafkaError("send failed")
        mock_producer.send.return_value = mock_future
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        # Should not raise - publish() catches after retries
        producer.publish("test-topic", b"msg")

    @mock.patch("kafka.KafkaProducer")
    def test_publish_encodes_key_as_utf8(self, mock_kafka_cls):
        mock_producer = mock.MagicMock()
        mock_future = mock.MagicMock()
        mock_metadata = mock.MagicMock()
        mock_metadata.partition = 0
        mock_metadata.offset = 0
        mock_future.get.return_value = mock_metadata
        mock_producer.send.return_value = mock_future
        mock_kafka_cls.return_value = mock_producer

        producer = PolymarketKafkaProducer(
            bootstrap_servers="localhost:9092",
            security_protocol="PLAINTEXT",
        )
        producer.publish("topic", b"data", key="unicode-key-\u00e9")

        call_args = mock_producer.send.call_args
        self.assertEqual(call_args[1]["key"], "unicode-key-\u00e9".encode("utf-8"))


if __name__ == "__main__":
    absltest.main()
