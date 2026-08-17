"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { Liker, likedWhen } from "../lib/api";
import Avatar from "./Avatar";

export default function LikersModal({
  likers,
  onClose,
}: {
  likers: Liker[];
  onClose: () => void;
}) {
  const [needle, setNeedle] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const q = needle.trim().toLowerCase();
  const shown = q
    ? likers.filter(
        (l) => l.name.toLowerCase().includes(q) || l.handle.toLowerCase().includes(q),
      )
    : likers;

  // Portalled to the body. `.post` animates transform with fill-mode both, so it keeps an
  // identity matrix forever — enough to make a fixed overlay size itself to the card.
  return createPortal(
    <div
      className="modal-veil"
      onClick={(e) => {
        // The card that owns this modal navigates on click, so nothing here may reach it.
        e.stopPropagation();
        // Only the backdrop itself closes; a click inside the panel bubbles up to here.
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label="Liked by">
        <header className="modal-head">
          <h2>Liked by {likers.length}</h2>
          <button onClick={onClose} aria-label="Close">×</button>
        </header>

        <input
          className="field"
          autoFocus
          value={needle}
          placeholder="Search name or handle"
          onChange={(e) => setNeedle(e.target.value)}
        />

        <div className="modal-list">
          {shown.map((liker) => (
            <Link key={liker.handle} className="liker-row" href={`/u/${liker.handle}`}>
              <Avatar
                name={liker.name}
                seed={liker.avatarSeed}
                url={liker.avatarUrl}
                size={32}
              />
              <span className="liker-row-id">
                <b>{liker.name}</b>
                <span>@{liker.handle}</span>
              </span>
              <span className="liker-row-when">{likedWhen(liker.likedAt)}</span>
            </Link>
          ))}
          {shown.length === 0 && <p className="modal-none">Nobody by that name.</p>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
