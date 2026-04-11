import { test as base, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export type AdminMeta = {
  username: string;
  pfx_path: string;
  pfx_passphrase: string;
  base_url: string;
  ui_login_code: string;
  compose_project: string;
};

let cachedAdminMeta: AdminMeta | null = null;

function readMeta(metaPath: string): AdminMeta {
  if (!fs.existsSync(metaPath)) {
    throw new Error(`RM_ADMIN_META points at a missing file: ${metaPath}`);
  }

  const parsed = JSON.parse(fs.readFileSync(metaPath, "utf8")) as AdminMeta;
  if (!path.isAbsolute(parsed.pfx_path)) {
    parsed.pfx_path = path.resolve(path.dirname(metaPath), parsed.pfx_path);
  }
  return parsed;
}

function resolveProvisionScriptPath(): string {
  const candidate = path.resolve(process.cwd(), "..", "..", "scripts", "create-admin.sh");
  if (!fs.existsSync(candidate)) {
    throw new Error(`Could not find provisioning script at: ${candidate}`);
  }
  return candidate;
}

function getAdminMeta(): AdminMeta {
  if (cachedAdminMeta) return cachedAdminMeta;

  const metaPath = process.env.RM_ADMIN_META;
  if (metaPath) {
    cachedAdminMeta = readMeta(metaPath);
    return cachedAdminMeta;
  }

  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), "rm-ui-test."));
  const username = `playwright${Date.now()}`;
  const scriptPath = resolveProvisionScriptPath();

  const args: string[] = [];
  if (process.env.RM_BASE_URL) {
    args.push("--base-url", process.env.RM_BASE_URL);
  }
  args.push(username, outDir);

  execFileSync(scriptPath, args, { stdio: "inherit" });

  const generatedMetaPath = path.join(outDir, "admin.json");
  cachedAdminMeta = readMeta(generatedMetaPath);
  return cachedAdminMeta;
}

export async function setLanguage(page: Page, lang: string): Promise<void> {
  await page.addInitScript((value: string) => {
    try {
      window.localStorage.setItem("language", value);
    } catch {
      // some contexts might block until page loaded
    }
  }, lang);
}

export async function suppressWalkthroughDialogs(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const originalGetItem = Storage.prototype.getItem;
    Storage.prototype.getItem = function patchedGetItem(key: string): string | null {
      if (key.includes("-onboarding-steps-")) return "[]";
      if (key.includes("-onboarding-role-")) return "admin";
      if (key.includes("-onboarding-")) return "true";
      if (
        key.startsWith("manage-users-walkthrough-") ||
        key.startsWith("add-users-walkthrough-")
      ) {
        return "true";
      }
      return originalGetItem.call(this, key);
    };
  });
}

export async function loginAsAdmin(
  page: Page,
  meta: AdminMeta,
): Promise<void> {
  await page.goto(`/login?code=${encodeURIComponent(meta.ui_login_code)}`);
  await page.waitForURL(/\/callsign-setup/, { timeout: 30_000 });
}

type Fixtures = {
  adminMeta: AdminMeta;
  adminPage: Page;
};

export const test = base.extend<Fixtures>({
  adminMeta: async ({}, use) => {
    await use(getAdminMeta());
  },
  adminPage: async ({ page, adminMeta }, use) => {
    await loginAsAdmin(page, adminMeta);
    await use(page);
  },
});

export { expect };
