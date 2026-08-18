/** 7px dot + uppercase micro label. The "● ONLINE" marker in the assistant header. */
export interface StatusDotProps {
  state?: "ok" | "warn" | "alert" | "idle";
  label?: React.ReactNode;
  /** Adds a soft halo — use only for a live/streaming state. */
  pulse?: boolean;
  style?: React.CSSProperties;
}
export declare function StatusDot(props: StatusDotProps): JSX.Element;
