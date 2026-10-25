/**
 * "Pidgin" and "English" stacked in one grid cell, cross-fading in turn, so a word
 * is always visible and the pill never changes width.
 */
export function LanguageRotator() {
  return (
    <span className="inline-grid rounded-lg bg-accent-wash px-2 align-bottom text-accent-strong">
      <span className="sr-only">Pidgin and English</span>
      <span aria-hidden className="col-start-1 row-start-1 animate-[swap-a_4.4s_ease-in-out_infinite]">
        Pidgin
      </span>
      <span aria-hidden className="col-start-1 row-start-1 animate-[swap-b_4.4s_ease-in-out_infinite]">
        English
      </span>
    </span>
  );
}
