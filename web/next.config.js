/** @type {import('next').NextConfig} */
module.exports = {
  async headers() {
    // Unlisted by design — belt and braces alongside the metadata robots tag.
    return [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
  },
};
