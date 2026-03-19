import { useEffect, useState, useCallback } from "react";
import type {
  IndicatorSpec,
  ConditionSpec,
  IndicatorConfig,
  ConditionConfig,
  UserStrategy,
  BacktestResult,
  ValidationResult,
} from "@/api/strategyBuilder";
import {
  fetchIndicators,
  fetchConditions,
  createStrategy,
  listStrategies,
  deleteStrategy,
  validateStrategy,
  backtestStrategy,
  publishStrategy,
} from "@/api/strategyBuilder";
import { cn, formatPercent } from "@/utils/utils";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function IndicatorPalette({
  indicators: specs,
  onAdd,
}: {
  indicators: IndicatorSpec[];
  onAdd: (spec: IndicatorSpec) => void;
}) {
  const [filter, setFilter] = useState("");
  const categories = [...new Set(specs.map((s) => s.category))];
  const [activeCat, setActiveCat] = useState<string | null>(null);

  const filtered = specs.filter(
    (s) =>
      (!activeCat || s.category === activeCat) &&
      (!filter ||
        s.name.toLowerCase().includes(filter.toLowerCase()) ||
        s.type.toLowerCase().includes(filter.toLowerCase()))
  );

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-300">
        Indicator Palette
      </h3>
      <input
        type="text"
        placeholder="Search indicators..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-3 w-full rounded border border-slate-600 bg-slate-900 px-3 py-1.5 text-sm text-slate-200 placeholder-slate-500 focus:border-brand-500 focus:outline-none"
      />
      <div className="mb-3 flex flex-wrap gap-1">
        <button
          onClick={() => setActiveCat(null)}
          className={cn(
            "rounded px-2 py-0.5 text-xs",
            !activeCat
              ? "bg-brand-500 text-white"
              : "bg-slate-700 text-slate-400 hover:bg-slate-600"
          )}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCat(cat)}
            className={cn(
              "rounded px-2 py-0.5 text-xs capitalize",
              activeCat === cat
                ? "bg-brand-500 text-white"
                : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            )}
          >
            {cat}
          </button>
        ))}
      </div>
      <div className="max-h-64 space-y-1 overflow-y-auto">
        {filtered.map((spec) => (
          <button
            key={spec.type}
            onClick={() => onAdd(spec)}
            className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm hover:bg-slate-700"
          >
            <div>
              <span className="font-medium text-slate-200">{spec.name}</span>
              <span className="ml-2 text-xs text-slate-500">{spec.type}</span>
            </div>
            <span className="text-xs text-brand-400">+ Add</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function IndicatorEditor({
  config,
  spec,
  onChange,
  onRemove,
}: {
  config: IndicatorConfig;
  spec: IndicatorSpec | undefined;
  onChange: (updated: IndicatorConfig) => void;
  onRemove: () => void;
}) {
  return (
    <div className="rounded border border-slate-600 bg-slate-800 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-slate-200">
            {spec?.name || config.type}
          </span>
          <span className="ml-2 text-xs text-slate-500">{config.id}</span>
        </div>
        <button
          onClick={onRemove}
          className="text-xs text-red-400 hover:text-red-300"
        >
          Remove
        </button>
      </div>
      {spec?.params.map((p) => (
        <div key={p.name} className="mb-1 flex items-center gap-2">
          <label className="w-28 text-xs text-slate-400">{p.name}</label>
          <input
            type="number"
            value={config.params[p.name] ?? p.default}
            min={p.min}
            max={p.max}
            step={p.type === "double" ? 0.01 : 1}
            onChange={(e) =>
              onChange({
                ...config,
                params: { ...config.params, [p.name]: Number(e.target.value) },
              })
            }
            className="w-24 rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
          />
          <span className="text-xs text-slate-500">
            ({p.min}-{p.max})
          </span>
        </div>
      ))}
    </div>
  );
}

function ConditionEditor({
  conditions,
  conditionSpecs,
  indicatorIds,
  label,
  onChange,
}: {
  conditions: ConditionConfig[];
  conditionSpecs: ConditionSpec[];
  indicatorIds: string[];
  label: string;
  onChange: (updated: ConditionConfig[]) => void;
}) {
  const addCondition = () => {
    onChange([
      ...conditions,
      {
        type: "CrossedUp",
        indicator: indicatorIds[0] || null,
        params: { reference: indicatorIds[1] || indicatorIds[0] || "" },
      },
    ]);
  };

  const updateCondition = (idx: number, updated: ConditionConfig) => {
    const next = [...conditions];
    next[idx] = updated;
    onChange(next);
  };

  const removeCondition = (idx: number) => {
    onChange(conditions.filter((_, i) => i !== idx));
  };

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-300">{label}</h3>
        <button
          onClick={addCondition}
          className="rounded bg-brand-500/20 px-2 py-0.5 text-xs text-brand-400 hover:bg-brand-500/30"
        >
          + Add Condition
        </button>
      </div>
      <div className="space-y-2">
        {conditions.map((cond, idx) => (
          <div
            key={idx}
            className="flex items-center gap-2 rounded border border-slate-600 bg-slate-800 p-2"
          >
            <select
              value={cond.type}
              onChange={(e) =>
                updateCondition(idx, { ...cond, type: e.target.value })
              }
              className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
            >
              {conditionSpecs.map((cs) => (
                <option key={cs.type} value={cs.type}>
                  {cs.type}
                </option>
              ))}
            </select>
            <select
              value={cond.indicator || ""}
              onChange={(e) =>
                updateCondition(idx, { ...cond, indicator: e.target.value })
              }
              className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
            >
              {indicatorIds.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
            {(cond.type === "CrossedUp" ||
              cond.type === "CrossedDown" ||
              cond.type === "OverIndicator" ||
              cond.type === "UnderIndicator") && (
              <select
                value={(cond.params.reference as string) || ""}
                onChange={(e) =>
                  updateCondition(idx, {
                    ...cond,
                    params: { ...cond.params, reference: e.target.value },
                  })
                }
                className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              >
                {indicatorIds.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            )}
            {(cond.type === "IsRising" || cond.type === "IsFalling") && (
              <input
                type="number"
                value={(cond.params.bars as number) || 5}
                min={1}
                max={100}
                onChange={(e) =>
                  updateCondition(idx, {
                    ...cond,
                    params: { ...cond.params, bars: Number(e.target.value) },
                  })
                }
                className="w-16 rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200"
                placeholder="bars"
              />
            )}
            <button
              onClick={() => removeCondition(idx)}
              className="ml-auto text-xs text-red-400 hover:text-red-300"
            >
              X
            </button>
          </div>
        ))}
        {conditions.length === 0 && (
          <p className="text-xs text-slate-500">
            No conditions yet. Add at least one.
          </p>
        )}
      </div>
    </div>
  );
}

function BacktestPanel({
  result,
  isRunning,
  onRun,
  symbol,
  onSymbolChange,
}: {
  result: BacktestResult | null;
  isRunning: boolean;
  onRun: () => void;
  symbol: string;
  onSymbolChange: (s: string) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="mb-3 text-sm font-semibold text-slate-300">Backtest</h3>
      <div className="mb-3 flex gap-2">
        <input
          type="text"
          value={symbol}
          onChange={(e) => onSymbolChange(e.target.value)}
          placeholder="BTC/USD"
          className="w-32 rounded border border-slate-600 bg-slate-900 px-2 py-1 text-sm text-slate-200"
        />
        <button
          onClick={onRun}
          disabled={isRunning}
          className={cn(
            "rounded px-4 py-1 text-sm font-medium",
            isRunning
              ? "bg-slate-600 text-slate-400"
              : "bg-brand-500 text-white hover:bg-brand-600"
          )}
        >
          {isRunning ? "Running..." : "Run Backtest"}
        </button>
      </div>
      {result && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricCard
            label="Return"
            value={result.total_return_pct}
            format="percent"
          />
          <MetricCard label="Sharpe" value={result.sharpe_ratio} format="number" />
          <MetricCard
            label="Win Rate"
            value={result.win_rate * 100}
            format="percent"
          />
          <MetricCard
            label="Max DD"
            value={result.max_drawdown_pct}
            format="percent"
          />
          <MetricCard
            label="Trades"
            value={result.total_trades}
            format="integer"
          />
          <MetricCard
            label="Candles"
            value={result.candles_analyzed}
            format="integer"
          />
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format: "percent" | "number" | "integer";
}) {
  const isPositive = value >= 0;
  const display =
    format === "percent"
      ? `${isPositive ? "+" : ""}${value.toFixed(2)}%`
      : format === "integer"
        ? String(Math.round(value))
        : value.toFixed(2);

  return (
    <div className="rounded border border-slate-600 bg-slate-900 p-2 text-center">
      <div className="text-xs text-slate-500">{label}</div>
      <div
        className={cn(
          "text-sm font-semibold",
          format === "percent"
            ? isPositive
              ? "text-emerald-400"
              : "text-red-400"
            : "text-slate-200"
        )}
      >
        {display}
      </div>
    </div>
  );
}

function StrategyList({
  strategies,
  onSelect,
  onDelete,
}: {
  strategies: UserStrategy[];
  onSelect: (s: UserStrategy) => void;
  onDelete: (id: string) => void;
}) {
  if (strategies.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No strategies yet. Create your first one above.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {strategies.map((s) => (
        <div
          key={s.id}
          className="flex items-center justify-between rounded border border-slate-700 bg-slate-800 p-3"
        >
          <button
            onClick={() => onSelect(s)}
            className="flex-1 text-left"
          >
            <div className="text-sm font-medium text-slate-200">{s.name}</div>
            <div className="text-xs text-slate-500">
              {s.indicators.length} indicators &middot; v{s.version}
              {s.is_published && (
                <span className="ml-2 text-emerald-400">Published</span>
              )}
            </div>
          </button>
          {s.backtest_results && (
            <div className="mx-4 text-xs">
              <span
                className={cn(
                  "font-semibold",
                  s.backtest_results.total_return_pct >= 0
                    ? "text-emerald-400"
                    : "text-red-400"
                )}
              >
                {s.backtest_results.total_return_pct >= 0 ? "+" : ""}
                {s.backtest_results.total_return_pct.toFixed(2)}%
              </span>
            </div>
          )}
          <button
            onClick={() => onDelete(s.id)}
            className="ml-2 text-xs text-red-400 hover:text-red-300"
          >
            Delete
          </button>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

let idCounter = 0;
function nextId(prefix: string) {
  idCounter += 1;
  return `${prefix}_${idCounter}`;
}

export function StrategyBuilderPage() {
  // Palette data
  const [indicatorSpecs, setIndicatorSpecs] = useState<IndicatorSpec[]>([]);
  const [conditionSpecs, setConditionSpecs] = useState<ConditionSpec[]>([]);

  // Strategy being built
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [indicators, setIndicators] = useState<IndicatorConfig[]>([]);
  const [entryConditions, setEntryConditions] = useState<ConditionConfig[]>([]);
  const [exitConditions, setExitConditions] = useState<ConditionConfig[]>([]);

  // Saved strategies
  const [strategies, setStrategies] = useState<UserStrategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<UserStrategy | null>(
    null
  );

  // Backtest
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(
    null
  );
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [backtestSymbol, setBacktestSymbol] = useState("BTC/USD");

  // Validation
  const [validationResult, setValidationResult] =
    useState<ValidationResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load palette and strategies on mount
  useEffect(() => {
    fetchIndicators()
      .then((res) => setIndicatorSpecs(res.data.map((d) => d.attributes)))
      .catch(console.error);
    fetchConditions()
      .then((res) => setConditionSpecs(res.data.map((d) => d.attributes)))
      .catch(console.error);
    loadStrategies();
  }, []);

  const loadStrategies = useCallback(() => {
    listStrategies()
      .then((res) => setStrategies(res.data.map((d) => d.attributes)))
      .catch(console.error);
  }, []);

  const specMap = Object.fromEntries(
    indicatorSpecs.map((s) => [s.type, s])
  );

  const indicatorIds = indicators.map((i) => i.id);

  const addIndicator = (spec: IndicatorSpec) => {
    const id = nextId(spec.type.toLowerCase());
    const defaultParams: Record<string, number> = {};
    for (const p of spec.params) {
      defaultParams[p.name] = p.default;
    }
    setIndicators([
      ...indicators,
      { id, type: spec.type, input: "close", params: defaultParams },
    ]);
  };

  const handleValidate = async () => {
    if (!name || indicators.length === 0) {
      setError("Name and at least one indicator required");
      return;
    }
    try {
      const res = await validateStrategy({
        name,
        indicators,
        entry_conditions: entryConditions,
        exit_conditions: exitConditions,
      });
      setValidationResult(res.data.attributes);
      setError(null);
    } catch (e: any) {
      setError(e?.error?.message || "Validation failed");
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await createStrategy({
        name,
        description,
        indicators,
        entry_conditions: entryConditions,
        exit_conditions: exitConditions,
      });
      const saved = res.data.attributes;
      setSelectedStrategy(saved);
      loadStrategies();
    } catch (e: any) {
      setError(e?.error?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleBacktest = async () => {
    const strategyId = selectedStrategy?.id;
    if (!strategyId) {
      setError("Save the strategy first before backtesting");
      return;
    }
    setBacktestRunning(true);
    setError(null);
    try {
      const res = await backtestStrategy(strategyId, {
        symbol: backtestSymbol,
      });
      setBacktestResult(res.data.attributes);
      loadStrategies();
    } catch (e: any) {
      setError(e?.error?.message || "Backtest failed");
    } finally {
      setBacktestRunning(false);
    }
  };

  const handlePublish = async () => {
    const strategyId = selectedStrategy?.id;
    if (!strategyId) return;
    setPublishing(true);
    setError(null);
    try {
      await publishStrategy(strategyId, { price: 0 });
      loadStrategies();
    } catch (e: any) {
      setError(e?.error?.message || "Publish failed");
    } finally {
      setPublishing(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteStrategy(id);
      if (selectedStrategy?.id === id) setSelectedStrategy(null);
      loadStrategies();
    } catch (e: any) {
      setError(e?.error?.message || "Delete failed");
    }
  };

  const handleSelectStrategy = (s: UserStrategy) => {
    setSelectedStrategy(s);
    setName(s.name);
    setDescription(s.description);
    setIndicators(s.indicators);
    setEntryConditions(s.entry_conditions);
    setExitConditions(s.exit_conditions);
    setBacktestResult(s.backtest_results);
  };

  const resetBuilder = () => {
    setSelectedStrategy(null);
    setName("");
    setDescription("");
    setIndicators([]);
    setEntryConditions([]);
    setExitConditions([]);
    setBacktestResult(null);
    setValidationResult(null);
    setError(null);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Strategy Builder</h1>
          <p className="text-sm text-slate-400">
            Create custom trading strategies with a visual no-code builder
          </p>
        </div>
        <button
          onClick={resetBuilder}
          className="rounded bg-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-600"
        >
          New Strategy
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Builder Area */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Palette */}
        <div className="lg:col-span-1">
          <IndicatorPalette indicators={indicatorSpecs} onAdd={addIndicator} />
        </div>

        {/* Right: Config */}
        <div className="space-y-4 lg:col-span-2">
          {/* Name & Description */}
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Strategy name"
              className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
            />
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              className="rounded border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
            />
          </div>

          {/* Active Indicators */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-slate-300">
              Indicators ({indicators.length})
            </h3>
            <div className="space-y-2">
              {indicators.map((ind, idx) => (
                <IndicatorEditor
                  key={ind.id}
                  config={ind}
                  spec={specMap[ind.type]}
                  onChange={(updated) => {
                    const next = [...indicators];
                    next[idx] = updated;
                    setIndicators(next);
                  }}
                  onRemove={() =>
                    setIndicators(indicators.filter((_, i) => i !== idx))
                  }
                />
              ))}
              {indicators.length === 0 && (
                <p className="py-4 text-center text-sm text-slate-500">
                  Drag indicators from the palette to get started
                </p>
              )}
            </div>
          </div>

          {/* Entry & Exit Conditions */}
          <ConditionEditor
            conditions={entryConditions}
            conditionSpecs={conditionSpecs}
            indicatorIds={indicatorIds}
            label="Entry Conditions (Buy)"
            onChange={setEntryConditions}
          />
          <ConditionEditor
            conditions={exitConditions}
            conditionSpecs={conditionSpecs}
            indicatorIds={indicatorIds}
            label="Exit Conditions (Sell)"
            onChange={setExitConditions}
          />

          {/* Validation result */}
          {validationResult && (
            <div
              className={cn(
                "rounded border p-3 text-sm",
                validationResult.valid
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-red-500/30 bg-red-500/10 text-red-400"
              )}
            >
              {validationResult.valid
                ? "Strategy config is valid"
                : `${validationResult.errors.length} error(s): ${validationResult.errors.map((e) => e.message).join(", ")}`}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleValidate}
              className="rounded bg-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-600"
            >
              Validate
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Strategy"}
            </button>
            {selectedStrategy && !selectedStrategy.is_published && (
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {publishing ? "Publishing..." : "Publish to Marketplace"}
              </button>
            )}
          </div>

          {/* Backtest */}
          <BacktestPanel
            result={backtestResult}
            isRunning={backtestRunning}
            onRun={handleBacktest}
            symbol={backtestSymbol}
            onSymbolChange={setBacktestSymbol}
          />
        </div>
      </div>

      {/* Saved Strategies */}
      <div>
        <h2 className="mb-3 text-lg font-semibold text-white">
          My Strategies
        </h2>
        <StrategyList
          strategies={strategies}
          onSelect={handleSelectStrategy}
          onDelete={handleDelete}
        />
      </div>
    </div>
  );
}
