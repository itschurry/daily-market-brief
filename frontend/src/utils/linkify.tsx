import type { ReactNode } from 'react';

const URL_PATTERN = /(https?:\/\/[^\s<>()]+[^\s<>().,;:!?"'])/g;

export function renderTextWithLinks(text: string): ReactNode[] {
  if (!text) return [text];

  const parts = text.split(URL_PATTERN);
  return parts.filter(Boolean).map((part, index) => {
    if (!part.match(URL_PATTERN)) {
      return part;
    }

    return (
      <a
        className="inline-link"
        key={`${part}-${index}`}
        href={part}
        target="_blank"
        rel="noreferrer"
      >
        {part}
      </a>
    );
  });
}
