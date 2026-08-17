// The page itself is a client component and cannot export metadata. It exists only to keep
// /login out of the index now that the site-wide noindex is gone.
export const metadata = { title: "Sign in", robots: { index: false, follow: false } };

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
