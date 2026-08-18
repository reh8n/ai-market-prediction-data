import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Annotation,
  Badge,
  BarChart,
  Button,
  DataTable,
  Input,
  SketchPanel,
  StatBlock,
} from "../design-system";
import {
  api,
  type Instrument,
  type InstrumentDetail,
  type PriceBar,
} from "../api";
import { PageHead } from "./AppShell";

function pct(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function money(value: number | null | undefined) {
  if (value == null) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

/** Monthly closes, so a year of daily bars fits the outline-bar chart. */
function monthlyCloses(bars: PriceBar[], count = 12) {
  const byMonth = new Map<string, PriceBar>();
  for (const bar of bars) byMonth.set(bar.day.slice(0, 7), bar);
  return [...byMonth.entries()]
    .slice(-count)
    .map(([month, bar]) => ({ label: month, value: Number(bar.close.toFixed(2)) }));
}

interface Props {
  onNotify: (title: string, body: string, tone: "info" | "alert") => void;
}

export default function MarketScreen({ onNotify }: Props) {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [detail, setDetail] = useState<InstrumentDetail | null>(null);
  const [ticker, setTicker] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      setInstruments(await api.listInstruments());
    } catch (err) {
      onNotify("Instrument list failed", String(err), "alert");
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const open = async (symbol: string) => {
    try {
      setDetail(await api.getInstrument(symbol));
    } catch (err) {
      onNotify("Instrument unavailable", String(err), "alert");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;
    setBusy(true);
    try {
      await api.syncInstrument(symbol);
      setTicker("");
      onNotify(
        "Sync queued",
        `${symbol} · pulling quote, daily bars and SEC filings`,
        "info",
      );
      // The sync runs in the background; give it a beat before re-reading.
      setTimeout(() => void refresh(), 4000);
    } catch (err) {
      onNotify("Sync failed", String(err), "alert");
    } finally {
      setBusy(false);
    }
  };

  const chart = useMemo(
    () => (detail ? monthlyCloses(detail.bars) : []),
    [detail],
  );

  // Filed revenue by fiscal year, the fundamentals side of the comparison.
  const revenueSeries = useMemo(() => {
    if (!detail) return [];
    return detail.financials
      .filter((f) => f.metric === "revenue" && f.form === "10-K")
      .sort((a, b) => a.period_end.localeCompare(b.period_end))
      .slice(-6)
      .map((f) => ({
        label: f.period_end.slice(0, 7),
        value: Number((f.value / 1e9).toFixed(2)),
      }));
  }, [detail]);

  return (
    <>
      <PageHead
        overline="Market // Price against filings"
        title={detail ? `${detail.name ?? detail.ticker}` : "Market Instruments"}
        right={
          detail ? (
            <Button variant="secondary" onClick={() => setDetail(null)}>
              ← Instruments
            </Button>
          ) : undefined
        }
      />

      {!detail && (
        <div className="split">
          <div className="stack">
            <SketchPanel overline="Instruments // Synced securities" tilt={false}>
              <DataTable
                rows={instruments}
                onRowClick={(r) => open(r.ticker)}
                columns={[
                  { key: "ticker", label: "Ticker", strong: true },
                  { key: "name", label: "Name", render: (r) => r.name || "—" },
                  { key: "sector", label: "Sector", render: (r) => r.sector || "—" },
                  {
                    key: "market_cap",
                    label: "Mkt cap",
                    align: "right",
                    render: (r) => money(r.market_cap),
                  },
                  {
                    key: "cik",
                    label: "SEC",
                    render: (r) =>
                      r.financials_synced_at ? (
                        <Badge tone="success">filed</Badge>
                      ) : (
                        <Badge>none</Badge>
                      ),
                  },
                ]}
                empty="No instruments synced yet"
              />
              <div
                style={{
                  marginTop: "var(--space-4)",
                  fontSize: "var(--size-micro)",
                  letterSpacing: "var(--track-label)",
                  textTransform: "uppercase",
                  color: "var(--text-faint)",
                }}
              >
                {instruments.length} instruments · prices yfinance · financials sec
                edgar
              </div>
            </SketchPanel>
          </div>

          <div className="stack">
            <SketchPanel overline="Sync // Add instrument" tilt={false}>
              <form onSubmit={submit}>
                <Input
                  id="ticker"
                  label="Ticker"
                  hint="us listings"
                  placeholder="AAPL"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                />
                <div style={{ marginTop: "var(--space-4)" }}>
                  <Button type="submit" disabled={busy || !ticker.trim()}>
                    {busy ? "Queuing…" : "Sync instrument"}
                  </Button>
                </div>
              </form>
              <div
                style={{
                  marginTop: "var(--space-5)",
                  paddingTop: "var(--space-4)",
                  borderTop: "1px solid var(--border-hairline)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                Pulls 5 years of daily bars plus every 10-K and 10-Q figure filed
                with the SEC. Neither source needs an API key.
              </div>
              <div style={{ marginTop: "var(--space-4)" }}>
                <Annotation arrow="↘">
                  edgar is what the company is — price is what the market thinks
                </Annotation>
              </div>
            </SketchPanel>
          </div>
        </div>
      )}

      {detail && (
        <div className="stack">
          <SketchPanel overline="Instrument // Market record" tilt={false}>
            <div
              style={{
                display: "flex",
                gap: "var(--space-4)",
                flexWrap: "wrap",
                marginBottom: "var(--space-5)",
              }}
            >
              <Badge tone="ink">{detail.ticker}</Badge>
              {detail.sector && <Badge>{detail.sector}</Badge>}
              {detail.exchange && (
                <span
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-muted)",
                  }}
                >
                  {detail.exchange}
                </span>
              )}
              {detail.cik && (
                <a
                  href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${detail.cik}&type=10-K`}
                  target="_blank"
                  rel="noreferrer"
                >
                  sec filings ↗
                </a>
              )}
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "var(--space-6)",
              }}
            >
              <StatBlock label="1M return" value={pct(detail.return_1m)} size="sm" />
              <StatBlock label="1Y return" value={pct(detail.return_1y)} size="sm" />
              <StatBlock
                label="Volatility"
                value={pct(detail.volatility)}
                size="sm"
                caption="Annualized"
              />
              <StatBlock
                label="Revenue growth"
                value={pct(detail.revenue_growth)}
                size="sm"
                caption="Latest filed year"
              />
            </div>
          </SketchPanel>

          <div className="split-even">
            <SketchPanel
              overline="Market // Monthly close"
              title="Price Action"
              tilt={false}
            >
              {chart.length ? (
                <BarChart height={200} data={chart} labelHeight={64} />
              ) : (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No price bars stored.
                </div>
              )}
            </SketchPanel>

            <SketchPanel
              overline="Filings // Revenue by year"
              title="Reported Revenue"
              tilt={false}
            >
              {revenueSeries.length ? (
                <BarChart
                  height={200}
                  data={revenueSeries}
                  yUnit="B"
                  labelHeight={64}
                />
              ) : (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No SEC filings stored for this instrument.
                </div>
              )}
            </SketchPanel>
          </div>

          <SketchPanel
            overline={`Fundamentals // Filed ${detail.latest_period ?? "—"}`}
            title="Latest Annual Figures"
            tilt={false}
          >
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: "var(--space-6)",
              }}
            >
              {Object.entries(detail.latest_metrics).map(([metric, value]) => (
                <StatBlock
                  key={metric}
                  label={metric.replace(/_/g, " ")}
                  value={money(value)}
                  size="sm"
                />
              ))}
              {Object.entries(detail.latest_ratios).map(([ratio, value]) => (
                <StatBlock
                  key={ratio}
                  label={ratio.replace(/_pct/, "").replace(/_/g, " ")}
                  value={ratio.endsWith("_pct") ? `${value}%` : String(value)}
                  size="sm"
                  tone="accent"
                />
              ))}
            </div>
            {!detail.latest_period && (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                No annual filings recorded. ETFs, indices and non-US listings have
                no SEC XBRL data.
              </div>
            )}
          </SketchPanel>
        </div>
      )}
    </>
  );
}
