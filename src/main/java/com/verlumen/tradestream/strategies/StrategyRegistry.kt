package com.verlumen.tradestream.strategies

import com.verlumen.tradestream.strategies.configurable.ConfigurableStrategySpec
import com.verlumen.tradestream.strategies.configurable.StrategyConfig
import com.verlumen.tradestream.strategies.configurable.StrategyConfigLoader
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.util.logging.Level
import java.util.logging.Logger

/**
 * A registry that discovers and loads strategy configurations at runtime from YAML files.
 * This provides string-based strategy lookup as part of the migration from StrategyType enum.
 *
 * The registry is immutable after construction and thread-safe.
 *
 * @property strategies The map of strategy names to their specifications
 */
class StrategyRegistry private constructor(
    private val strategies: Map<String, StrategySpec>
) {
    companion object {
        private val logger = Logger.getLogger(StrategyRegistry::class.java.name)

        /** Default classpath resource path for strategy YAML files. */
        const val DEFAULT_RESOURCE_PATH = "/strategies"

        /**
         * Creates a registry by loading all YAML files from a directory on the filesystem.
         *
         * @param directoryPath The path to the directory containing YAML files
         * @return A new StrategyRegistry with all discovered strategies
         * @throws IOException if the directory cannot be read
         * @throws IllegalStateException if no valid strategies are found
         */
        @JvmStatic
        fun fromDirectory(directoryPath: String): StrategyRegistry {
            val strategies = mutableMapOf<String, StrategySpec>()
            val path = Path.of(directoryPath)

            if (!Files.isDirectory(path)) {
                throw IOException("Not a directory: $directoryPath")
            }

            Files.list(path)
                .filter { Files.isRegularFile(it) }
                .filter { it.fileName.toString().endsWith(".yaml") || it.fileName.toString().endsWith(".yml") }
                .forEach { filePath ->
                    try {
                        val config = StrategyConfigLoader.loadYaml(filePath.toString())
                        val spec = ConfigurableStrategySpec(config).strategySpec
                        val strategyName = config.name

                        if (strategyName.isNullOrBlank()) {
                            logger.warning("Skipping YAML file with no name: ${filePath.fileName}")
                            return@forEach
                        }

                        if (strategies.containsKey(strategyName)) {
                            throw IllegalStateException(
                                "Duplicate strategy name '$strategyName' found in ${filePath.fileName}"
                            )
                        }

                        strategies[strategyName] = spec
                        logger.info("Loaded strategy: $strategyName from ${filePath.fileName}")
                    } catch (e: Exception) {
                        throw IllegalStateException(
                            "Failed to load strategy from ${filePath.fileName}: ${e.message}", e
                        )
                    }
                }

            if (strategies.isEmpty()) {
                throw IllegalStateException("No valid strategies found in directory: $directoryPath")
            }

            logger.info("StrategyRegistry initialized with ${strategies.size} strategies")
            return StrategyRegistry(strategies.toMap())
        }

        /**
         * Creates a registry by loading all YAML files from a classpath resource directory.
         *
         * @param resourcePath The classpath resource path (e.g., "/strategies")
         * @return A new StrategyRegistry with all discovered strategies
         * @throws IllegalStateException if no valid strategies are found
         */
        @JvmStatic
        fun fromClasspath(resourcePath: String = DEFAULT_RESOURCE_PATH): StrategyRegistry {
            val strategies = mutableMapOf<String, StrategySpec>()
            val classLoader = StrategyRegistry::class.java.classLoader

            // Get resource URL to find all files in the directory
            val resourceUrl = classLoader.getResource(resourcePath.removePrefix("/"))
                ?: throw IllegalStateException("Resource path not found: $resourcePath")

            val resourceDir = Path.of(resourceUrl.toURI())

            if (!Files.isDirectory(resourceDir)) {
                throw IllegalStateException("Resource path is not a directory: $resourcePath")
            }

            Files.list(resourceDir)
                .filter { Files.isRegularFile(it) }
                .filter { it.fileName.toString().endsWith(".yaml") || it.fileName.toString().endsWith(".yml") }
                .forEach { filePath ->
                    try {
                        val relativePath = "$resourcePath/${filePath.fileName}"
                        val config = StrategyConfigLoader.loadYamlResource(relativePath)
                        val spec = ConfigurableStrategySpec(config).strategySpec
                        val strategyName = config.name

                        if (strategyName.isNullOrBlank()) {
                            logger.warning("Skipping YAML file with no name: ${filePath.fileName}")
                            return@forEach
                        }

                        if (strategies.containsKey(strategyName)) {
                            throw IllegalStateException(
                                "Duplicate strategy name '$strategyName' found in ${filePath.fileName}"
                            )
                        }

                        strategies[strategyName] = spec
                        logger.info("Loaded strategy: $strategyName from classpath ${filePath.fileName}")
                    } catch (e: Exception) {
                        throw IllegalStateException(
                            "Failed to load strategy from ${filePath.fileName}: ${e.message}", e
                        )
                    }
                }

            if (strategies.isEmpty()) {
                throw IllegalStateException("No valid strategies found in classpath: $resourcePath")
            }

            logger.info("StrategyRegistry initialized with ${strategies.size} strategies from classpath")
            return StrategyRegistry(strategies.toMap())
        }

        /**
         * Creates a registry from a list of pre-loaded StrategyConfig objects.
         *
         * @param configs The list of strategy configurations
         * @return A new StrategyRegistry
         * @throws IllegalStateException if configs is empty or contains duplicates
         */
        @JvmStatic
        fun fromConfigs(configs: List<StrategyConfig>): StrategyRegistry {
            if (configs.isEmpty()) {
                throw IllegalStateException("Cannot create registry from empty config list")
            }

            val strategies = mutableMapOf<String, StrategySpec>()

            for (config in configs) {
                val strategyName = config.name
                    ?: throw IllegalStateException("Strategy config has no name")

                if (strategies.containsKey(strategyName)) {
                    throw IllegalStateException("Duplicate strategy name: $strategyName")
                }

                val spec = ConfigurableStrategySpec(config).strategySpec
                strategies[strategyName] = spec
                logger.fine("Added strategy: $strategyName")
            }

            logger.info("StrategyRegistry initialized with ${strategies.size} strategies from configs")
            return StrategyRegistry(strategies.toMap())
        }

        /**
         * Creates an empty registry. Useful for testing or when no strategies are available.
         *
         * @return An empty StrategyRegistry
         */
        @JvmStatic
        fun empty(): StrategyRegistry = StrategyRegistry(emptyMap())
    }

    /**
     * Gets the StrategySpec for the given strategy name.
     *
     * @param strategyName The name of the strategy (e.g., "MACD_CROSSOVER")
     * @return The StrategySpec for the strategy
     * @throws NoSuchElementException if the strategy is not found
     */
    fun getSpec(strategyName: String): StrategySpec {
        return strategies[strategyName]
            ?: throw NoSuchElementException("Strategy not found: $strategyName")
    }

    /**
     * Gets the StrategySpec for the given strategy name, or null if not found.
     *
     * @param strategyName The name of the strategy
     * @return The StrategySpec, or null if not found
     */
    fun getSpecOrNull(strategyName: String): StrategySpec? = strategies[strategyName]

    /**
     * Checks if a strategy with the given name is registered.
     *
     * @param strategyName The name of the strategy
     * @return true if the strategy exists in the registry
     */
    fun isSupported(strategyName: String): Boolean = strategies.containsKey(strategyName)

    /**
     * Returns a list of all registered strategy names.
     *
     * @return List of strategy names, sorted alphabetically
     */
    fun getSupportedStrategyNames(): List<String> = strategies.keys.sorted()

    /**
     * Returns the number of registered strategies.
     *
     * @return The count of strategies in the registry
     */
    fun size(): Int = strategies.size

    /**
     * Returns all registered strategies as a map.
     *
     * @return An immutable copy of the strategies map
     */
    fun getAllSpecs(): Map<String, StrategySpec> = strategies.toMap()
}
