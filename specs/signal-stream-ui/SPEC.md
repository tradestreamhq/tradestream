# Signal Stream UI Specification

## Goal

React component displaying live trading signals with expandable reasoning, sorted by opportunity score with visual tier indicators.

## Target Behavior

The SignalStream component is the primary view of the agent dashboard. It displays a scrolling list of signal cards, each showing the symbol, action, confidence, opportunity score, and a summary. Clicking a card expands it to reveal full reasoning, tool calls, and strategy breakdown.

### Primary View

```
┌─────────────────────────────────────────────────────────────┐
│  TOP OPPORTUNITIES                         [Ask Agent...]   │
│  [All] [BUY only] [SELL only] [Min score: 60 ▼]            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔥 87                                               │   │
│  │ 🟢 BUY ETH/USD         12:34:56    Confidence: 82%  │   │
│  │ Expected return: +3.2% | 4/5 strategies bullish     │   │
│  │ [▼ Show reasoning]                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⭐ 74                                               │   │
│  │ 🔴 SELL BTC/USD        12:31:22    Confidence: 71%  │   │
│  │ Expected return: +2.1% | High volatility detected   │   │
│  │ [▼ Show reasoning]                                   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⚪ 52                                               │   │
│  │ ⚪ HOLD SOL/USD        12:28:15    Confidence: 65%  │   │
│  │ Mixed signals, waiting for confirmation             │   │
│  │ [▼ Show reasoning]                                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Expanded Card View

```
┌─────────────────────────────────────────────────────────────┐
│ 🔥 OPPORTUNITY SCORE: 87                              [×]  │
│ 🟢 BUY ETH/USD                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ SCORE BREAKDOWN                                            │
│ ─────────────────────────────────────────────────────────  │
│ Confidence         82%    ████████░░    +20.5 pts         │
│ Expected Return    +3.2%  ██████████    +30.0 pts         │
│ Strategy Consensus 80%    ████████░░    +16.0 pts         │
│ Volatility         2.1%   ███████░░░    +10.5 pts         │
│ Freshness          2m     █████████░    +10.0 pts         │
│                                                             │
│ TOOL CALLS                                                 │
│ ─────────────────────────────────────────────────────────  │
│ 🔧 get_top_strategies(symbol="ETH/USD", limit=5)   45ms   │
│    → RSI_REVERSAL (0.89), MACD_CROSS (0.85), ...          │
│                                                             │
│ 🔧 get_strategy_signals(strategies=[...])          32ms   │
│    → 4/5 strategies signal BUY                            │
│                                                             │
│ 🔧 get_volatility(symbol="ETH/USD")                28ms   │
│    → volatility: 2.1%, atr: 45.2                          │
│                                                             │
│ ANALYSIS                                                   │
│ ─────────────────────────────────────────────────────────  │
│ Strong consensus among top strategies. RSI shows           │
│ oversold recovery at 28, MACD just crossed bullish with   │
│ histogram expanding. Volume confirms breakout attempt.     │
│                                                             │
│ STRATEGY BREAKDOWN                                         │
│ ─────────────────────────────────────────────────────────  │
│ ✅ RSI_REVERSAL      BUY   0.89   RSI oversold recovery   │
│ ✅ MACD_CROSS        BUY   0.85   Bullish crossover       │
│ ✅ BOLLINGER_BOUNCE  BUY   0.78   Lower band bounce       │
│ ✅ EMA_TREND         BUY   0.72   Above 50 EMA            │
│ ❌ VOLUME_BREAKOUT   SELL  0.65   Volume declining        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
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
  actions?: ('BUY' | 'SELL' | 'HOLD')[];
  minConfidence?: number;
  minOpportunityScore?: number;
}

<SignalStream
  maxSignals={100}
  filters={{
    symbols: ['ETH/USD', 'BTC/USD'],
    minOpportunityScore: 60
  }}
  onSignalClick={(signal) => openReasoningPanel(signal)}
  autoScroll={true}
/>
```

### SignalCard

```tsx
interface SignalCardProps {
  signal: Signal;
  isExpanded: boolean;
  onToggleExpand: () => void;
  events?: AgentEvent[];
}

<SignalCard
  signal={signal}
  isExpanded={expandedId === signal.signal_id}
  onToggleExpand={() => setExpandedId(signal.signal_id)}
  events={eventsForSignal}
/>
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
/>
```

### ToolCallLog

```tsx
interface ToolCallLogProps {
  events: (ToolCallEvent | ToolResultEvent)[];
}

<ToolCallLog events={toolEvents} />
```

## Implementation

### SignalStream.tsx

```tsx
import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { FixedSizeList as List } from 'react-window';
import { Signal } from '@/api/types';
import { SignalCard } from './SignalCard';
import { useAgentStream } from '@/hooks/useAgentStream';

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
        (s) => s.opportunity_score >= filters.minOpportunityScore!
      );
    }

    // Sort by opportunity score (highest first)
    return result.sort((a, b) => b.opportunity_score - a.opportunity_score);
  }, [signals, filters, maxSignals]);

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
        (e) => 'signal_id' in e.data && e.data.signal_id === signalId
      );
    },
    [events]
  );

  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const signal = filteredSignals[index];
    return (
      <div style={style}>
        <SignalCard
          signal={signal}
          isExpanded={expandedId === signal.signal_id}
          onToggleExpand={() => {
            setExpandedId(
              expandedId === signal.signal_id ? null : signal.signal_id
            );
            onSignalClick?.(signal);
          }}
          events={getEventsForSignal(signal.signal_id)}
        />
      </div>
    );
  };

  return (
    <div
      className="signal-stream"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <List
        ref={listRef}
        height={600}
        itemCount={filteredSignals.length}
        itemSize={expandedId ? 400 : 120}
        width="100%"
      >
        {Row}
      </List>
    </div>
  );
}
```

### SignalCard.tsx

```tsx
import { Signal, AgentEvent } from '@/api/types';
import { ScoreBreakdown } from './ScoreBreakdown';
import { ToolCallLog } from './ToolCallLog';
import { StrategyBreakdown } from './StrategyBreakdown';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface SignalCardProps {
  signal: Signal;
  isExpanded: boolean;
  onToggleExpand: () => void;
  events?: AgentEvent[];
}

export function SignalCard({
  signal,
  isExpanded,
  onToggleExpand,
  events = [],
}: SignalCardProps) {
  const tierIcon = getTierIcon(signal.opportunity_tier);
  const actionColor = getActionColor(signal.action);

  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-4 transition-all duration-200',
        isExpanded && 'ring-2 ring-primary'
      )}
    >
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{tierIcon}</span>
          <span className="text-lg font-semibold text-muted-foreground">
            {signal.opportunity_score}
          </span>
        </div>
        <span className="text-sm text-muted-foreground">
          {formatTime(signal.timestamp)}
        </span>
      </div>

      {/* Signal Info */}
      <div className="mt-2 flex items-center gap-4">
        <span className={cn('text-xl font-bold', actionColor)}>
          {getActionIcon(signal.action)} {signal.action}
        </span>
        <span className="text-lg font-medium">{signal.symbol}</span>
        <span className="text-sm text-muted-foreground">
          Confidence: {(signal.confidence * 100).toFixed(0)}%
        </span>
      </div>

      {/* Summary */}
      <p className="mt-2 text-sm text-muted-foreground">
        Expected return: +{(signal.opportunity_factors.expected_return.value * 100).toFixed(1)}% |{' '}
        {signal.strategies_bullish}/{signal.strategies_analyzed} strategies bullish
      </p>

      {/* Expand Toggle */}
      <button
        onClick={onToggleExpand}
        className="mt-3 flex items-center gap-1 text-sm text-primary hover:underline"
      >
        {isExpanded ? (
          <>
            <ChevronUp size={16} /> Hide reasoning
          </>
        ) : (
          <>
            <ChevronDown size={16} /> Show reasoning
          </>
        )}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="mt-4 space-y-6 border-t pt-4">
          <ScoreBreakdown
            factors={signal.opportunity_factors}
            totalScore={signal.opportunity_score}
          />
          <ToolCallLog events={events} />
          <div>
            <h4 className="mb-2 font-semibold">Analysis</h4>
            <p className="text-sm">{signal.reasoning}</p>
          </div>
          <StrategyBreakdown strategies={signal.strategy_breakdown} />
        </div>
      )}
    </div>
  );
}

function getTierIcon(tier: string): string {
  switch (tier) {
    case 'HOT': return '🔥';
    case 'GOOD': return '⭐';
    case 'NEUTRAL': return '⚪';
    default: return '🔹';
  }
}

function getActionIcon(action: string): string {
  switch (action) {
    case 'BUY': return '🟢';
    case 'SELL': return '🔴';
    default: return '⚪';
  }
}

function getActionColor(action: string): string {
  switch (action) {
    case 'BUY': return 'text-green-500';
    case 'SELL': return 'text-red-500';
    default: return 'text-gray-500';
  }
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString();
}
```

### ScoreBreakdown.tsx

```tsx
import { OpportunityFactors } from '@/api/types';

interface ScoreBreakdownProps {
  factors: OpportunityFactors;
  totalScore: number;
}

export function ScoreBreakdown({ factors, totalScore }: ScoreBreakdownProps) {
  return (
    <div>
      <h4 className="mb-3 font-semibold">Score Breakdown</h4>
      <div className="space-y-2">
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
    </div>
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
    <div className="flex items-center gap-4 text-sm">
      <span className="w-36">{label}</span>
      <span className="w-16 text-right">{value}</span>
      <div className="flex-1">
        <div className="h-2 rounded-full bg-muted">
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

## Constraints

- React functional components with hooks only
- Uses `useAgentStream()` hook for SSE connection
- Virtualized list for performance (react-window)
- Responsive on mobile viewports (min-width: 320px)
- Expansion animation < 200ms
- Client-side filtering (instant response)
- Maximum 100 signals in memory

## Acceptance Criteria

- [ ] Signals appear within 1s of SSE event
- [ ] Expansion animation completes in < 200ms
- [ ] Filter changes are instant (client-side)
- [ ] Works on mobile viewport (320px+)
- [ ] Handles 100+ signals without lag (virtualized)
- [ ] Auto-scroll pauses on hover
- [ ] Score breakdown shows all 5 factors with progress bars
- [ ] Tool calls display with latency
- [ ] Strategy breakdown shows individual strategy signals

## Storybook Stories

```tsx
// stories/SignalCard.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { SignalCard } from '../src/components/SignalStream/SignalCard';
import { mockSignal, mockEvents } from './mocks';

const meta: Meta<typeof SignalCard> = {
  title: 'Components/SignalCard',
  component: SignalCard,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof SignalCard>;

export const BuySignal: Story = {
  args: {
    signal: mockSignal('BUY', 87),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const SellSignal: Story = {
  args: {
    signal: mockSignal('SELL', 74),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const HoldSignal: Story = {
  args: {
    signal: mockSignal('HOLD', 52),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};

export const Expanded: Story = {
  args: {
    signal: mockSignal('BUY', 87),
    isExpanded: true,
    onToggleExpand: () => {},
    events: mockEvents,
  },
};

export const HotOpportunity: Story = {
  args: {
    signal: mockSignal('BUY', 92),
    isExpanded: false,
    onToggleExpand: () => {},
  },
};
```

## Performance Considerations

1. **Virtualization**: Use react-window to render only visible items
2. **Memoization**: Memoize filtered/sorted signal list
3. **Event Delegation**: Single click handler on container, not per-card
4. **Debounced Filters**: Debounce filter changes if typing involved
5. **Lazy Loading**: Load expanded content only when needed
