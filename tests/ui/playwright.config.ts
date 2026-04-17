import { defineConfig, devices } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const _dirname = path.dirname(fileURLToPath(import.meta.url));
import type { AdminMeta } from "./fixtures/admin";

/**
 * Playwright configuration for the Rasenmaeher UI playthrough.
 *
 * Environment variables:
 *
 *   RM_ADMIN_META   Path to admin.json produced by scripts/create-admin.sh.
 *                   Required. Contains base_url, pfx_path, ui_login_code, etc.
 *
 *   RM_BASE_URL     Override the UI base URL (defaults to the value in admin.json,
 *                   else https://localmaeher.dev.pvarki.fi:4439).
 *
 *   RM_THEME        Theme id baked into the running uiv2 build. Used only to name
 *                   the screenshots output subdirectory. Defaults to "default".
 *
 *   SCREENSHOTS     When set to "1", the opt-in screenshots spec runs and captures
 *                   the language matrix. Otherwise it is skipped.
 */

function loadAdminMeta(): AdminMeta | null {
  const metaPath = process.env.RM_ADMIN_META;
  if (!metaPath) return null;
  if (!fs.existsSync(metaPath)) {
    throw new Error(`RM_ADMIN_META points at a missing file: ${metaPath}`);
  }
  const parsed = JSON.parse(fs.readFileSync(metaPath, "utf8")) as AdminMeta;
  if (!path.isAbsolute(parsed.pfx_path)) {
    parsed.pfx_path = path.resolve(path.dirname(metaPath), parsed.pfx_path);
  }
  return parsed;
}

const adminMeta = loadAdminMeta();
const baseURL =
  process.env.RM_BASE_URL ||
  adminMeta?.base_url ||
  "https://localmaeher.dev.pvarki.fi:4439";

// Derive the mtls.* origin from the base URL so both hosts get the same cert.
const mtlsOrigin = (() => {
  const url = new URL(baseURL);
  return `${url.protocol}//mtls.${url.host}`;
})();

const clientCertificates = adminMeta
  ? [
      {
        origin: baseURL,
        pfxPath: adminMeta.pfx_path,
        passphrase: adminMeta.pfx_passphrase,
      },
      {
        origin: mtlsOrigin,
        pfxPath: adminMeta.pfx_path,
        passphrase: adminMeta.pfx_passphrase,
      },
    ]
  : undefined;

// Scan repo root for directories containing e2e specs to auto-discover products.
// Supports both <product>/e2e and <product>/ui/e2e layouts.
const repoRoot = path.resolve(_dirname, "..", "..");
const rawProductFilter =
  process.env.RM_UI_PRODUCTS || process.env.RM_UI_PRODUCT || "";
const selectedProducts = new Set(
  rawProductFilter
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
);

function productTestGlob(name: string): string | null {
  if (fs.existsSync(path.join(repoRoot, name, "e2e"))) {
    return `**/${name}/e2e/**/*.spec.ts`;
  }
  if (fs.existsSync(path.join(repoRoot, name, "ui", "e2e"))) {
    return `**/${name}/ui/e2e/**/*.spec.ts`;
  }
  return null;
}

const products = fs
  .readdirSync(repoRoot, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .filter((d) => selectedProducts.size === 0 || selectedProducts.has(d.name))
  .flatMap((d) => {
    const glob = productTestGlob(d.name);
    return glob ? [{ name: d.name, glob }] : [];
  });

const screenshotsEnabled = process.env.SCREENSHOTS === "1";
const screenshotTestIgnore = screenshotsEnabled
  ? undefined
  : /screenshots[^/]*\.spec\.ts$/;

const browsers = [
  {
    suffix: "chromium",
    use: {
      ...devices["Desktop Chrome"],
      channel: "chromium",
      viewport: { width: 1600, height: 900 },
    },
  },
  { suffix: "android", use: { ...devices["Pixel 7"], channel: "chromium" } },
];

const projects =
  products.length > 0
    ? products.flatMap((product) =>
        browsers.map((browser) => ({
          name: `${product.name}-${browser.suffix}`,
          testMatch: product.glob,
          testIgnore: screenshotTestIgnore,
          use: browser.use,
        })),
      )
    : browsers.map((browser) => ({
        name: browser.suffix,
        testMatch: "**/e2e/**/*.spec.ts",
        testIgnore: screenshotTestIgnore,
        use: browser.use,
      }));

export default defineConfig({
  // Discover specs from any submodule that follows the e2e/ convention.
  testDir: "../..",
  tsconfig: "./tsconfig.json",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 1,
  timeout: 30_000,
  expect: { timeout: 15_000 },
  workers: process.env.CI ? 2 : 4,
  reporter: [
    ["list"],
    ["junit", { outputFile: "test-results/junit.xml" }],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  outputDir: "test-results",
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    clientCertificates,
  },
  projects,
});
