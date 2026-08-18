/** Single-line text field with optional uppercase label, prefix/suffix slot and error line. */
export interface InputProps {
  value?: string;
  defaultValue?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  /** Uppercase overline label above the field. */
  label?: string;
  /** Right-aligned micro hint on the label row, e.g. "optional". */
  hint?: string;
  /** Error message; also turns the border red. */
  error?: string;
  disabled?: boolean;
  type?: string;
  size?: "sm" | "md" | "lg";
  prefix?: React.ReactNode;
  suffix?: React.ReactNode;
  id?: string;
  style?: React.CSSProperties;
}
export declare function Input(props: InputProps): JSX.Element;
/** Standalone uppercase field label, exported for custom controls. */
export declare function FieldLabel(props: { children?: React.ReactNode; htmlFor?: string; hint?: string }): JSX.Element;
