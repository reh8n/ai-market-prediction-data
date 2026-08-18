import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Annotation,
  Badge,
  Button,
  DataTable,
  Input,
  Select,
  SketchPanel,
  StatBlock,
  Tag,
} from "../design-system";
import {
  api,
  type ScrapedPage,
  type ScrapeJob,
  type ScrapeSite,
  type ScrapeStats,
} from "../api";
import { PageHead } from "./AppShell";
import { statusTone } from "./DatasetScreen";

function money(value: number | null) {
  if (value == null) return "—";
  if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  if (Math.abs(value) >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
  return `$${value.toFixed(0)}`;
}

interface Props {
  onNotify: (title: string, body: string, tone: "info" | "alert") => void;
}

export default function ScrapeScreen({ onNotify }: Props) {
  const [sites, setSites] = useState<ScrapeSite[]>([]);
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [pages, setPages] = useState<ScrapedPage[]>([]);
  const [stats, setStats] = useState<ScrapeStats | null>(null);
  const [selected, setSelected] = useState<ScrapedPage | null>(null);
  const [addingSite, setAddingSite] = useState(false);

  // Run form
  const [siteKey, setSiteKey] = useState("");
  const [limit, setLimit] = useState("25");
  const [industry, setIndustry] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [fundingMin, setFundingMin] = useState("");
  const [busy, setBusy] = useState(false);

  // New-site form
  const [siteName, setSiteName] = useState("");
  const [siteUrl, setSiteUrl] = useState("");
  const [sitePattern, setSitePattern] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [s, j, p, st] = await Promise.all([
        api.listScrapeSites(),
        api.listScrapeJobs(),
        api.listScrapedPages(200),
        api.scrapeStats(),
      ]);
      setSites(s);
      setJobs(j);
      setPages(p);
      setStats(st);
      if (!siteKey && s.length) setSiteKey(s[0].key);
    } catch (err) {
      onNotify("Scraper unavailable", String(err), "alert");
    }
  }, [onNotify, siteKey]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll only while something is running.
  useEffect(() => {
    if (!stats?.jobs_running) return;
    const timer = setInterval(() => void refresh(), 3000);
    return () => clearInterval(timer);
  }, [stats?.jobs_running, refresh]);

  const run = async (event: FormEvent) => {
    event.preventDefault();
    if (!siteKey) return;
    setBusy(true);
    try {
      const job = await api.runScrape({
        site_key: siteKey,
        limit: Number(limit) || 25,
        industry: industry.trim() || null,
        year_min: yearMin ? Number(yearMin) : null,
        funding_min: fundingMin ? Number(fundingMin) * 1e6 : null,
      });
      onNotify(
        "Scrape started",
        `Job ${job.id} · looking for ${job.requested} businesses`,
        "info",
      );
      void refresh();
    } catch (err) {
      onNotify("Scrape failed to start", String(err), "alert");
    } finally {
      setBusy(false);
    }
  };

  const addSite = async (event: FormEvent) => {
    event.preventDefault();
    if (!siteName.trim() || !siteUrl.trim()) return;
    try {
      await api.addScrapeSite({
        name: siteName.trim(),
        base_url: siteUrl.trim(),
        url_pattern: sitePattern.trim() || null,
      });
      setSiteName("");
      setSiteUrl("");
      setSitePattern("");
      setAddingSite(false);
      onNotify("Site added", `${siteName} is ready to scrape`, "info");
      void refresh();
    } catch (err) {
      onNotify("Could not add site", String(err), "alert");
    }
  };

  if (selected) {
    return (
      <>
        <PageHead
          overline={`Business // Scraped record`}
          title={selected.name || "Untitled"}
          right={
            <Button variant="secondary" onClick={() => setSelected(null)}>
              ← Businesses
            </Button>
          }
        />
        <div className="stack">
          <SketchPanel overline="Record // Extracted fields" tilt={false}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "var(--space-6)",
                marginBottom: "var(--space-5)",
              }}
            >
              <StatBlock
                label="Raised"
                value={money(selected.funding_usd)}
                size="sm"
              />
              <StatBlock
                label="Founded"
                value={selected.founded_year ? String(selected.founded_year) : "—"}
                size="sm"
              />
              <StatBlock
                label="Shut down"
                value={selected.shutdown_year ? String(selected.shutdown_year) : "—"}
                size="sm"
              />
              <StatBlock
                label="Country"
                value={selected.country || "—"}
                size="sm"
              />
            </div>
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                flexWrap: "wrap",
                marginBottom: "var(--space-4)",
              }}
            >
              {selected.rule_fields.map((f) => (
                <Badge key={f}>{f.split(":")[0]}</Badge>
              ))}
              {selected.ai_fields.map((f) => (
                <Badge key={f} tone="accent">
                  {f} · ai
                </Badge>
              ))}
            </div>
            <a href={selected.url} target="_blank" rel="noreferrer">
              view original ↗
            </a>
          </SketchPanel>

          <SketchPanel
            overline="Cause // Why it failed"
            title="Post-mortem"
            tilt={false}
          >
            {selected.cause ? (
              <p
                style={{
                  margin: 0,
                  fontSize: "var(--size-body)",
                  lineHeight: "var(--lh-body)",
                }}
              >
                {selected.cause}
              </p>
            ) : (
              <div
                style={{
                  fontSize: "var(--size-small)",
                  color: "var(--text-faint)",
                }}
              >
                No cause stated on the page. An AI key would let the system infer one.
              </div>
            )}
            {selected.description && (
              <p
                style={{
                  marginTop: "var(--space-5)",
                  paddingTop: "var(--space-4)",
                  borderTop: "1px solid var(--border-hairline)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                }}
              >
                {selected.description}
              </p>
            )}
          </SketchPanel>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead
        overline="Scrape // Failed businesses"
        title="Business Collector"
        right={
          <Button
            variant={addingSite ? "secondary" : "primary"}
            onClick={() => setAddingSite((v) => !v)}
          >
            {addingSite ? "Cancel" : "Add site"}
          </Button>
        }
      />

      <div className="split">
        <div className="stack">
          {addingSite && (
            <SketchPanel overline="Sites // Add your own" tilt={false}>
              <form onSubmit={addSite}>
                <div style={{ display: "grid", gap: "var(--space-4)" }}>
                  <Input
                    id="site-name"
                    label="Site name"
                    placeholder="Startup Graveyard"
                    value={siteName}
                    onChange={(e) => setSiteName(e.target.value)}
                  />
                  <Input
                    id="site-url"
                    label="Address"
                    placeholder="https://example.com"
                    value={siteUrl}
                    onChange={(e) => setSiteUrl(e.target.value)}
                  />
                  <Input
                    id="site-pattern"
                    label="Page pattern"
                    hint="optional"
                    placeholder="/company/[^/]+$"
                    value={sitePattern}
                    onChange={(e) => setSitePattern(e.target.value)}
                  />
                  <div>
                    <Button type="submit" disabled={!siteName || !siteUrl}>
                      Add site
                    </Button>
                  </div>
                </div>
              </form>
              <div
                style={{
                  marginTop: "var(--space-4)",
                  fontSize: "var(--size-small)",
                  color: "var(--text-muted)",
                  lineHeight: "var(--lh-snug)",
                }}
              >
                The scraper reads the site's sitemap and obeys its robots rules. Leave
                the pattern blank to use the common layout.
              </div>
            </SketchPanel>
          )}

          <SketchPanel overline="Run // Find businesses" tilt={false}>
            <form onSubmit={run}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.4fr 1fr",
                  gap: "var(--space-3)",
                }}
              >
                <Select
                  id="site"
                  label="Site"
                  value={siteKey}
                  onChange={(e) => setSiteKey(e.target.value)}
                  options={sites.map((s) => ({ value: s.key, label: s.name }))}
                />
                <Input
                  id="limit"
                  label="How many"
                  placeholder="25"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value.replace(/\D/g, ""))}
                />
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: "var(--space-3)",
                  marginTop: "var(--space-4)",
                }}
              >
                <Input
                  id="industry"
                  label="Industry"
                  hint="optional"
                  placeholder="fintech"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                />
                <Input
                  id="year"
                  label="Closed after"
                  hint="optional"
                  placeholder="2020"
                  value={yearMin}
                  onChange={(e) => setYearMin(e.target.value.replace(/\D/g, ""))}
                />
                <Input
                  id="funding"
                  label="Raised over"
                  hint="$m"
                  placeholder="10"
                  value={fundingMin}
                  onChange={(e) => setFundingMin(e.target.value.replace(/[^\d.]/g, ""))}
                />
              </div>

              <div style={{ marginTop: "var(--space-5)" }}>
                <Button type="submit" disabled={busy || !siteKey}>
                  {busy ? "Starting…" : "Find businesses"}
                </Button>
              </div>
            </form>
          </SketchPanel>

          <SketchPanel
            overline={`Businesses // Collected [${pages.length}]`}
            tilt={false}
          >
            <DataTable
              rows={pages}
              onRowClick={(r) => setSelected(r)}
              columns={[
                { key: "name", label: "Business", strong: true },
                {
                  key: "funding_usd",
                  label: "Raised",
                  align: "right",
                  render: (r) => money(r.funding_usd),
                },
                {
                  key: "shutdown_year",
                  label: "Closed",
                  align: "right",
                  render: (r) => r.shutdown_year || "—",
                },
                { key: "country", label: "Country", render: (r) => r.country || "—" },
                {
                  key: "cause",
                  label: "Cause",
                  render: (r) =>
                    r.cause ? (
                      <Badge tone="success">stated</Badge>
                    ) : (
                      <Badge>missing</Badge>
                    ),
                },
              ]}
              empty="No businesses collected yet"
            />
          </SketchPanel>
        </div>

        <div className="stack">
          <SketchPanel overline="Collection // Totals" tilt={false}>
            <div className="split-even" style={{ gap: "var(--space-6)" }}>
              <StatBlock
                label="Businesses"
                value={String(stats?.pages ?? 0)}
                meter={
                  stats?.pages ? (stats.with_cause / stats.pages) * 100 : 0
                }
              />
              <StatBlock
                label="With a cause"
                value={String(stats?.with_cause ?? 0)}
                caption="Reason for failure captured"
              />
              <StatBlock
                label="With funding"
                value={String(stats?.with_funding ?? 0)}
                caption="Capital raised known"
              />
              <StatBlock
                label="AI assisted"
                value={String(stats?.ai_assisted ?? 0)}
                caption="Gaps filled by a model"
              />
            </div>
            <div
              style={{
                marginTop: "var(--space-6)",
                paddingTop: "var(--space-4)",
                borderTop: "1px solid var(--border-hairline)",
              }}
            >
              <Annotation arrow="→">rules first — ai only fills the gaps</Annotation>
            </div>
          </SketchPanel>

          <SketchPanel overline="Sites // Available" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {sites.map((site) => (
                <div
                  key={site.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    paddingBottom: "var(--space-3)",
                    borderBottom: "1px solid var(--border-hairline)",
                  }}
                >
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontSize: "var(--size-small)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {site.name}
                  </span>
                  {site.built_in ? (
                    <Tag>built in</Tag>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await api.deleteScrapeSite(site.id);
                        void refresh();
                      }}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </SketchPanel>

          <SketchPanel overline="Jobs // Recent runs" tilt={false}>
            <div style={{ display: "grid", gap: "var(--space-3)" }}>
              {jobs.length === 0 && (
                <div
                  style={{
                    fontSize: "var(--size-small)",
                    color: "var(--text-faint)",
                  }}
                >
                  No runs yet.
                </div>
              )}
              {jobs.slice(0, 6).map((job) => (
                <div
                  key={job.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-3)",
                    paddingBottom: "var(--space-3)",
                    borderBottom: "1px solid var(--border-hairline)",
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--size-micro)",
                      color: "var(--text-faint)",
                      width: 30,
                    }}
                  >
                    #{job.id}
                  </span>
                  <span
                    style={{
                      flex: 1,
                      fontSize: "var(--size-small)",
                      color: "var(--text-body)",
                    }}
                  >
                    {job.saved}/{job.requested} saved
                    {job.skipped ? ` · ${job.skipped} skipped` : ""}
                  </span>
                  <Badge tone={statusTone(job.status)}>{job.status}</Badge>
                </div>
              ))}
            </div>
          </SketchPanel>
        </div>
      </div>
    </>
  );
}
