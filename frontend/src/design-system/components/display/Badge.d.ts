/** Small uppercase status chip: outcome, job state, transcript method. */
export interface BadgeProps {
  children?: React.ReactNode;
  /** `success`/`alert` map to outcome states; `accent` for counts; `ink` for the strongest emphasis. */
  tone?: "neutral" | "ink" | "accent" | "success" | "warn" | "alert";
  style?: React.CSSProperties;
}
export declare function Badge(props: BadgeProps): JSX.Element;
