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
│   │   │   ├── skeleton.tsx       # Loading state components
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
│   │   ├── ErrorBoundary/         # Error handling
│   │   │   ├── ErrorBoundary.tsx
│   │   │   └── index.ts
│   │   └── Layout/                # App layout
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── index.ts
│   ├── context/
│   │   └── DashboardContext.tsx   # Global UI state
│   ├── hooks/
│   │   ├── useAgentStream.ts      # SSE connection management
│   │   ├── useSignals.ts          # Signal state management
│   │   ├── useDashboard.ts        # Dashboard context hook
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
├── __tests__/                     # Test files
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── tailwind.config.js
├── postcss.config.js
├── Dockerfile
└── README.md
```

## Bundle Size Optimization

To minimize bundle size and achieve the <500kb target:

### D3.js Modular Imports

Instead of importing the full D3 library, use only the required modules:

```tsx
// Bad - imports entire D3 library (~500kb)
import * as d3 from "d3";

// Good - imports only needed modules (~50kb)
import { arc, pie } from "d3-shape";
import { scaleLinear } from "d3-scale";
import { select } from "d3-selection";
import { interpolate } from "d3-interpolate";
```

### Lazy Loading for Heavy Components

The ConfidenceGauge component uses D3.js and should be lazy-loaded:

```tsx
// Lazy load D3-dependent components
const ConfidenceGauge = lazy(() => import("./components/ConfidenceGauge"));
const ReasoningPanel = lazy(() => import("./components/ReasoningPanel"));

// Usage with Suspense
<Suspense fallback={<GaugeSkeleton />}>
  <ConfidenceGauge value={signal.confidence} />
</Suspense>;
```

### Code Splitting Strategy

Update `vite.config.ts` for optimal chunk splitting:

```ts
rollupOptions: {
  output: {
    manualChunks: {
      'react-vendor': ['react', 'react-dom'],
      'query': ['@tanstack/react-query'],
      'd3-charts': ['d3-shape', 'd3-scale', 'd3-selection', 'd3-interpolate'],
    },
  },
},
```

## Error Handling & Loading States

### Error Boundary Implementation

```tsx
// src/components/ErrorBoundary/ErrorBoundary.tsx
import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("Dashboard error:", error, errorInfo);
    // Future: send to error tracking service
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="p-4 bg-destructive/10 border border-destructive rounded-lg">
            <h2 className="text-lg font-semibold text-destructive">
              Something went wrong
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {this.state.error?.message || "An unexpected error occurred"}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-2 text-sm underline"
            >
              Try again
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
```

### Loading State Components

```tsx
// src/components/ui/skeleton.tsx
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse bg-muted rounded", className)} />;
}

// Signal card skeleton for loading states
export function SignalCardSkeleton() {
  return (
    <div className="p-4 border rounded-lg space-y-3">
      <div className="flex justify-between">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-16" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

// Gauge skeleton for lazy-loaded D3 component
export function GaugeSkeleton() {
  return (
    <div className="flex items-center justify-center h-24 w-24">
      <Skeleton className="h-20 w-20 rounded-full" />
    </div>
  );
}
```

## State Management Strategy

### Architecture Overview

State is organized into three tiers:

1. **Server State** (React Query) - API data with caching, refetching, and synchronization
2. **Global UI State** (React Context) - Cross-component state like filters, connection status
3. **Local Component State** (useState/useReducer) - Component-specific UI state

### Dashboard Context for Shared State

```tsx
// src/context/DashboardContext.tsx
import { createContext, useContext, useReducer, ReactNode } from "react";

interface FilterState {
  symbols: string[];
  actions: ("BUY" | "SELL" | "HOLD")[];
  minConfidence: number;
}

interface DashboardState {
  filters: FilterState;
  selectedSignalId: string | null;
  isReasoningPanelOpen: boolean;
  connectionStatus: "connected" | "disconnected" | "reconnecting";
}

type DashboardAction =
  | { type: "SET_FILTERS"; payload: Partial<FilterState> }
  | { type: "SELECT_SIGNAL"; payload: string | null }
  | { type: "TOGGLE_REASONING_PANEL" }
  | {
      type: "SET_CONNECTION_STATUS";
      payload: DashboardState["connectionStatus"];
    };

const initialState: DashboardState = {
  filters: { symbols: [], actions: [], minConfidence: 0 },
  selectedSignalId: null,
  isReasoningPanelOpen: false,
  connectionStatus: "disconnected",
};

function dashboardReducer(
  state: DashboardState,
  action: DashboardAction,
): DashboardState {
  switch (action.type) {
    case "SET_FILTERS":
      return { ...state, filters: { ...state.filters, ...action.payload } };
    case "SELECT_SIGNAL":
      return {
        ...state,
        selectedSignalId: action.payload,
        isReasoningPanelOpen: true,
      };
    case "TOGGLE_REASONING_PANEL":
      return { ...state, isReasoningPanelOpen: !state.isReasoningPanelOpen };
    case "SET_CONNECTION_STATUS":
      return { ...state, connectionStatus: action.payload };
    default:
      return state;
  }
}

const DashboardContext = createContext<{
  state: DashboardState;
  dispatch: React.Dispatch<DashboardAction>;
} | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(dashboardReducer, initialState);
  return (
    <DashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </DashboardContext.Provider>
  );
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return context;
}
```

### When to Use Each Pattern

| State Type          | Pattern              | Examples                                   |
| ------------------- | -------------------- | ------------------------------------------ |
| API data            | React Query          | Signals, historical data, user preferences |
| Cross-component UI  | Context + useReducer | Filters, selected signal, panel visibility |
| Single component    | useState             | Input values, local toggles, hover states  |
| Complex local logic | useReducer           | Multi-step forms, complex interactions     |

## Testing Strategy

### Unit Tests (Vitest)

Unit tests for individual components, hooks, and utilities:

```tsx
// __tests__/unit/hooks/useAgentStream.test.ts
import { renderHook, act } from "@testing-library/react";
import { useAgentStream } from "@/hooks/useAgentStream";

describe("useAgentStream", () => {
  it("initializes with disconnected state", () => {
    const { result } = renderHook(() => useAgentStream());
    expect(result.current.isConnected).toBe(false);
    expect(result.current.signals).toEqual([]);
  });

  it("handles incoming signals", async () => {
    // Mock EventSource and test signal handling
  });

  it("auto-reconnects on connection loss", async () => {
    // Test reconnection logic
  });
});
```

### Integration Tests (Vitest + Testing Library)

Test component interactions and data flow:

```tsx
// __tests__/integration/SignalStream.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardProvider } from "@/context/DashboardContext";
import { SignalStream } from "@/components/SignalStream";

describe("SignalStream integration", () => {
  it("renders signals and allows selection", async () => {
    // Test full signal stream with context and query providers
  });

  it("filters signals based on dashboard context", async () => {
    // Test filter integration
  });
});
```

### End-to-End Tests (Playwright)

Full user journey tests:

```ts
// __tests__/e2e/dashboard.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Dashboard E2E", () => {
  test("displays live signals from SSE stream", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("main")).toBeVisible();
    // Wait for SSE connection indicator
    await expect(page.getByTestId("connection-status")).toHaveText("Connected");
  });

  test("opens reasoning panel on signal click", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("signal-card").first().click();
    await expect(page.getByTestId("reasoning-panel")).toBeVisible();
  });

  test("filters signals by symbol", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("combobox", { name: /symbol/i }).click();
    await page.getByRole("option", { name: "BTCUSDT" }).click();
    // Verify filtered results
  });
});
```

### Test Configuration

```ts
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html"],
      exclude: ["node_modules/", "src/test/"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

### Test Scripts

```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

## Accessibility Requirements

### WCAG 2.1 AA Compliance

The dashboard must meet WCAG 2.1 Level AA standards:

#### Keyboard Navigation

- All interactive elements must be focusable and operable via keyboard
- Logical tab order following visual layout
- Focus indicators visible with sufficient contrast (3:1 ratio minimum)
- Skip links for main content areas

```tsx
// Example: Accessible signal card
<article
  role="article"
  tabIndex={0}
  aria-label={`${signal.symbol} ${signal.action} signal with ${signal.confidence}% confidence`}
  onKeyDown={(e) => e.key === "Enter" && onSelect(signal)}
  className="focus:ring-2 focus:ring-primary focus:outline-none"
>
  {/* Card content */}
</article>
```

#### Screen Reader Support

- Semantic HTML elements (header, main, nav, article)
- ARIA labels for complex widgets
- Live regions for real-time updates

```tsx
// Real-time signal announcements
<div role="status" aria-live="polite" aria-atomic="false" className="sr-only">
  {latestSignal &&
    `New ${latestSignal.action} signal for ${latestSignal.symbol}`}
</div>
```

#### Color & Contrast

- Text contrast ratio minimum 4.5:1 (3:1 for large text)
- Color is not the only means of conveying information
- Support for reduced motion preferences

```tsx
// Respect reduced motion preferences
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

<div className={cn(
  'transition-all',
  prefersReducedMotion ? 'duration-0' : 'duration-300'
)}>
```

#### Focus Management

- Focus trap in modals and panels
- Restore focus after modal close
- Announce dynamic content changes

```tsx
// Focus trap for reasoning panel
import { useFocusTrap } from "@/hooks/useFocusTrap";

export function ReasoningPanel({ isOpen, onClose }) {
  const panelRef = useFocusTrap(isOpen);

  return (
    <aside
      ref={panelRef}
      role="complementary"
      aria-label="Signal reasoning details"
      aria-hidden={!isOpen}
    >
      {/* Panel content */}
    </aside>
  );
}
```

### Accessibility Testing

- Automated: axe-core via @axe-core/playwright
- Manual: Screen reader testing (VoiceOver, NVDA)
- Keyboard-only navigation testing

```ts
// Playwright accessibility test
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("dashboard has no accessibility violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
```

## Key Components

### App.tsx - Main Application

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DashboardProvider } from "./context/DashboardContext";
import { SignalStream } from "./components/SignalStream";
import { ChatInput } from "./components/ChatInput";
import { FilterBar } from "./components/FilterBar";
import { Header } from "./components/Layout/Header";
import { SignalCardSkeleton } from "./components/ui/skeleton";
import { useAgentStream } from "./hooks/useAgentStream";

// Lazy load heavy components
const ReasoningPanel = lazy(() => import("./components/ReasoningPanel"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
    },
  },
});

function DashboardContent() {
  const { signals, isConnected, reconnect } = useAgentStream();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header isConnected={isConnected} onReconnect={reconnect} />
      <main className="container mx-auto p-4" role="main">
        <ChatInput />
        <FilterBar />
        <ErrorBoundary
          fallback={<div role="alert">Failed to load signals</div>}
        >
          <Suspense fallback={<SignalCardSkeleton />}>
            <SignalStream signals={signals} />
          </Suspense>
        </ErrorBoundary>
        <ErrorBoundary>
          <Suspense fallback={null}>
            <ReasoningPanel />
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  );
}

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <DashboardProvider>
          <DashboardContent />
        </DashboardProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
```

### useAgentStream Hook

```tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { Signal, AgentEvent } from "../api/types";

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

    eventSource.addEventListener("signal", (e) => {
      const signal = JSON.parse(e.data) as Signal;
      setSignals((prev) => [signal, ...prev].slice(0, 100));
    });

    eventSource.addEventListener("reasoning", (e) => {
      const event = JSON.parse(e.data) as AgentEvent;
      setEvents((prev) => [...prev, event]);
    });

    eventSource.addEventListener("tool_call", (e) => {
      const event = JSON.parse(e.data) as AgentEvent;
      setEvents((prev) => [...prev, event]);
    });

    eventSource.onerror = () => {
      setIsConnected(false);
      setError(new Error("Connection lost"));
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
  action: "BUY" | "SELL" | "HOLD";
  confidence: number;
  opportunity_score: number;
  opportunity_tier: "HOT" | "GOOD" | "NEUTRAL" | "LOW";
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
  | { type: "signal"; data: Signal }
  | { type: "reasoning"; data: ReasoningStep }
  | { type: "tool_call"; data: ToolCallEvent }
  | { type: "tool_result"; data: ToolResultEvent }
  | { type: "error"; data: ErrorEvent };

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
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8081",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom"],
          query: ["@tanstack/react-query"],
          "d3-charts": [
            "d3-shape",
            "d3-scale",
            "d3-selection",
            "d3-interpolate",
          ],
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
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: "hsl(var(--primary))",
        secondary: "hsl(var(--secondary))",
        accent: "hsl(var(--accent))",
        muted: "hsl(var(--muted))",
        destructive: "hsl(var(--destructive))",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
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
    "test:ui": "vitest --ui",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "storybook": "storybook dev -p 6006",
    "build-storybook": "storybook build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.0.0",
    "react-window": "^1.8.10",
    "d3-shape": "^3.2.0",
    "d3-scale": "^4.0.2",
    "d3-selection": "^3.0.0",
    "d3-interpolate": "^3.0.1",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "class-variance-authority": "^0.7.0",
    "lucide-react": "^0.312.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/d3-shape": "^3.1.6",
    "@types/d3-scale": "^4.0.8",
    "@types/d3-selection": "^3.0.10",
    "@types/d3-interpolate": "^3.0.4",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.2.0",
    "@vitest/ui": "^1.2.0",
    "@vitest/coverage-v8": "^1.2.0",
    "@testing-library/react": "^14.1.0",
    "@testing-library/jest-dom": "^6.2.0",
    "@playwright/test": "^1.41.0",
    "@axe-core/playwright": "^4.8.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.33",
    "autoprefixer": "^10.4.17",
    "@storybook/react": "^7.6.0",
    "@storybook/react-vite": "^7.6.0",
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^6.19.0",
    "eslint-plugin-jsx-a11y": "^6.8.0"
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
- D3.js modular imports for complex visualizations (integrate via refs, not React state)
- Must be containerizable for K8s deployment
- Support dark mode (default) with potential light mode toggle
- Production bundle < 500kb (gzipped)
- Initial load < 2 seconds
- Lighthouse performance score > 80
- WCAG 2.1 AA accessibility compliance

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
- [ ] Error boundaries catch and display component errors gracefully
- [ ] Loading states shown during data fetching and lazy loading
- [ ] Unit test coverage > 80%
- [ ] E2E tests pass for critical user journeys
- [ ] No WCAG 2.1 AA accessibility violations (axe-core)
- [ ] Keyboard navigation works for all interactive elements

## Development Workflow

```bash
# Install dependencies
cd ui/agent-dashboard
npm install

# Start development server
npm run dev

# Run Storybook for component development
npm run storybook

# Run unit tests
npm test

# Run unit tests with UI
npm run test:ui

# Run E2E tests
npm run test:e2e

# Build for production
npm run build

# Lint code
npm run lint
```

## Integration with Existing Dashboard

The new React dashboard will eventually replace the existing vanilla JS dashboard at `ui/strategy-monitor/`. During the transition:

1. Both dashboards will run in parallel
2. New React dashboard accessible at `/agent/` route
3. Feature parity achieved before switching default
4. Existing D3.js visualizations can be ported or wrapped
