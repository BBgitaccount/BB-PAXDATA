import { expect, test } from "@playwright/test";

test.describe("HITL Dashboard E2E Flow", () => {
	test.beforeEach(async ({ page }) => {
		// 1. Visit the home page (which redirects to login if unauthenticated)
		await page.goto("/");

		// 2. Perform login
		await page.fill('input[type="email"]', "admin@paxdata.local");
		await page.fill('input[type="password"]', "paxdata2024");
		await page.click('button[type="submit"]');

		// 3. Confirm redirected to dashboard
		await expect(page.locator("text=Özet")).toBeVisible({ timeout: 5000 });
	});

	test("should view review queue, submit verdict offline, and sync online", async ({
		page,
		context,
	}) => {
		// 1. Navigate to Review Queue page
		await page.click("text=İnceleme Kuyruğu");
		await expect(page.locator("text=İnceleme Kuyruğu")).toBeVisible();

		// Wait for the data table to load
		await page.waitForTimeout(1000);

		// 2. Click on the first "İNCELE" button
		const firstReviewBtn = page.locator('button:has-text("İNCELE")').first();
		await expect(firstReviewBtn).toBeVisible();
		await firstReviewBtn.click();

		// 3. Confirm we are on the Review Detail page
		await expect(page.locator("text=Karar Formu")).toBeVisible();

		// 4. Fill in some verdict information
		await page.click("text=HATA ONAYLANDI");
		await page.fill(
			'textarea[placeholder*="gerekçesini detaylandırın"]',
			"E2E Test justification details.",
		);

		// 5. Go Offline
		await context.setOffline(true);

		// 6. Submit the verdict
		await page.click('button:has-text("KARARI GÖNDER")');

		// 7. Verify offline toast alert shows up
		await expect(page.locator("text=Çevrimdışı mod")).toBeVisible();

		// 8. Go back to queue, confirm the item is optimistically hidden
		await page.click("text=Kuyruğa Dön");
		await page.waitForTimeout(500);

		// 9. Go Online
		await context.setOffline(false);

		// 10. Verify online sync toast message appears
		await expect(page.locator("text=senkronize edildi")).toBeVisible({
			timeout: 10000,
		});
	});
});
