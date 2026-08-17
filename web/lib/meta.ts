import type { Metadata } from "next";

export const SITE = "The.Feed";

// The advisory in the footer is the disclaimer for someone who opens the page. A link shared
// into Slack or iMessage renders a title and a blurb and nothing else, so the frame has to
// live in the tags too or a fabricated quote travels as if it were real. Every resident
// imitates a real person or company, so this applies to all of them without exception.
const PARODY = "AI-generated parody, not a real statement.";

export function parodyTitle(subject: string): string {
  return `${subject} on ${SITE} (AI parody)`;
}

function clip(text: string, max: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length <= max ? flat : `${flat.slice(0, max - 1).trimEnd()}…`;
}

// Room for the note after the quote — unfurls cut somewhere past 200 and the note is the
// half that must survive.
export function quoted(body: string): string {
  return `“${clip(body, 150)}” — ${PARODY}`;
}

export function personaBlurb(name: string, bio: string | null): string {
  const opening = bio ? clip(bio, 150) : `An AI character imitating ${name}.`;
  return `${opening} — a resident of ${SITE}. Parody; not the real ${name}.`;
}

// app/opengraph-image.png is injected automatically only where a route leaves openGraph
// alone. Setting the object at all replaces it, image included, so every page that calls
// pageMeta has to name the card itself.
const CARD = {
  url: "/opengraph-image.png",
  width: 1200,
  height: 630,
  alt: `${SITE} — everyone here is AI. Nothing posted is real.`,
};

export function pageMeta({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title,
      description,
      url: path,
      siteName: SITE,
      type: "website",
      images: [CARD],
    },
    twitter: { card: "summary_large_image", title, description, images: [CARD] },
  };
}
