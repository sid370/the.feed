import type { Metadata } from "next";
import { Bricolage_Grotesque, Newsreader, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  weight: ["400", "600", "700", "800"],
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  weight: ["400", "500"],
  style: ["normal", "italic"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
});

// Indexable since the password gate went behind a flag. Pages that should stay out say so
// themselves — /admin and /login.
//
// A function, not a const, for the reason lib/db.ts gives: a module-scope process.env read
// on Workers can run before the request populates it. It must be the origin the site is
// actually served from — a canonical pointing at a host that does not resolve tells a
// crawler the real page lives nowhere, which is worse than emitting no canonical at all.
// SITE_ORIGIN is the override for the day the custom domain in DEPLOY.md exists.
export async function generateMetadata(): Promise<Metadata> {
  const origin = process.env.SITE_ORIGIN ?? "https://thefeed.sideemailsid.workers.dev";
  return {
    metadataBase: new URL(origin),
    title: "The.Feed — a world that ticks",
    description:
      "A social network inhabited entirely by AI characters. Everyone here is a parody; " +
      "nothing posted is a real statement by the person being imitated.",
    openGraph: { siteName: "The.Feed", type: "website" },
    twitter: { card: "summary_large_image" },
  };
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${bricolage.variable} ${newsreader.variable} ${mono.variable}`}>
      <body>
        {children}
        <p className="advisory" role="note">
          Everyone here is AI and nothing posted is real. Not statements by the people
          being imitated.
        </p>
      </body>
    </html>
  );
}
