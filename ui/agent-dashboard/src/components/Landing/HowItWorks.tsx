import { Dna, TestTube, Users, TrendingUp } from 'lucide-react';

export function HowItWorks() {
  const steps = [
    {
      icon: Dna,
      title: 'Genetic Discovery',
      description:
        'Our algorithms evolve 40M+ trading strategies using genetic optimization, finding patterns across 70+ indicator combinations',
    },
    {
      icon: TestTube,
      title: 'Rigorous Validation',
      description:
        'Every strategy undergoes 6 months of forward testing. Walk-forward analysis ensures no overfitting to historical data',
    },
    {
      icon: Users,
      title: 'Strategy Consensus',
      description:
        'Signals are generated when top strategies agree. Not one AI opinion—validated consensus from the best performers',
    },
    {
      icon: TrendingUp,
      title: 'Opportunity Scoring',
      description:
        '5-factor scoring ranks opportunities by confidence, expected return, consensus strength, volatility, and freshness',
    },
  ];

  return (
    <div className="bg-slate-800 py-16 md:py-24">
      <div className="container mx-auto px-4">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4">
            How It Works
          </h2>
          <p className="text-xl text-slate-400 max-w-3xl mx-auto">
            From genetic discovery to actionable signals—our scientific approach to trading intelligence
          </p>
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, index) => {
            const Icon = step.icon;
            return (
              <div key={index} className="relative">
                {/* Connector line (desktop only) */}
                {index < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-12 left-full w-full h-0.5 bg-gradient-to-r from-blue-500/50 to-transparent -z-10" />
                )}

                {/* Card */}
                <div className="relative bg-slate-800/50 border border-slate-700/50 rounded-lg p-6 hover:border-blue-500/50 transition-colors">
                  {/* Step number badge */}
                  <div className="absolute -top-3 -left-3 w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold text-sm">
                    {index + 1}
                  </div>

                  {/* Icon */}
                  <div className="mb-4">
                    <Icon className="h-12 w-12 text-blue-400" />
                  </div>

                  {/* Title */}
                  <h3 className="text-xl font-bold text-white mb-3">
                    {step.title}
                  </h3>

                  {/* Description */}
                  <p className="text-sm text-slate-400 leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
