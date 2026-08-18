/** Outline-bar distribution chart — pale fill, 1px ink stroke, x labels rotated -24°. */
export interface BarDatum { label: string; value: number; tone?: "default" | "accent" }
export interface BarChartProps {
  data?: BarDatum[];
  /** Y-axis top. Defaults to the data max rounded up to the next 20. */
  max?: number;
  /** Plot height in px, excluding the label gutter. */
  height?: number;
  /** Number of horizontal gridlines/ticks. */
  ticks?: number;
  /** Height of the rotated x-label gutter in px. Raise it for long category names. */
  labelHeight?: number;
  /** Suffix appended to each y tick, e.g. "%". */
  yUnit?: string;
  style?: React.CSSProperties;
}
export declare function BarChart(props: BarChartProps): JSX.Element;
