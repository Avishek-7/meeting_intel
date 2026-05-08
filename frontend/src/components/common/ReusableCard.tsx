import type { ReactNode } from "react";

type ReusableCardProps = {
  title: string;
  description: string;
  image?: string;
  buttonText?: string;
  onButtonClick?: () => void;
  footer?: ReactNode;
};

export default function ReusableCard({
  title,
  description,
  image,
  buttonText = "Learn More",
  onButtonClick,
  footer,
}: ReusableCardProps) {
  return (
    <article className="mi-card">
      {image ? <img src={image} alt={title} className="mi-card-image" /> : null}
      <div className="mi-card-content">
        <h3>{title}</h3>
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
