/**
 * The system's only container: white paper, hairline border, uneven hand-drawn radius,
 * faint offset inner stroke and a fraction-of-a-degree tilt.
 * @startingPoint section="Surfaces" subtitle="Sketched panels, overlines and annotations" viewport="700x300"
 */
export interface SketchPanelProps {
  children?: React.ReactNode;
  /** Bold ink headline inside the panel header. */
  title?: React.ReactNode;
  /** Uppercase overline above the title, e.g. "DATASET PROFILE // VISUAL SCHEMATIC". */
  overline?: React.ReactNode;
  /** Right-aligned controls on the title row. */
  actions?: React.ReactNode;
  /** Overrides `--panel-pad`. */
  padding?: string;
  /** Sub-degree rotation that makes the panel read as drawn. Off for panels inside a tight grid. */
  tilt?: boolean;
  /** Stronger drop shadow — for modals and dragged cards only. */
  lifted?: boolean;
  /** Left accent rail: `accent` (ink) for assistant output, `user` (blue) for user input. */
  rail?: "accent" | "user" | null;
  style?: React.CSSProperties;
}
export declare function SketchPanel(props: SketchPanelProps): JSX.Element;
export interface PanelLabelProps {
  children?: React.ReactNode;
  tone?: "muted" | "strong" | "accent";
  style?: React.CSSProperties;
}
export declare function PanelLabel(props: PanelLabelProps): JSX.Element;
