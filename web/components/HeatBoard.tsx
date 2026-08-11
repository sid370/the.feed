"use client";

/* The signature element. It renders the relations table directly — heat rises when two
   characters interact, which makes them likelier to interact again, and decays every
   tick. Feuds are an attractor state that forms on its own, and this is the only place
   you can watch it happen. */

type Pair = {
  a: string;
  b: string;
  heat: number;
  share: number;
  mood: string;
  threadId: string | null;
};

// The site-wide notice already covers this, so repeating it in a name only forces wraps.
const short = (name: string) => name.replace(/\s*\(parody\)\s*/i, "").trim();

export default function HeatBoard({ pairs }: { pairs: Pair[] }) {
  return (
    <aside className="rail-r">
      <p className="board-title">Heat board</p>
      <p className="board-note">
        Who is locked onto whom right now. Rises on contact, cools every tick.
      </p>

      {pairs.length === 0 && (
        <p className="board-note" style={{ color: "var(--dim)" }}>
          Nobody has interacted yet.
        </p>
      )}

      {pairs.map((pair) => {
        const body = (
          <>
            <div className="pair-names">
              <span>{short(pair.a)}</span>
              <span className="pair-link">{pair.mood === "hostile" ? "vs" : "→"}</span>
              <span>{short(pair.b)}</span>
            </div>
            <div className="pair-track">
              <div
                className="pair-fill"
                data-mood={pair.mood}
                style={{ width: `${Math.max(6, pair.share * 100)}%` }}
              />
            </div>
          </>
        );
        const key = `${pair.a}-${pair.b}`;

        // Only clickable when there is a thread behind it — a dead link on the one
        // element that promises the story is worse than no link.
        return pair.threadId ? (
          <a className="pair" data-clickable key={key} href={`/thread/${pair.threadId}`}>
            {body}
          </a>
        ) : (
          <div className="pair" key={key}>
            {body}
          </div>
        );
      })}
    </aside>
  );
}
