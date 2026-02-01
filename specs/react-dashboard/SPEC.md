# React Dashboard Specification

## Goal

Modern React application for the agent-first trading dashboard, providing real-time visibility into agent signals, reasoning, and tool calls.

## Target Behavior

- Vite-based React 18 application with TypeScript
- Real-time SSE integration for live signal streaming
- Component library: shadcn/ui for consistent styling
- State management: React Query for server state, useState/useReducer for local
- Dark mode by default (match existing dashboard aesthetic)

## Project Structure

```
ui/agent-dashboard/
├── src/
│   ├── components/
│   │   ├── ui/                    # shadcn/ui components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── badge.tsx
│   │   │   └── ...
│   │   ├── SignalStream/          # Live signal feed
│   │   │   ├── SignalStream.tsx
│   │   │   ├── SignalCard.tsx
│   │   │   └── index.ts
│   │   ├── ReasoningPanel/        # Expandable reasoning view
│   │   │   ├── ReasoningPanel.tsx
│   │   │   ├── ToolCallLog.tsx
│   │   │   ├── ScoreBreakdown.tsx
│   │   │   └── index.ts
│   │   ├── ChatInput/             # Ask agent input
│   │   │   ├── ChatInput.tsx
│   │   │   └── index.ts
│   │   ├── ConfidenceGauge/       # D3.js confidence visualization
│   │   │   ├── ConfidenceGauge.tsx
│   │   │   └── index.ts
│   │   ├── FilterBar/             # Signal filters
│   │   │   ├── FilterBar.tsx
│   │   │   └── index.ts
│   │   └── Layout/                # App layout
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── index.ts
│   ├── hooks/
│   │   ├── useAgentStream.ts      # SSE connection management
│   │   ├── useSignals.ts          # Signal state management
│   │   └── useFilters.ts          # Filter state
│   ├── api/
│   │   ├── agent.ts               # REST API client
│   │   └── types.ts               # API type definitions
│   ├── lib/
│   │   ├── utils.ts               # Utility functions
│   │   └── constants.ts           # App constants
│   ├── styles/
│   │   └── globals.css            # Global styles + Tailwind
│   ├── App.tsx                    # Root component
│   ├── main.tsx                   # Entry point
│   └── vite-env.d.ts
├── public/
│   └── favicon.ico
├── .storybook/                    # Storybook configuration
│   ├── main.ts
│   └── preview.ts
├── stories/                       # Component stories
│   ├── SignalCard.stories.tsx
│   └── ...
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── Dockerfile
└── README.md
```

## Key Components

### App.tsx - Main Application

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SignalStream } from './components/SignalStream';
import { ChatInput } from './components/ChatInput';
import { FilterBar } from './components/FilterBar';
import { useAgentStream } from './hooks/useAgentStream';

const queryClient = new QueryClient();

export function App() {
  const { signals, isConnected, reconnect } = useAgentStream();

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-background text-foreground">
        <Header isConnected={isConnected} onReconnect={reconnect} />
        <main className="container mx-auto p-4">
          <ChatInput />
          <FilterBar />
          <SignalStream signals={signals} />
        </main>
      </div>
    </QueryClientProvider>
  );
}
```

### useAgentStream Hook

```tsx
import { useState, useEffect, useCallback, useRef } from 'react';
import { Signal, AgentEvent } from '../api/types';

interface UseAgentStreamResult {
  signals: Signal[];
  events: AgentEvent[];
  isConnected: boolean;
  error: Error | null;
  reconnect: () => void;
}

export function useAgentStream(): UseAgentStreamResult {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<number>();

  const connect = useCallback(() => {
    const url = `${import.meta.env.VITE_API_URL}/api/agent/stream`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    eventSource.addEventListener('signal', (e) => {
      const signal = JSON.parse(e.data) as Signal;
      setSignals((prev) => [signal, ...prev].slice(0, 100));
    });

    eventSource.addEventListener('reasoning', (e) => {
      const event = JSON.parse(e.data) as AgentEvent;
      setEvents((prev) => [...prev, event]);
    });

    eventSource.addEventListener('tool_call', (e) => {
      const event = JSON.parse(e.data) as AgentEvent;
      setEvents((prev) => [...prev, event]);
    });

    eventSource.onerror = () => {
      setIsConnected(false);
      setError(new Error('Connection lost'));
      eventSource.close();

      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
    };
  }, []);

  const reconnect = useCallback(() => {
    eventSourceRef.current?.close();
    clearTimeout(reconnectTimeoutRef.current);
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  return { signals, events, isConnected, error, reconnect };
}
```

## Type Definitions

```tsx
// api/types.ts

export interface Signal {
  signal_id: string;
  symbol: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  opportunity_score: number;
  opportunity_tier: 'HOT' | 'GOOD' | 'NEUTRAL' | 'LOW';
  opportunity_factors: OpportunityFactors;
  strategies_analyzed: number;
  strategies_bullish: number;
  strategies_bearish: number;
  top_strategy: TopStrategy;
  strategy_breakdown: StrategyBreakdown[];
  reasoning: string;
  market_context: MarketContext;
  timestamp: string;
}

export interface OpportunityFactors {
  confidence: { value: number; contribution: number };
  expected_return: { value: number; contribution: number };
  consensus: { value: number; contribution: number };
  volatility: { value: number; contribution: number };
  freshness: { value: number; contribution: number };
}

export interface TopStrategy {
  name: string;
  score: number;
  signal: string;
  parameters: Record<string, unknown>;
}

export interface StrategyBreakdown {
  name: string;
  signal: string;
  score: number;
}

export interface MarketContext {
  current_price: number;
  price_change_1h: number;
  volume_ratio: number;
  volatility_1h: number;
}

export type AgentEvent =
  | { type: 'signal'; data: Signal }
  | { type: 'reasoning'; data: ReasoningStep }
  | { type: 'tool_call'; data: ToolCallEvent }
  | { type: 'tool_result'; data: ToolResultEvent }
  | { type: 'error'; data: ErrorEvent };

export interface ReasoningStep {
  signal_id: string;
  step: number;
  content: string;
  timestamp: string;
}

export interface ToolCallEvent {
  signal_id: string;
  tool_name: string;
  parameters: Record<string, unknown>;
  timestamp: string;
}

export interface ToolResultEvent {
  signal_id: string;
  tool_name: string;
  result: unknown;
  latency_ms: number;
  timestamp: string;
}
```

## Configuration

### vite.config.ts

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8081',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          charts: ['d3'],
        },
      },
    },
  },
});
```

### tailwind.config.js

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: 'hsl(var(--primary))',
        secondary: 'hsl(var(--secondary))',
        accent: 'hsl(var(--accent))',
        muted: 'hsl(var(--muted))',
        destructive: 'hsl(var(--destructive))',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

### package.json

```json
{
  "name": "agent-dashboard",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx",
    "test": "vitest",
    "storybook": "storybook dev -p 6006",
    "build-storybook": "storybook build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.0.0",
    "react-window": "^1.8.10",
    "d3": "^7.8.5",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "class-variance-authority": "^0.7.0",
    "lucide-react": "^0.312.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/d3": "^7.4.3",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.2.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.33",
    "autoprefixer": "^10.4.17",
    "@storybook/react": "^7.6.0",
    "@storybook/react-vite": "^7.6.0",
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^6.19.0"
  }
}
```

### Dockerfile

```dockerfile
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### nginx.conf

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://agent-gateway:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;

        # SSE-specific settings
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

## Environment Variables

```bash
# .env.development
VITE_API_URL=http://localhost:8081

# .env.production
VITE_API_URL=https://api.tradestream.io
```

## Constraints

- TypeScript for type safety throughout
- D3.js for complex visualizations (integrate via refs, not React state)
- Must be containerizable for K8s deployment
- Support dark mode (default) with potential light mode toggle
- Production bundle < 500kb (gzipped)
- Initial load < 2 seconds
- Lighthouse performance score > 80

## Acceptance Criteria

- [ ] `npm run dev` starts development server on port 3000
- [ ] `npm run build` produces production bundle < 500kb
- [ ] Dockerfile builds and runs successfully
- [ ] SSE reconnects automatically on disconnect
- [ ] Components have Storybook stories for visual testing
- [ ] TypeScript strict mode enabled with no errors
- [ ] Dark mode works correctly
- [ ] Responsive on mobile viewports
- [ ] React Query caching works for API calls

## Development Workflow

```bash
# Install dependencies
cd ui/agent-dashboard
npm install

# Start development server
npm run dev

# Run Storybook for component development
npm run storybook

# Build for production
npm run build

# Run tests
npm test

# Lint code
npm run lint
```

## Integration with Existing Dashboard

The new React dashboard will eventually replace the existing vanilla JS dashboard at `ui/strategy-monitor/`. During the transition:

1. Both dashboards will run in parallel
2. New React dashboard accessible at `/agent/` route
3. Feature parity achieved before switching default
4. Existing D3.js visualizations can be ported or wrapped
