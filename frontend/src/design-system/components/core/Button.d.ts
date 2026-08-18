/**
 * Primary action control. Uppercase mono label, letterspaced, square-ish 5px corners.
 * @startingPoint section="Core" subtitle="Buttons, inputs and form controls" viewport="700x260"
 */
export interface ButtonProps {
  children?: React.ReactNode;
  /** Visual weight. `primary` is the solid ink button used for the single main action per panel. */
  variant?: "primary" | "secondary" | "ghost" | "accent" | "danger";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  fullWidth?: boolean;
  /** Leading glyph — a Lucide `<i data-lucide>` element or an emoji span. */
  icon?: React.ReactNode;
  /** Trailing glyph, e.g. the `↵` on the assistant send button. */
  trailing?: React.ReactNode;
  type?: "button" | "submit" | "reset";
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  style?: React.CSSProperties;
}
export declare function Button(props: ButtonProps): JSX.Element;
