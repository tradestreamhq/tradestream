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
