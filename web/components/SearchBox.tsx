"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

/* Filters the timeline as you type. It stays on / and only changes the query string, which
   is what lets the input keep focus and the caret across a re-render — a separate results
   route unmounts this component on the first keystroke and drops whatever is typed during
   the navigation. The <form> around it is not decoration: with JS off, enter still works. */

const DEBOUNCE_MS = 220;

export default function SearchBox({ q = "" }: { q?: string }) {
  const router = useRouter();
  const [text, setText] = useState(q);
  const [pending, start] = useTransition();
  // The mount fires this effect once with whatever the URL already said; navigating to the
  // page you are on would fight the back button for no reason.
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    const timer = setTimeout(() => {
      const next = text.trim();
      // replace, not push — otherwise every keystroke is a history entry and leaving the
      // page takes one press of Back per character typed.
      start(() => router.replace(next ? `/?q=${encodeURIComponent(next)}` : "/", { scroll: false }));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [text, router]);

  return (
    <form className="searchbar" action="/" method="get" role="search" data-pending={pending}>
      <input
        className="field"
        type="search"
        name="q"
        value={text}
        maxLength={80}
        placeholder="Search the feed"
        aria-label="Search posts and people"
        onChange={(e) => setText(e.target.value)}
      />
    </form>
  );
}
