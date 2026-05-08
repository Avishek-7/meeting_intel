import { createElement, type ReactNode } from "react";

type ReusableCardProps = {
  title: string;
  description: string;
  image?: string;
  headingLevel?: 1 | 2 | 3 | 4 | 5 | 6;
  buttonText?: string;
  onButtonClick?: () => void;
  footer?: ReactNode;
};

export default function ReusableCard({
  title,
  description,
  image,
  headingLevel = 3,
  buttonText = "Learn More",
  onButtonClick,
  footer,
}: ReusableCardProps) {
  const headingTag = `h${headingLevel}` as const;
  const hasImage = typeof image === "string" && image.trim() !== "";

  return (
    <article className="mi-card">
      {hasImage ? (
        <img src={image} alt={title || "Card image"} width={1200} height={675} className="mi-card-image" />
      ) : null}
      <div className="mi-card-content">
        {createElement(headingTag, null, title)}
        <p>{description}</p>
        {onButtonClick ? (
          <button onClick={onButtonClick} className="btn-primary">
            {buttonText}
          </button>
        ) : null}
        {footer}
      </div>
    </article>
  );
}
