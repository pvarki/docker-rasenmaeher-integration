import { expect, type Page } from "@playwright/test";
import { getMtlsUrl } from "@helpers/screenshots";

export async function setLanguage(page: Page, lang: string): Promise<void> {
  await page.addInitScript((value: string) => {
    try {
      window.localStorage.setItem("language", value);
    } catch {}
  }, lang);
}

export async function suppressProductOnboarding(
  page: Page,
  productKey: string,
): Promise<void> {
  await page.addInitScript((key: string) => {
    const finished = new RegExp(`-${key}-onboarding-.*-finished$`);
    const steps = new RegExp(`-${key}-onboarding-.*-steps$`);
    const session = new RegExp(`-${key}-onboarding-.*-session$`);
    const originalGetItem = Storage.prototype.getItem;
    Storage.prototype.getItem = function patchedGetItem(
      key: string,
    ): string | null {
      if (finished.test(key)) return "true";
      if (steps.test(key)) return "[]";
      if (session.test(key)) return null;
      return originalGetItem.call(this, key);
    };
  }, productKey);
}

export async function gotoProductRoute(
  page: Page,
  productKey: string,
): Promise<void> {
  const configuredBase =
    process.env.RM_BASE_URL || "https://localmaeher.dev.pvarki.fi:4439";

  const productUrl = getMtlsUrl(configuredBase, `/product/${productKey}`);
  await page.goto(productUrl, { waitUntil: "domcontentloaded" });

  await expect(page.getByTestId("home-page")).toBeVisible({ timeout: 30_000 });
}
