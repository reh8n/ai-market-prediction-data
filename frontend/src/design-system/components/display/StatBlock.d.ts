/**
 * Headline metric: uppercase overline, bold mono number, optional 4px meter and caption.
 * @startingPoint section="Data display" subtitle="Metrics, charts, tables and badges" viewport="700x320"
 */
export interface StatBlockProps {
  /** Uppercase overline, e.g. "MODEL CONFIDENCE". */
  label: React.ReactNode;
  /** The number, pre-formatted with its unit ("98.4%", "424"). */
  value: React.ReactNode;
  /** One-line explanation below, sentence case. */
  caption?: React.ReactNode;
  /** 0–100; renders the ink meter bar under the value. */
  meter?: number | null;
  tone?: "ink" | "accent" | "muted";
  size?: "sm" | "md" | "lg";
  style?: React.CSSProperties;
}
export declare function StatBlock(props: StatBlockProps): JSX.Element;
