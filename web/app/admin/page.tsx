import AdminConsole from "../../components/AdminConsole";

// Never cached and never prerendered: it is behind a token, and its numbers are the ones you
// check right after a deploy.
export const dynamic = "force-dynamic";

// The site-wide noindex went away when the gate did; this page still has no business in a
// search result.
export const metadata = { title: "Control room", robots: { index: false, follow: false } };

export default function Admin() {
  // Set to http://localhost:8000 in web/.env.local to get the write controls back. Unset on
  // the deployed app, where the endpoints they call do not exist on purpose.
  return <AdminConsole writeApi={process.env.ADMIN_WRITE_API ?? ""} />;
}
