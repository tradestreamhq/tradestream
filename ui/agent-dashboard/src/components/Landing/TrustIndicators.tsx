export function TrustIndicators() {
  const indicators = [
    {
      number: '40,000,000+',
      label: 'Strategies Discovered',
      description: 'Genetic algorithms finding patterns humans miss',
    },
    {
      number: '70+',
      label: 'Strategy Types',
      description: 'RSI, MACD, Bollinger, custom indicators',
    },
    {
      number: '6 months',
      label: 'Forward Testing',
      description: 'Every strategy validated in live markets',
    },
    {
      number: '5-factor',
      label: 'Opportunity Scoring',
      description: 'Confidence, return, consensus, volatility, freshness',
    },
  ];

  return (
    <div className="bg-slate-900 py-16 md:py-24">
      <div className="container mx-auto px-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {indicators.map((indicator, index) => (
            <div
              key={index}
              className="bg-slate-800/50 rounded-lg p-6 text-center"
            >
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">
                {indicator.number}
              </div>
              <div className="text-sm font-medium text-slate-300 mb-2">
                {indicator.label}
              </div>
              <div className="text-xs text-slate-500">
                {indicator.description}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
