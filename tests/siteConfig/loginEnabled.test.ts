import { makeConfig } from "@site-config/ga2/local/config";

const BROWSER_URL = "https://example.org";

// GA2's config once omitted `loginEnabled` altogether, so every auth-gated
// shared component saw `isConfigured === false` on GA2 with no way to flip it
// short of an app-code change. BRC's equivalent config isn't asserted here
// because importing it pulls in next-mdx-remote, which Jest can't transform.
describe("ga2 site config", () => {
  it("exposes loginEnabled when enabled", () => {
    expect(makeConfig(BROWSER_URL, undefined, true).loginEnabled).toBe(true);
  });

  it("exposes loginEnabled when disabled", () => {
    expect(makeConfig(BROWSER_URL, undefined, false).loginEnabled).toBe(false);
  });

  it("defaults loginEnabled off when the env var is unset", () => {
    expect(makeConfig(BROWSER_URL).loginEnabled).toBe(false);
  });
});
