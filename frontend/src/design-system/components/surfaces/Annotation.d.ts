/** Handwritten aside in Caveat — the only place a non-mono face appears. Keep to one per panel. */
export interface AnnotationProps {
  children?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  tone?: "ink" | "muted" | "accent";
  /** Optional trailing pointer glyph, e.g. "→" or "↘". */
  arrow?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function Annotation(props: AnnotationProps): JSX.Element;
