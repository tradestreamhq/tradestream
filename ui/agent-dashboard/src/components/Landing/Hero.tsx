import { ArrowRight, Play } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui/button';

export function Hero() {
  return (
    <div className="relative overflow-hidden bg-gradient-to-b from-slate-900 via-slate-900 to-slate-800">
      {/* Background glow effect */}
      <div className="absolute inset-0 bg-blue-500/20 blur-3xl" aria-hidden="true" />

      <div className="relative container mx-auto px-4 py-16 md:py-24 lg:py-32">
        <div className="flex flex-col items-center text-center">
          {/* Badge with ping animation */}
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-800/50 px-4 py-2 text-sm text-slate-300 border border-slate-700/50 mb-8">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            Live signals from 40M+ strategies
          </div>

          {/* Headline with gradient */}
          <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold text-white mb-6 max-w-5xl">
            Trading Signals Backed by{' '}
            <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
              Strategy Consensus
            </span>
          </h1>

          {/* Subheadline */}
          <p className="text-xl text-slate-400 mb-12 max-w-3xl">
            No single AI opinion. TradeStream discovers and validates millions of trading strategies,
            generating signals only when the best performers agree. Genetic algorithms, rigorous testing,
            and social proof built in.
          </p>

          {/* Primary CTAs */}
          <div className="flex flex-col sm:flex-row gap-4 mb-16">
            <Link to="/register">
              <Button size="lg" className="bg-blue-500 hover:bg-blue-600 text-white">
                Start Free
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link to="/dashboard">
              <Button size="lg" variant="outline" className="border-slate-700 text-slate-300 hover:bg-slate-800">
                <Play className="mr-2 h-5 w-5" />
                Try Demo
              </Button>
            </Link>
          </div>

          {/* Social proof metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 w-full max-w-3xl">
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">40M+</div>
              <div className="text-sm text-slate-300 font-medium">Strategies Discovered</div>
            </div>
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">70+</div>
              <div className="text-sm text-slate-300 font-medium">Strategy Types</div>
            </div>
            <div className="text-center">
              <div className="text-3xl md:text-4xl font-bold text-white mb-2">6mo</div>
              <div className="text-sm text-slate-300 font-medium">Forward Testing</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
