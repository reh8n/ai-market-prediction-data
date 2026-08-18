/** Selectable filter chip with the hand-drawn small radius. Sentence case, not uppercase. */
export interface TagProps {
  children?: React.ReactNode;
  /** Selected state — fills with ink. */
  active?: boolean;
  onClick?: () => void;
  /** Renders a ✕ that removes the tag. */
  onRemove?: () => void;
  /** Leading glyph or emoji. */
  icon?: React.ReactNode;
  style?: React.CSSProperties;
}
export declare function Tag(props: TagProps): JSX.Element;
