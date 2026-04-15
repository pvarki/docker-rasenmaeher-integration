import { test as adminTest, expect } from "@fixtures/admin";

type Fixtures = {
  unauthenticatedPageBaseUrl: string;
};

export const test = adminTest.extend<Fixtures>({
  unauthenticatedPageBaseUrl: async ({ adminMeta }, use, testInfo) => {
    const baseURL = (testInfo.project.use.baseURL as string | undefined) || adminMeta.base_url;
    await use(baseURL);
  },
  context: async ({ browser, unauthenticatedPageBaseUrl }, use) => {
    const context = await browser.newContext({
      baseURL: unauthenticatedPageBaseUrl,
      ignoreHTTPSErrors: true,
    });

    await use(context);
    await context.close();
  },
});

export { expect };