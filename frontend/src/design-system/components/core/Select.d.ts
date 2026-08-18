/** Native select styled to match Input. Chevron is the unicode `▾`, not an icon font. */
export interface SelectOption { value: string; label: string }
export interface SelectProps {
  value?: string;
  defaultValue?: string;
  onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  /** Strings or `{value,label}` pairs. */
  options?: (string | SelectOption)[];
  label?: string;
  hint?: string;
  disabled?: boolean;
  size?: "sm" | "md" | "lg";
  id?: string;
  style?: React.CSSProperties;
}
export declare function Select(props: SelectProps): JSX.Element;
