/** Centred modal built on a lifted SketchPanel over a blurred ink scrim. */
export interface DialogProps {
  open?: boolean;
  title?: React.ReactNode;
  overline?: React.ReactNode;
  children?: React.ReactNode;
  /** Right-aligned action row below a hairline divider. */
  footer?: React.ReactNode;
  /** Called on backdrop click and on the ✕ button. Omit to hide the close affordance. */
  onClose?: () => void;
  width?: number | string;
}
export declare function Dialog(props: DialogProps): JSX.Element | null;
