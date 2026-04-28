import type { Locator, Page } from "@playwright/test";

export async function isInViewport(page: Page, locator: Locator): Promise<boolean> {
  const box = await locator.boundingBox();
  const viewport = page.viewportSize();
  if (!box || !viewport) {
    return false;
  }

  return (
    box.width > 0 &&
    box.height > 0 &&
    box.x >= 0 &&
    box.y >= 0 &&
    box.x + box.width <= viewport.width &&
    box.y + box.height <= viewport.height
  );
}

export async function pickInViewportByTestId(page: Page, testId: string): Promise<Locator> {
  const candidates = page.getByTestId(testId);
  const count = await candidates.count();
  if (count <= 1) {
    return candidates.first();
  }

  const viewport = page.viewportSize();
  if (!viewport) {
    return candidates.last();
  }

  for (let i = 0; i < count; i += 1) {
    const candidate = candidates.nth(i);
    if (!(await candidate.isVisible())) {
      continue;
    }

    if (await isInViewport(page, candidate)) {
      return candidate;
    }
  }

  return candidates.last();
}

export async function clickSafe(locator: Locator): Promise<void> {
  await locator.scrollIntoViewIfNeeded();
  await locator.click({ timeout: 2_000 }).catch(async () => {
    await locator.click({ force: true }).catch(async () => {
      await locator.evaluate((el: HTMLElement) => el.click());
    });
  });
}

export async function clickReady(page: Page, testId: string): Promise<void> {
  const target = await pickInViewportByTestId(page, testId);
  await clickSafe(target);
}
