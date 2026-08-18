/** Pipeline notice with a coloured left rail. Position it yourself. */
export interface ToastProps {
  /** Uppercase micro title, e.g. "TRANSCRIPT READY". */
  title: React.ReactNode;
  children?: React.ReactNode;
  tone?: "info" | "success" | "warn" | "alert";
  onDismiss?: () => void;
  style?: React.CSSProperties;
}
export declare function Toast(props: ToastProps): JSX.Element;
