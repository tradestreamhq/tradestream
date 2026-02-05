import { Hero } from '../components/Landing/Hero';
import { TrustIndicators } from '../components/Landing/TrustIndicators';
import { HowItWorks } from '../components/Landing/HowItWorks';
import { Disclaimers } from '../components/Landing/Disclaimers';

export function Landing() {
  return (
    <div className="min-h-screen bg-slate-900">
      <Hero />
      <TrustIndicators />
      <HowItWorks />
      <Disclaimers />
    </div>
  );
}
