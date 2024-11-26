import com.google.auto.value.AutoValue;

@AutoValue
abstract class CoinMarketCapConfig {
    static CoinMarketCapConfig create(int topN, String apiKey) {
        return new AutoValue_CoinMarketCapConfig(topN, apiKey);
    }
    
    abstract int topN();
    abstract String apiKey();
}
