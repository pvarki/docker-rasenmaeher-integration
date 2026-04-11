import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import type { Page } from "@playwright/test";
import { expect } from "../../fixtures/admin";

export const SCREENSHOTS_ENABLED = process.env.SCREENSHOTS === "1";
export const THEME = process.env.RM_THEME || "default";
export const LANGUAGES = ["en", "fi", "sv"] as const;
const _dirname = path.dirname(fileURLToPath(import.meta.url));
export const SCREENSHOT_DIR = path.resolve(_dirname, "..", "..", "screenshots");

const SCREENSHOT_SETTLE_MS = 500;
const NETWORKIDLE_TIMEOUT_MS = 3_500;
const TRANSIENT_UI_TIMEOUT_MS = 4_000;
const INTERACTIVE_TIMEOUT_MS = 20_000;
const INTERACTIVE_RECOVERY_ATTEMPTS = 4;
const OVERLAY_STABILITY_MS = 180;

const DIALOG_DISMISS_BUTTON_RE =
  /Got it|Close|Skip|Done|Finish|Next|Continue|OK|Sulje|Stang|Seuraava|Valmis|Jatka|N.sta|Klar/i;

export async function seedWaitingRoomState(page: Page): Promise<void> {
  await page.addInitScript(() => {
    localStorage.setItem("callsign", "PLAYWRIGHT_USER");
    localStorage.setItem("approveCode", "PLAYW123");
  });
}

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
    await page.waitForLoadState("networkidle", { timeout: NETWORKIDLE_TIMEOUT_MS });
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
  await page.waitForTimeout(SCREENSHOT_SETTLE_MS);
}

export async function waitForTransientUiToClear(page: Page): Promise<void> {
  // Sonner notifications can drift into captures -> wait for them
  const visibleToasts = page.locator("[data-sonner-toast]:visible");
  await expect
    .poll(async () => visibleToasts.count(), {
      timeout: TRANSIENT_UI_TIMEOUT_MS,
      message: "Expected transient toast notifications to disappear",
    })
    .toBe(0)
    .catch(() => undefined);
}

export async function captureFullPage(page: Page, screenshotPath: string): Promise<void> {
  await fs.mkdir(path.dirname(screenshotPath), { recursive: true });
  await closeTransientDialogs(page);
  await settleBeforeScreenshot(page);
  await page.screenshot({
    path: screenshotPath,
    type: "png",
    animations: "disabled",
    caret: "hide",
  });
}

export async function closeTransientDialogs(page: Page): Promise<void> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (page.isClosed()) {
      return;
    }

    const visibleOverlays = page.locator(
      "[role='dialog']:visible, [data-slot='drawer-content']:visible, [data-slot='drawer-overlay']:visible",
    );
    if ((await visibleOverlays.count()) === 0) {
      // Some overlays (like intro guides) can mount right after initial readiness.
      await page.waitForTimeout(OVERLAY_STABILITY_MS).catch(() => undefined);
      if ((await visibleOverlays.count()) === 0) {
        return;
      }
    }

    const explicitDismissButton = page
      .locator(
        "[data-slot='dialog-close']:visible, [role='dialog'] button[aria-label='Close']:visible, [data-slot='drawer-content'] button[aria-label='Close']:visible",
      )
      .first();
    if ((await explicitDismissButton.count()) > 0) {
      const previousCount = await visibleOverlays.count();
      await explicitDismissButton.click({ timeout: 1_200 }).catch(() => undefined);
      if (page.isClosed()) {
        return;
      }
      await expect
        .poll(async () => visibleOverlays.count(), {
          timeout: 1_000,
          message: "Expected overlay count to decrease after explicit close",
        })
        .toBeLessThan(previousCount)
        .catch(() => undefined);
      continue;
    }

    const actionDismissButton = page
      .locator(
        "[role='dialog'] button:visible, [data-slot='drawer-content'] button:visible",
      )
      .filter({ hasText: DIALOG_DISMISS_BUTTON_RE })
      .first();
    if ((await actionDismissButton.count()) > 0) {
      const previousCount = await visibleOverlays.count();
      await actionDismissButton.click({ timeout: 1_200 }).catch(() => undefined);
      if (page.isClosed()) {
        return;
      }
      await expect
        .poll(async () => visibleOverlays.count(), {
          timeout: 1_000,
          message: "Expected overlay count to decrease after action dismiss",
        })
        .toBeLessThan(previousCount)
        .catch(() => undefined);
      continue;
    }

    // Multi-step dialogs: advance via a generic "step forward" button.
    const stepForwardButton = page
      .locator("[data-testid='dialog-step-forward']:visible")
      .first();
    if ((await stepForwardButton.count()) > 0) {
      await stepForwardButton.click({ timeout: 1_200 }).catch(() => undefined);
      if (page.isClosed()) {
        return;
      }
      await page.waitForTimeout(300);
      continue;
    }

    await page.keyboard.press("Escape").catch(() => undefined);
    if (page.isClosed()) {
      return;
    }
    await expect
      .poll(async () => visibleOverlays.count(), {
        timeout: 1_000,
        message: "Expected overlays to close after Escape",
      })
      .toBe(0)
      .catch(() => undefined);
  }
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
    return url.pathname.startsWith("/error") &&
      (url.searchParams.get("code") ?? "").toLowerCase() === "mtls_fail";
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

export async function waitForInteractivePage(page: Page): Promise<void> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= INTERACTIVE_RECOVERY_ATTEMPTS; attempt += 1) {
    await page.waitForLoadState("domcontentloaded").catch(() => undefined);

    try {
      await expect
        .poll(() => isPageInteractive(page), {
          timeout: INTERACTIVE_TIMEOUT_MS,
          message: "Page did not become interactive in time",
        })
        .toBeTruthy();

      const hitMtlsFailPage = await isMtlsFailPage(page);
      if (!hitMtlsFailPage) {
        return;
      }

      lastError = new Error("Landed on mTLS failure page after readiness check");
    } catch (error) {
      lastError = error;
    }

    if (attempt === INTERACTIVE_RECOVERY_ATTEMPTS || page.isClosed()) {
      break;
    }

    await page.waitForTimeout(400 * attempt).catch(() => undefined);
    await page.reload({ waitUntil: "domcontentloaded" }).catch(() => undefined);
  }

  if (lastError instanceof Error) {
    throw lastError;
  }

  throw new Error("Page did not become interactive in time");
}