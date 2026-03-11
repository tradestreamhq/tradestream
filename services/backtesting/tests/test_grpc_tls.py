"""Tests for gRPC TLS configuration in the backtesting service."""

import os
import tempfile
import unittest
from unittest import mock

from services.backtesting.backtesting_service import create_grpc_server


class TestGrpcTlsConfiguration(unittest.TestCase):
    """Test TLS configuration for the gRPC backtesting server."""

    @mock.patch.dict(os.environ, {}, clear=True)
    @mock.patch("services.backtesting.backtesting_service.BacktestingServicer")
    def test_insecure_port_when_no_tls_env_vars(self, mock_servicer):
        """Server uses insecure port when TLS env vars are not set."""
        # Remove TLS env vars if present
        os.environ.pop("TLS_CERT_PATH", None)
        os.environ.pop("TLS_KEY_PATH", None)

        server = create_grpc_server(50099)
        self.assertIsNotNone(server)
        server.stop(grace=0)

    @mock.patch("services.backtesting.backtesting_service.BacktestingServicer")
    def test_secure_port_when_tls_env_vars_set(self, mock_servicer):
        """Server uses secure port when TLS env vars are set with valid certs."""
        # Generate a self-signed cert for testing
        try:
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID
            import datetime

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                ]
            )
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(
                    datetime.datetime.utcnow() + datetime.timedelta(days=1)
                )
                .sign(key, hashes.SHA256())
            )

            with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_file:
                cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
                cert_path = cert_file.name

            with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as key_file:
                key_file.write(
                    key.private_bytes(
                        serialization.Encoding.PEM,
                        serialization.PrivateFormat.TraditionalOpenSSL,
                        serialization.NoEncryption(),
                    )
                )
                key_path = key_file.name

            with mock.patch.dict(
                os.environ,
                {"TLS_CERT_PATH": cert_path, "TLS_KEY_PATH": key_path},
            ):
                server = create_grpc_server(50098)
                self.assertIsNotNone(server)
                server.stop(grace=0)

            os.unlink(cert_path)
            os.unlink(key_path)

        except ImportError:
            self.skipTest("cryptography library not available for cert generation")

    @mock.patch("services.backtesting.backtesting_service.BacktestingServicer")
    def test_file_not_found_raises(self, mock_servicer):
        """Server raises when TLS env vars point to missing files."""
        with mock.patch.dict(
            os.environ,
            {
                "TLS_CERT_PATH": "/nonexistent/cert.pem",
                "TLS_KEY_PATH": "/nonexistent/key.pem",
            },
        ):
            with self.assertRaises(FileNotFoundError):
                create_grpc_server(50097)


if __name__ == "__main__":
    unittest.main()
