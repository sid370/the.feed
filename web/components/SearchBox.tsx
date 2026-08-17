/* A GET form, so search costs no client JavaScript and a result is a URL you can share.
   The browser builds /search?q=… itself and the page reads it on the server. */

export default function SearchBox({ q = "" }: { q?: string }) {
  return (
    <form className="searchbar" action="/search" method="get" role="search">
      <input
        className="field"
        type="search"
        name="q"
        defaultValue={q}
        maxLength={80}
        placeholder="Search the feed"
        aria-label="Search posts and people"
      />
    </form>
  );
}
