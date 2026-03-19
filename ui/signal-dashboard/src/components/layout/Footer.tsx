import { Link } from "react-router-dom";

export function Footer() {
  return (
    <footer className="border-t border-slate-700/50 bg-surface py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <div className="text-sm text-slate-500">
            &copy; {new Date().getFullYear()} TradeStream. All rights reserved.
          </div>
          <div className="flex gap-6">
            <Link
              to="/"
              className="text-sm text-slate-500 transition-colors hover:text-slate-300"
            >
              Home
            </Link>
            <a
              href="mailto:support@tradestream.io"
              className="text-sm text-slate-500 transition-colors hover:text-slate-300"
            >
              Support
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
