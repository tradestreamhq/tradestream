package com.verlumen.tradestream.backtestingservice

import com.google.common.flogger.FluentLogger
import com.google.inject.Guice
import com.google.inject.Inject
import com.verlumen.tradestream.backtestingservice.BacktestingGrpcService
import com.verlumen.tradestream.backtestingservice.BacktestingServiceModule
import io.grpc.Server
import io.grpc.ServerBuilder
import io.grpc.protobuf.services.HealthStatusManager
import io.grpc.protobuf.services.ProtoReflectionService
import net.sourceforge.argparse4j.ArgumentParsers
import net.sourceforge.argparse4j.inf.ArgumentParserException
import java.util.concurrent.TimeUnit

/**
 * Standalone gRPC server for the Backtesting Service.
 *
 * This server provides backtesting functionality via gRPC, enabling the
 * Strategy Discovery Pipeline (running on Java 17/Flink) to offload
 * backtesting to this service (capable of running on Java 21 with ta4j 0.22+).
 *
 * Features:
 * - Single backtest execution
 * - Batch backtest for GA fitness evaluation
 * - Health checking for Kubernetes readiness/liveness probes
 * - gRPC reflection for debugging with grpcurl
 */
class BacktestServiceServer
    @Inject
    constructor(
        private val backtestingService: BacktestingGrpcService,
    ) {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val DEFAULT_PORT = 50051

            @JvmStatic
            fun main(args: Array<String>) {
                val parser =
                    ArgumentParsers
                        .newFor("BacktestServiceServer")
                        .build()
                        .defaultHelp(true)
                        .description("Backtesting Service gRPC Server")

                parser
                    .addArgument("--port")
                    .type(Integer::class.java)
                    .setDefault(DEFAULT_PORT)
                    .help("Port to listen on")

                try {
                    val ns = parser.parseArgs(args)
                    val port = ns.getInt("port")

                    val injector = Guice.createInjector(BacktestingServiceModule())
                    val server = injector.getInstance(BacktestServiceServer::class.java)
                    server.start(port)
                    server.blockUntilShutdown()
                } catch (e: ArgumentParserException) {
                    parser.handleError(e)
                    System.exit(1)
                }
            }
        }

        private var server: Server? = null
        private val healthStatusManager = HealthStatusManager()

        /**
         * Starts the gRPC server on the specified port.
         */
        fun start(port: Int) {
            server =
                ServerBuilder
                    .forPort(port)
                    .addService(backtestingService)
                    .addService(healthStatusManager.healthService)
                    .addService(ProtoReflectionService.newInstance())
                    .build()
                    .start()

            logger.atInfo().log("Backtesting Service started on port %d", port)

            // Mark service as serving
            healthStatusManager.setStatus(
                "verlumen.tradestream.backtesting.BacktestingService",
                io.grpc.health.v1.HealthCheckResponse.ServingStatus.SERVING,
            )

            // Add shutdown hook
            Runtime.getRuntime().addShutdownHook(
                Thread {
                    logger.atInfo().log("Shutting down gRPC server due to JVM shutdown")
                    stop()
                },
            )
        }

        /**
         * Stops the gRPC server gracefully.
         */
        fun stop() {
            server?.let { s ->
                logger.atInfo().log("Initiating graceful shutdown")

                // Mark service as not serving
                healthStatusManager.setStatus(
                    "verlumen.tradestream.backtesting.BacktestingService",
                    io.grpc.health.v1.HealthCheckResponse.ServingStatus.NOT_SERVING,
                )

                // Shutdown the service
                backtestingService.shutdown()

                // Shutdown the server
                s.shutdown()
                try {
                    if (!s.awaitTermination(30, TimeUnit.SECONDS)) {
                        logger.atWarning().log("Server did not terminate in time, forcing shutdown")
                        s.shutdownNow()
                        if (!s.awaitTermination(5, TimeUnit.SECONDS)) {
                            logger.atSevere().log("Server did not terminate after force shutdown")
                        }
                    }
                } catch (e: InterruptedException) {
                    logger.atWarning().log("Shutdown interrupted")
                    s.shutdownNow()
                    Thread.currentThread().interrupt()
                }

                logger.atInfo().log("Server shutdown complete")
            }
        }

        /**
         * Blocks until the server is terminated.
         */
        fun blockUntilShutdown() {
            server?.awaitTermination()
        }
    }
