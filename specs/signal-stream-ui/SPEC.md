# Signal Stream UI Specification

## Goal

React component displaying live trading signals with expandable reasoning, sorted by opportunity score with visual tier indicators.

## Target Behavior

The SignalStream component is the primary view of the agent dashboard. It displays a scrolling list of signal cards, each showing the symbol, action, confidence, opportunity score, and a summary. Clicking a card expands it to reveal full reasoning, tool calls, and strategy breakdown.

### Primary View

```
+-------------------------------------------------------------+
|  TOP OPPORTUNITIES                         [Ask Agent...]   |
|  [All] [BUY only] [SELL only] [Min score: 60 v]            |
+-------------------------------------------------------------+
|  +-----------------------------------------------------+   |
|  | HOT 87                                              |   |
|  | BUY ETH/USD          12:34:56    Confidence: 82%    |   |
|  | Expected return: +3.2% | 4/5 strategies bullish     |   |
|  | [v Show reasoning]                                  |   |
|  +-----------------------------------------------------+   |
|  +-----------------------------------------------------+   |
|  | GOOD 74                                             |   |
|  | SELL BTC/USD         12:31:22    Confidence: 71%    |   |
|  | Expected return: +2.1% | High volatility detected   |   |
|  | [v Show reasoning]                                  |   |
|  +-----------------------------------------------------+   |
|  +-----------------------------------------------------+   |
|  | NEUTRAL 52                                          |   |
|  | HOLD SOL/USD         12:28:15    Confidence: 65%    |   |
|  | Mixed signals, waiting for confirmation             |   |
|  | [v Show reasoning]                                  |   |
|  +-----------------------------------------------------+   |
+-------------------------------------------------------------+
```

### Expanded Card View

```
+-------------------------------------------------------------+
| HOT OPPORTUNITY SCORE: 87                               [x] |
| BUY ETH/USD                                                 |
+-------------------------------------------------------------+
|                                                             |
| SCORE BREAKDOWN                                             |
| -----------------------------------------------------------+
| Confidence         82%    ########..    +20.5 pts          |
| Expected Return    +3.2%  ##########    +30.0 pts          |
| Strategy Consensus 80%    ########..    +16.0 pts          |
| Volatility         2.1%   #######...    +10.5 pts          |
| Freshness          2m     #########.    +10.0 pts          |
|                                                             |
| TOOL CALLS                                                  |
| -----------------------------------------------------------+
| [tool] get_top_strategies(symbol="ETH/USD", limit=5) 45ms  |
|    -> RSI_REVERSAL (0.89), MACD_CROSS (0.85), ...          |
|                                                             |
| [tool] get_strategy_signals(strategies=[...])        32ms  |
|    -> 4/5 strategies signal BUY                            |
|                                                             |
| [tool] get_volatility(symbol="ETH/USD")              28ms  |
|    -> volatility: 2.1%, atr: 45.2                          |
|                                                             |
| ANALYSIS                                                    |
| -----------------------------------------------------------+
| Strong consensus among top strategies. RSI shows            |
| oversold recovery at 28, MACD just crossed bullish with    |
| histogram expanding. Volume confirms breakout attempt.      |
|                                                             |
| STRATEGY BREAKDOWN                                          |
| -----------------------------------------------------------+
| [ok] RSI_REVERSAL      BUY   0.89   RSI oversold recovery  |
| [ok] MACD_CROSS        BUY   0.85   Bullish crossover      |
| [ok] BOLLINGER_BOUNCE  BUY   0.78   Lower band bounce      |
| [ok] EMA_TREND         BUY   0.72   Above 50 EMA           |
| [x]  VOLUME_BREAKOUT   SELL  0.65   Volume declining       |
|                                                             |
+-------------------------------------------------------------+
```

## Component API

### SignalStream

```tsx
interface SignalStreamProps {
  /** Maximum signals to keep in memory */
  maxSignals?: number;
  /** Filter configuration */
  filters?: SignalFilters;
  /** Callback when signal is clicked */
  onSignalClick?: (signal: Signal) => void;
  /** Auto-scroll to new signals (pauses on hover) */
  autoScroll?: boolean;
}

interface SignalFilters {
  symbols?: string[];
  actions?: ("BUY" | "SELL" | "HOLD")[];
  minConfidence?: number;
  minOpportunityScore?: number;
}

<SignalStream
  maxSignals={100}
  filters={{
    symbols: ["ETH/USD", "BTC/USD"],
    minOpportunityScore: 60,
  }}
  onSignalClick={(signal) => openReasoningPanel(signal)}
  autoScroll={true}
/>;
```

### SignalCard

```tsx
interface SignalCardProps {
  signal: Signal;
  isExpanded: boolean;
  isFocused?: boolean;
  onToggleExpand: () => void;
  events?: AgentEvent[];
}

<SignalCard
  signal={signal}
  isExpanded={expandedId === signal.signal_id}
  isFocused={focusedIndex === index}
  onToggleExpand={() => setExpandedId(signal.signal_id)}
  events={eventsForSignal}
/>;
```

### ScoreBreakdown

```tsx
interface ScoreBreakdownProps {
  factors: OpportunityFactors;
  totalScore: number;
}

<ScoreBreakdown
  factors={signal.opportunity_factors}
  totalScore={signal.opportunity_score}
/>;
```

### ToolCallLog

```tsx
interface ToolCallLogProps {
  events: (ToolCallEvent | ToolResultEvent)[];
}

<ToolCallLog events={toolEvents} />;
```

## Implementation

### SignalStream.tsx

```tsx
import { useState, useMemo, useCallback, useRef, useEffect } from "react";
import { VariableSizeList as List } from "react-window";
import { Signal } from "@/api/types";
import { SignalCard } from "./SignalCard";
import { SignalStreamErrorBoundary } from "./SignalStreamErrorBoundary";
import { useAgentStream } from "@/hooks/useAgentStream";

// Row heights for virtualized list
const COLLAPSED_ROW_HEIGHT = 120;
const EXPANDED_ROW_HEIGHT = 480;

interface SignalStreamProps {
  maxSignals?: number;
  filters?: SignalFilters;
  onSignalClick?: (signal: Signal) => void;
  autoScroll?: boolean;
}

export function SignalStream({
  maxSignals = 100,
  filters = {},
  onSignalClick,
  autoScroll = true,
}: SignalStreamProps) {
  const { signals, events } = useAgentStream();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const listRef = useRef<List>(null);

  // Filter and sort signals
  const filteredSignals = useMemo(() => {
    let result = signals.slice(0, maxSignals);

    if (filters.symbols?.length) {
      result = result.filter((s) => filters.symbols!.includes(s.symbol));
    }
    if (filters.actions?.length) {
      result = result.filter((s) => filters.actions!.includes(s.action));
    }
    if (filters.minConfidence) {
      result = result.filter((s) => s.confidence >= filters.minConfidence!);
    }
    if (filters.minOpportunityScore) {
      result = result.filter(
        (s) => s.opportunity_score >= filters.minOpportunityScore!,
      );
    }

    // Sort by opportunity score (highest first)
    return result.sort((a, b) => b.opportunity_score - a.opportunity_score);
  }, [signals, filters, maxSignals]);

  // Dynamic row height based on expanded state
  const getItemSize = useCallback(
    (index: number) => {
      const signal = filteredSignals[index];
      return signal?.signal_id === expandedId
        ? EXPANDED_ROW_HEIGHT
        : COLLAPSED_ROW_HEIGHT;
    },
    [expandedId, filteredSignals],
  );

  // Reset list measurements when expansion state changes
  useEffect(() => {
    if (listRef.current) {
      listRef.current.resetAfterIndex(0);
    }
  }, [expandedId]);

  // Auto-scroll to top when new signal arrives
  useEffect(() => {
    if (autoScroll && !isHovered && listRef.current) {
      listRef.current.scrollToItem(0);
    }
  }, [signals.length, autoScroll, isHovered]);

  // Get events for a specific signal
  const getEventsForSignal = useCallback(
    (signalId: string) => {
      return events.filter(
        (e) => "signal_id" in e.data && e.data.signal_id === signalId,
      );
    },
    [events],
  );

  // Keyboard navigation handler
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setFocusedIndex((prev) =>
            Math.min(prev + 1, filteredSignals.length - 1),
          );
          break;
        case "ArrowUp":
          event.preventDefault();
          setFocusedIndex((prev) => Math.max(prev - 1, 0));
          break;
        case "Enter":
        case " ":
          event.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < filteredSignals.length) {
            const signal = filteredSignals[focusedIndex];
            setExpandedId(
              expandedId === signal.signal_id ? null : signal.signal_id,
            );
            onSignalClick?.(signal);
          }
          break;
        case "Escape":
          setExpandedId(null);
          break;
      }
    },
    [focusedIndex, filteredSignals, expandedId, onSignalClick],
  );

  // Scroll focused item into view
  useEffect(() => {
    if (focusedIndex >= 0 && listRef.current) {
      listRef.current.scrollToItem(focusedIndex, "smart");
    }
  }, [focusedIndex]);

  const Row = ({
    index,
    style,
  }: {
    index: number;
    style: React.CSSProperties;
  }) => {
    const signal = filteredSignals[index];
    const isExpanded = expandedId === signal.signal_id;
    const isFocused = focusedIndex === index;

    return (
      <div
        style={style}
        role="listitem"
        aria-posinset={index + 1}
        aria-setsize={filteredSignals.length}
      >
        <SignalCard
          signal={signal}
          isExpanded={isExpanded}
          isFocused={isFocused}
          onToggleExpand={() => {
            setExpandedId(isExpanded ? null : signal.signal_id);
            onSignalClick?.(signal);
          }}
          events={getEventsForSignal(signal.signal_id)}
        />
      </div>
    );
  };

  return (
    <SignalStreamErrorBoundary>
      <div
        className="signal-stream"
        role="list"
        aria-label="Trading signals sorted by opportunity score"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <List
          ref={listRef}
          height={600}
          itemCount={filteredSignals.length}
          itemSize={getItemSize}
          width="100%"
        >
          {Row}
        </List>
        {/* Live region for screen reader announcements */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {filteredSignals.length} signals available
        </div>
      </div>
    </SignalStreamErrorBoundary>
  );
}
```

### SignalStreamErrorBoundary.tsx

```tsx
import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class SignalStreamErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("SignalStream error:", error, errorInfo);
    // Report to error tracking service (e.g., Sentry)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div
            className="signal-stream-error rounded-lg border border-destructive bg-destructive/10 p-6"
            role="alert"
            aria-live="assertive"
          >
            <h3 className="mb-2 font-semibold text-destructive">
              Signal Stream Error
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Unable to display trading signals. Please try refreshing the page.
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="rounded bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
            >
              Try Again
            </button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
```

### SignalCard.tsx

```tsx
import { Signal, AgentEvent } from "@/api/types";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { ToolCallLog } from "./ToolCallLog";
import { StrategyBreakdown } from "./StrategyBreakdown";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

interface SignalCardProps {
  signal: Signal;
  isExpanded: boolean;
  isFocused?: boolean;
  onToggleExpand: () => void;
  events?: AgentEvent[];
}

export function SignalCard({
  signal,
  isExpanded,
  isFocused = false,
  onToggleExpand,
  events = [],
}: SignalCardProps) {
  const tierIcon = getTierIcon(signal.opportunity_tier);
  const tierLabel = getTierLabel(signal.opportunity_tier);
  const actionColor = getActionColor(signal.action);

  return (
    <article
      className={cn(
        "rounded-lg border bg-card p-4 transition-all duration-200",
        isExpanded && "ring-2 ring-primary",
        isFocused && "ring-2 ring-ring ring-offset-2",
      )}
      aria-label={`${signal.action} signal for ${signal.symbol} with opportunity score ${signal.opportunity_score}`}
      aria-expanded={isExpanded}
    >
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl" role="img" aria-label={tierLabel}>
            {tierIcon}
          </span>
          <span className="text-lg font-semibold text-muted-foreground">
            {signal.opportunity_score}
          </span>
        </div>
        <time
          className="text-sm text-muted-foreground"
          dateTime={signal.timestamp}
        >
          {formatTime(signal.timestamp)}
        </time>
      </div>

      {/* Signal Info */}
      <div className="mt-2 flex items-center gap-4">
        <span className={cn("text-xl font-bold", actionColor)}>
          <span role="img" aria-label={`${signal.action} action`}>
            {getActionIcon(signal.action)}
          </span>{" "}
          {signal.action}
        </span>
        <span className="text-lg font-medium">{signal.symbol}</span>
        <span className="text-sm text-muted-foreground">
          Confidence: {(signal.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Summary */}
      <p className="mt-2 text-sm text-muted-foreground">
        Expected return: +
        {(signal.opportunity_factors.expected_return.value * 100).toFixed(1)}% |{" "}
        {signal.strategies_bullish}/{signal.strategies_analyzed} strategies
        bullish
      </p>

      {/* Expand Toggle */}
      <button
        onClick={onToggleExpand}
        className="mt-3 flex items-center gap-1 text-sm text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        aria-expanded={isExpanded}
        aria-controls={`signal-details-${signal.signal_id}`}
      >
        {isExpanded ? (
          <>
            <ChevronUp size={16} aria-hidden="true" /> Hide reasoning
          </>
        ) : (
          <>
            <ChevronDown size={16} aria-hidden="true" /> Show reasoning
          </>
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div
          id={`signal-details-${signal.signal_id}`}
          className="mt-4 space-y-6 border-t pt-4"
        >
          <ScoreBreakdown
            factors={signal.opportunity_factors}
            totalScore={signal.opportunity_score}
          />
          <ToolCallLog events={events} />
          <section aria-labelledby={`analysis-${signal.signal_id}`}>
            <h4
              id={`analysis-${signal.signal_id}`}
              className="mb-2 font-semibold"
            >
              Analysis
            </h4>
            <p className="text-sm">{signal.reasoning}</p>
          </section>
          <StrategyBreakdown strategies={signal.strategy_breakdown} />
        </div>
      )}
    </article>
  );
}

function getTierIcon(tier: string): string {
  switch (tier) {
    case "HOT":
      return "🔥";
    case "GOOD":
      return "⭐";
    case "NEUTRAL":
      return "⚪";
    default:
      return "🔹";
  }
}

function getTierLabel(tier: string): string {
  switch (tier) {
    case "HOT":
      return "Hot opportunity";
    case "GOOD":
      return "Good opportunity";
    case "NEUTRAL":
      return "Neutral opportunity";
    default:
      return "Opportunity";
  }
}

function getActionIcon(action: string): string {
  switch (action) {
    case "BUY":
      return "🟢";
    case "SELL":
      return "🔴";
    default:
      return "⚪";
  }
}

function getActionColor(action: string): string {
  switch (action) {
    case "BUY":
      return "text-green-500";
    case "SELL":
      return "text-red-500";
    default:
      return "text-gray-500";
  }
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString();
}
```

### ScoreBreakdown.tsx

```tsx
import { OpportunityFactors } from "@/api/types";

interface ScoreBreakdownProps {
  factors: OpportunityFactors;
  totalScore: number;
}

export function ScoreBreakdown({ factors, totalScore }: ScoreBreakdownProps) {
  return (
    <section aria-labelledby="score-breakdown-heading">
      <h4 id="score-breakdown-heading" className="mb-3 font-semibold">
        Score Breakdown
      </h4>
      <div className="space-y-2" role="list" aria-label="Score factors">
        <FactorRow
          label="Confidence"
          value={`${(factors.confidence.value * 100).toFixed(0)}%`}
          contribution={factors.confidence.contribution}
          maxContribution={25}
        />
        <FactorRow
          label="Expected Return"
          value={`+${(factors.expected_return.value * 100).toFixed(1)}%`}
          contribution={factors.expected_return.contribution}
          maxContribution={30}
        />
        <FactorRow
          label="Strategy Consensus"
          value={`${(factors.consensus.value * 100).toFixed(0)}%`}
          contribution={factors.consensus.contribution}
          maxContribution={20}
        />
        <FactorRow
          label="Volatility"
          value={`${(factors.volatility.value * 100).toFixed(1)}%`}
          contribution={factors.volatility.contribution}
          maxContribution={15}
        />
        <FactorRow
          label="Freshness"
          value={`${factors.freshness.value}m ago`}
          contribution={factors.freshness.contribution}
          maxContribution={10}
        />
        <div className="mt-2 border-t pt-2 text-right font-semibold">
          Total: {totalScore.toFixed(1)} pts
        </div>
      </div>
    </section>
  );
}

function FactorRow({
  label,
  value,
  contribution,
  maxContribution,
}: {
  label: string;
  value: string;
  contribution: number;
  maxContribution: number;
}) {
  const percentage = (contribution / maxContribution) * 100;

  return (
    <div
      className="flex items-center gap-4 text-sm"
      role="listitem"
      aria-label={`${label}: ${value}, contributing ${contribution.toFixed(1)} points`}
    >
      <span className="w-36">{label}</span>
      <span className="w-16 text-right">{value}</span>
      <div className="flex-1">
        <div
          className="h-2 rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label} contribution`}
        >
          <div
            className="h-2 rounded-full bg-primary"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
      <span className="w-20 text-right text-muted-foreground">
        +{contribution.toFixed(1)} pts
      </span>
    </div>
  );
}
```

## Accessibility

### ARIA Labels and Roles

| Element               | Role/Attribute                                     | Purpose                                       |
| --------------------- | -------------------------------------------------- | --------------------------------------------- |
| Signal list container | `role="list"`, `aria-label`                        | Identifies the signal list for screen readers |
| Signal card           | `role="listitem"`, `aria-posinset`, `aria-setsize` | Position within the list                      |
| Signal card article   | `aria-label`, `aria-expanded`                      | Describes signal and expansion state          |
| Expand button         | `aria-expanded`, `aria-controls`                   | Toggle state and controlled element           |
| Progress bars         | `role="progressbar"`, `aria-valuenow`              | Score factor visualization                    |
| Live region           | `role="status"`, `aria-live="polite"`              | Announces signal count changes                |
| Error boundary        | `role="alert"`, `aria-live="assertive"`            | Announces errors immediately                  |

### Keyboard Navigation

| Key               | Action                                  |
| ----------------- | --------------------------------------- |
| `Tab`             | Move focus to signal list               |
| `Arrow Down`      | Move focus to next signal card          |
| `Arrow Up`        | Move focus to previous signal card      |
| `Enter` / `Space` | Toggle expand/collapse for focused card |
| `Escape`          | Collapse any expanded card              |

### Screen Reader Support

- All emoji icons have accessible labels via `role="img"` and `aria-label`
- Time values use semantic `<time>` elements with `dateTime` attribute
- Sections use `aria-labelledby` for proper heading association
- Dynamic content changes announced via live regions

### Focus Management

- Visible focus indicators on all interactive elements (2px ring offset)
- Focus follows keyboard navigation through the list
- Auto-scroll respects focus position with `scrollToItem(index, 'smart')`

## Responsive Design

### Breakpoints

| Breakpoint | Width          | Layout Changes                                |
| ---------- | -------------- | --------------------------------------------- |
| `xs`       | 320px - 479px  | Single column, stacked layout, compact cards  |
| `sm`       | 480px - 639px  | Single column, slightly larger touch targets  |
| `md`       | 640px - 767px  | Optional sidebar visible, comfortable spacing |
| `lg`       | 768px - 1023px | Full sidebar, expanded card details inline    |
| `xl`       | 1024px+        | Maximum content width, optimal reading width  |

### Mobile-Specific Behavior (< 640px)

```tsx
// Responsive styles
const responsiveClasses = {
  container: cn("signal-stream", "px-2 sm:px-4 lg:px-6", "py-2 sm:py-4"),
  card: cn("p-3 sm:p-4", "text-sm sm:text-base"),
  header: cn("flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"),
  signalInfo: cn("flex-wrap gap-2 sm:gap-4", "text-base sm:text-lg"),
  scoreBreakdown: cn(
    // Stack labels and values on mobile
    "flex-col gap-1 sm:flex-row sm:items-center sm:gap-4",
  ),
};
```

### Touch Target Sizing

- Minimum touch target: 44x44px on mobile (WCAG 2.5.5)
- Expand/collapse button: full card width on mobile for easier tapping
- Filter buttons: minimum 48px height on touch devices

### Mobile Optimizations

1. **Reduced motion**: Respects `prefers-reduced-motion` media query
2. **Sticky header**: Filter bar sticks to top on scroll
3. **Swipe gestures**: Optional swipe-to-expand on cards (future enhancement)
4. **Virtual keyboard**: Input fields don't obstruct the view

## Error Handling

### Error Boundary Specifications

The `SignalStreamErrorBoundary` component catches and handles errors in the signal stream:

1. **Caught Errors**:
   - Render errors in SignalStream or child components
   - Invalid signal data causing render failures
   - Missing required props

2. **Error Recovery**:
   - "Try Again" button resets error state
   - Automatic retry with exponential backoff (future enhancement)
   - Preserved scroll position on recovery

3. **Error Reporting**:
   - Console logging in development
   - Integration with error tracking (Sentry) in production
   - Error context includes component stack trace

4. **User Experience**:
   - Clear, non-technical error message
   - Accessible error announcement via `role="alert"`
   - Maintains page layout (prevents layout shift)

### Network Error Handling

```tsx
// In useAgentStream hook
const handleStreamError = (error: Error) => {
  if (error.name === "AbortError") {
    // User navigated away, ignore
    return;
  }

  if (error.message.includes("network")) {
    // Show reconnection UI
    setConnectionState("reconnecting");
    scheduleReconnect();
  } else {
    // Propagate to error boundary
    throw error;
  }
};
```

## Constraints

- React functional components with hooks only
- Uses `useAgentStream()` hook for SSE connection
- Virtualized list for performance (react-window VariableSizeList)
- Responsive on mobile viewports (min-width: 320px)
- Expansion animation < 200ms
- Client-side filtering (instant response)
- Maximum 100 signals in memory
- WCAG 2.1 AA accessibility compliance

## Acceptance Criteria

- [ ] Signals appear within 1s of SSE event
- [ ] Expansion animation completes in < 200ms
- [ ] Filter changes apply within 150ms (debounced for text input)
- [ ] Works on mobile viewport (320px+)
- [ ] Handles 100+ signals without lag (virtualized with VariableSizeList)
- [ ] Auto-scroll pauses on hover
- [ ] Score breakdown shows all 5 factors with progress bars
- [ ] Tool calls display with latency
- [ ] Strategy breakdown shows individual strategy signals
- [ ] Full keyboard navigation support (Arrow keys, Enter, Escape)
- [ ] Screen reader compatible (VoiceOver, NVDA tested)
- [ ] Error boundary catches and displays component failures gracefully

## Storybook Stories

```tsx
// stories/SignalCard.stories.tsx
import type { Meta, StoryObj } from "@storybook/react";
import { SignalCard } from "../src/components/SignalStream/SignalCard";
import { mockSignal, mockEvents } from "./mocks";

const meta: Meta<typeof SignalCard> = {
  title: "Components/SignalCard",
  component: SignalCard,
  parameters: {
    layout: "centered",
  },
};

export default meta;
type Story = StoryObj<typeof SignalCard>;

export const BuySignal: Story = {
  args: {
    signal: mockSignal("BUY", 87),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const SellSignal: Story = {
  args: {
    signal: mockSignal("SELL", 74),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const HoldSignal: Story = {
  args: {
    signal: mockSignal("HOLD", 52),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const Expanded: Story = {
  args: {
    signal: mockSignal("BUY", 87),
    isExpanded: true,
    onToggleExpand: () => {},
    events: mockEvents,
  },
};

export const HotOpportunity: Story = {
  args: {
    signal: mockSignal("BUY", 92),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const Focused: Story = {
  args: {
    signal: mockSignal("BUY", 87),
    isExpanded: false,
    isFocused: true,
    onToggleExpand: () => {},
  },
};

export const MobileView: Story = {
  args: {
    signal: mockSignal("BUY", 87),
    isExpanded: false,
    onToggleExpand: () => {},
  },
  parameters: {
    viewport: { defaultViewport: "mobile1" },
  },
};
```

## Performance Considerations

1. **Virtualization**: Use react-window `VariableSizeList` with `resetAfterIndex()` for dynamic row heights when cards expand/collapse
2. **Memoization**: Memoize filtered/sorted signal list
3. **Event Delegation**: Single click handler on container, not per-card
4. **Debounced Filters**: 150ms debounce for text input filters (symbol search, min score slider); instant for toggle filters (action type buttons)
5. **Lazy Loading**: Load expanded content only when needed
6. **Row Height Caching**: `VariableSizeList` caches computed heights; call `resetAfterIndex(0)` when expansion state changes
