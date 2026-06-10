import { test, expect } from "@playwright/test";

// =============================================================================
// AutoInsight AI — Playwright E2E Tests
// Phase 4: Frontend Integration Tests (Day 44)
// =============================================================================

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";

test.describe("Authentication Flow", () => {
  test("should redirect unauthenticated users to login", async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test("should show login form", async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await expect(page.getByRole("heading", { name: /sign in/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test("should show validation errors on empty form", async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByLabel(/email/i)).toBeVisible();
  });

  test("should navigate to register page", async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByRole("link", { name: /register/i }).click();
    await expect(page).toHaveURL(/\/auth\/register/);
  });
});

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    // Mock authentication
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByLabel(/email/i).fill("admin@autoinsight.com");
    await page.getByLabel(/password/i).fill("password");
    await page.getByRole("button", { name: /sign in/i }).click();
  });

  test("should show dashboard after login", async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(/AutoInsight AI/i)).toBeVisible();
  });

  test("should show upload zone", async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await expect(page.getByText(/upload csv/i)).toBeVisible();
  });

  test("should navigate to upload page", async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.getByRole("button", { name: /upload dataset/i }).click();
    await expect(page).toHaveURL(/\/upload/);
  });
});

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByLabel(/email/i).fill("admin@autoinsight.com");
    await page.getByLabel(/password/i).fill("password");
    await page.getByRole("button", { name: /sign in/i }).click();
  });

  test("should navigate to all main pages", async ({ page }) => {
    const pages = [
      { link: /dashboard/i, url: /\/dashboard/ },
      { link: /upload data/i, url: /\/upload/ },
      { link: /reports/i, url: /\/reports/ },
      { link: /nlq chat/i, url: /\/nlq/ },
      { link: /admin/i, url: /\/admin/ },
    ];

    for (const { link } of pages) {
      await page.getByRole("link", { name: link }).first().click();
      await page.waitForTimeout(500);
    }
  });

  test("should logout successfully", async ({ page }) => {
    await page.goto(`${BASE_URL}/dashboard`);
    await page.getByTitle(/logout/i).click();
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});

test.describe("Upload Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByLabel(/email/i).fill("analyst@autoinsight.com");
    await page.getByLabel(/password/i).fill("password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.goto(`${BASE_URL}/upload`);
  });

  test("should show upload dropzone", async ({ page }) => {
    await expect(page.getByText(/upload csv/i)).toBeVisible();
  });

  test("should show configuration panel", async ({ page }) => {
    await expect(page.getByText(/upload configuration/i)).toBeVisible();
    await expect(page.getByText(/llm provider/i)).toBeVisible();
  });

  test("should show info cards", async ({ page }) => {
    await expect(page.getByText(/stage 1: csv parsing/i)).toBeVisible();
    await expect(page.getByText(/stage 2: cleaning/i)).toBeVisible();
    await expect(page.getByText(/stage 3-4: analysis/i)).toBeVisible();
  });

  test("should reject non-CSV files", async ({ page }) => {
    const fileChooserPromise = page.waitForEvent("filechooser");
    await page.getByText(/upload csv file/i).click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: "test.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("not a csv"),
    });
    await expect(page.getByText(/only csv files/i)).toBeVisible();
  });
});

test.describe("NLQ Chat Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByLabel(/email/i).fill("analyst@autoinsight.com");
    await page.getByLabel(/password/i).fill("password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.goto(`${BASE_URL}/nlq`);
  });

  test("should show welcome message", async ({ page }) => {
    await expect(page.getByText(/welcome to autoinsight/i)).toBeVisible();
  });

  test("should show suggested questions", async ({ page }) => {
    await expect(page.getByText(/try asking:/i)).toBeVisible();
    await expect(page.getByText(/what are the key trends/i)).toBeVisible();
  });

  test("should have reasoning toggle", async ({ page }) => {
    await expect(page.getByText(/show reasoning/i)).toBeVisible();
  });

  test("should have dataset selector", async ({ page }) => {
    await expect(page.getByRole("combobox")).toBeVisible();
  });
});

test.describe("Admin Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/auth/login`);
    await page.getByLabel(/email/i).fill("admin@autoinsight.com");
    await page.getByLabel(/password/i).fill("password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await page.goto(`${BASE_URL}/admin`);
  });

  test("should show system status", async ({ page }) => {
    await expect(page.getByText(/system status/i)).toBeVisible();
    await expect(page.getByText(/application/i)).toBeVisible();
    await expect(page.getByText(/llm provider/i)).toBeVisible();
  });

  test("should show pipeline stages", async ({ page }) => {
    await expect(page.getByText(/pipeline stages/i)).toBeVisible();
    await expect(page.getByText(/csv→json/i)).toBeVisible();
  });

  test("should show user management", async ({ page }) => {
    await expect(page.getByText(/user management/i)).toBeVisible();
  });
});
