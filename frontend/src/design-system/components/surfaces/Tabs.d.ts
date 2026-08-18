/** Underlined uppercase tab row for switching views inside a panel. */
export interface TabItem { value: string; label: string; count?: number }
export interface TabsProps {
  tabs?: (string | TabItem)[];
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  style?: React.CSSProperties;
}
export declare function Tabs(props: TabsProps): JSX.Element;
