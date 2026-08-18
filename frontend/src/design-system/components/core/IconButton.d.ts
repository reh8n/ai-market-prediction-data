/** Square icon-only control for panel toolbars. `label` is required for a11y and tooltip. */
export interface IconButtonProps {
  children?: React.ReactNode;
  /** Accessible name; also rendered as the native tooltip. */
  label: string;
  size?: "sm" | "md" | "lg";
  variant?: "ghost" | "outline" | "solid";
  disabled?: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  style?: React.CSSProperties;
}
export declare function IconButton(props: IconButtonProps): JSX.Element;
