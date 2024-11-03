# TradeStream

TradeStream is an algorithmic trading platform designed to leverage real-time data streams and advanced trading infrastructure. This initial version deploys the TradeStream platform, which includes Kafka configured in KRaft mode (Zookeeper-less).

## Overview

- **Platform Components**: Includes a Kafka setup in KRaft mode, eliminating the need for Zookeeper.
- **Deployment**: Managed using Helm charts on Kubernetes.
- **CI/CD Pipeline**: GitHub Actions workflow ensures that the TradeStream chart is tested on Minikube.

## Installation

To deploy the **TradeStream** platform locally on a Kubernetes cluster:

1. Ensure `kubectl` and `helm` are installed.
2. Run the following command:

```bash
helm install my-tradestream charts/tradestream --namespace tradestream-namespace --create-namespace
```

This command deploys the entire **TradeStream** platform, including Kafka configured in KRaft mode, into the `tradestream-namespace`.

## CI/CD Pipeline

The GitHub Actions workflow for this repository:

- Sets up Minikube and Helm.
- Installs the `tradestream` chart to verify its deployment.
- Checks that all pods are running correctly using `kubectl`.

## TODOs

- [ ] Add more Helm charts for additional components of the TradeStream platform.
- [ ] Enhance resource requests and limits for production-ready deployments.
- [ ] Integrate monitoring and logging for better observability.
- [ ] Expand the CI pipeline to include functional and integration tests.

## Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request to help improve the project.
