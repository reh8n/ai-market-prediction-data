/** Hairline table for company/source/event lists. No zebra rows; hover tints only when clickable. */
export interface DataColumn {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: number | string;
  /** Renders the value in stronger ink at semibold. */
  strong?: boolean;
  /** Custom cell renderer — return a Badge, Tag, etc. */
  render?: (row: any) => React.ReactNode;
}
export interface DataTableProps {
  columns?: DataColumn[];
  rows?: any[];
  onRowClick?: (row: any) => void;
  /** Empty-state text. */
  empty?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function DataTable(props: DataTableProps): JSX.Element;
