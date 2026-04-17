import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";

export const SCREENSHOTS_ENABLED = process.env.SCREENSHOTS === "1";
export const THEME = process.env.RM_THEME || "default";
export const LANGUAGES = ["en", "fi", "sv"] as const;

/**
 * Languages to capture in screenshot specs.
 * Environment variable SCREENSHOT_LANGS:
 *  - default ("all"/empty)         -> captures all languages
 *  - list ("en", "en,fi")          -> captures the matching languages
 */
function parseScreenshotLanguages(): readonly string[] {
  const raw = (process.env.SCREENSHOT_LANGS ?? "").trim().toLowerCase();
  if (!raw || raw === "all") return LANGUAGES;
  const requested = new Set(
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  const filtered = LANGUAGES.filter((lang) => requested.has(lang));
  return filtered.length > 0 ? filtered : LANGUAGES;
}

export const SCREENSHOT_LANGUAGES: readonly string[] =
  parseScreenshotLanguages();
const _dirname = path.dirname(fileURLToPath(import.meta.url));
export const SCREENSHOT_DIR = path.resolve(_dirname, "..", "screenshots");

const INTERACTIVE_RECOVERY_ATTEMPTS = 6;

export function getMtlsUrl(baseUrl: string, pathname: string): string {
  const url = new URL(baseUrl);
  if (!url.hostname.startsWith("mtls.")) {
    url.hostname = `mtls.${url.hostname}`;
  }

  const resolvedPath = new URL(pathname, url);
  url.pathname = resolvedPath.pathname;
  url.search = resolvedPath.search;
  return url.toString();
}

export async function settleBeforeScreenshot(page: Page): Promise<void> {
  await page.waitForLoadState("domcontentloaded");
  try {
    await page.waitForLoadState("networkidle");
  } catch {
    // Some data might be missing..
  }

  await page
    .evaluate(async () => {
      await new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      });
    })
    .catch(() => undefined);

  await page
    .evaluate(async () => {
      if (typeof document === "undefined" || !("fonts" in document)) {
        return;
      }

      const docWithFonts = document as Document & {
        fonts?: { ready: Promise<unknown> };
      };

      await docWithFonts.fonts?.ready;
    })
    .catch(() => undefined);

  await waitForTransientUiToClear(page);
  await blurActiveElement(page);
  await page.waitForTimeout(250);
}

async function blurActiveElement(page: Page): Promise<void> {
  await page
    .evaluate(() => {
      const active = document.activeElement as HTMLElement | null;
      if (
        active &&
        active !== document.body &&
        typeof active.blur === "function"
      ) {
        active.blur();
      }
      if (typeof window.getSelection === "function") {
        window.getSelection()?.removeAllRanges();
      }
    })
    .catch(() => undefined);
}

export async function waitForTransientUiToClear(page: Page): Promise<void> {
  // Sonner notifications can drift into captures -> wait for them
  const visibleToasts = page.locator("[data-sonner-toast]:visible");
  if ((await visibleToasts.count()) === 0) return;
  await expect
    .poll(async () => visibleToasts.count(), {
      message: "Expected transient toast notifications to disappear",
    })
    .toBe(0)
    .catch(() => undefined);
}

export async function captureFullPage(
  page: Page,
  screenshotPath: string,
): Promise<void> {
  await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
  await settleBeforeScreenshot(page);
  await page.screenshot({
    path: screenshotPath,
    type: "png",
    animations: "disabled",
    caret: "hide",
  });
}

async function isMtlsFailPage(page: Page): Promise<boolean> {
  if (page.isClosed()) {
    return false;
  }

  const mtlsFailError = page.locator(
    "[data-testid='error-content'][data-error-code='mtls_fail']",
  );
  if ((await mtlsFailError.count()) === 0) {
    return false;
  }

  try {
    const url = new URL(page.url());
    return (
      url.pathname.startsWith("/error") &&
      (url.searchParams.get("code") ?? "").toLowerCase() === "mtls_fail"
    );
  } catch {
    return false;
  }
}

async function isPageInteractive(page: Page): Promise<boolean> {
  if (page.isClosed()) {
    return false;
  }

  try {
    if (await page.locator("main:visible").count()) {
      return true;
    }
    return (await page.locator("body:visible *:visible").count()) > 0;
  } catch {
    return false;
  }
}

export async function waitForInteractivePage(
  page: Page,
  recoverUrl?: string,
): Promise<void> {
  let lastError: unknown;

  for (
    let attempt = 1;
    attempt <= INTERACTIVE_RECOVERY_ATTEMPTS;
    attempt += 1
  ) {
    await page.waitForLoadState("domcontentloaded").catch(() => undefined);

    try {
      await expect
        .poll(() => isPageInteractive(page), {
          message: "Page did not become interactive in time",
          timeout: 5_000,
        })
        .toBeTruthy();

      const hitMtlsFailPage = await isMtlsFailPage(page);
      if (!hitMtlsFailPage) {
        return;
      }

      lastError = new Error(
        "Landed on mTLS failure page after readiness check",
      );
    } catch (error) {
      lastError = error;
    }

    if (attempt === INTERACTIVE_RECOVERY_ATTEMPTS || page.isClosed()) {
      break;
    }

    await page.waitForTimeout(500 * attempt).catch(() => undefined);
    //recover from mTLS error
    if (recoverUrl) {
      await page
        .goto(recoverUrl, { waitUntil: "domcontentloaded" })
        .catch(() => undefined);
    } else {
      await page
        .reload({ waitUntil: "domcontentloaded" })
        .catch(() => undefined);
    }
  }

  if (lastError instanceof Error) {
    throw lastError;
  }

  throw new Error("Page did not become interactive in time");
}

export async function gotoInteractive(page: Page, url: string): Promise<void> {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await waitForInteractivePage(page, url);
}
