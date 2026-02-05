export function Disclaimers() {
  const disclaimers = [
    {
      title: 'Risk Disclosure',
      content:
        'Trading stocks, options, futures, and other financial instruments involves substantial risk of loss and is not suitable for every investor. Past performance is not indicative of future results.',
    },
    {
      title: 'No Guarantees',
      content:
        'TradeStream does not guarantee profits or protection from losses. All trading decisions are made at your own risk. No strategy can guarantee success in all market conditions.',
    },
    {
      title: 'Do Your Own Research',
      content:
        'Signals and information provided by TradeStream are for informational purposes only. Conduct your own research and consult with qualified financial advisors before making investment decisions.',
    },
  ];

  return (
    <div className="bg-slate-900 border-t border-slate-800 py-12">
      <div className="container mx-auto px-4">
        <div className="space-y-4">
          {disclaimers.map((disclaimer, index) => (
            <div key={index} className="text-xs text-slate-500">
              <span className="font-bold">{disclaimer.title}:</span>{' '}
              {disclaimer.content}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
