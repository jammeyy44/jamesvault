import { expect, test } from "@playwright/test";

const PUBLIC = ["/", "/games", "/bonus-zone", "/refer", "/support", "/login", "/register", "/legal/terms"];

test.describe("brief constraints", () => {
  for (const path of PUBLIC) {
    test(`no VIP or FAQ content on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const text = (await page.locator("body").innerText()).toLowerCase();
      expect(text).not.toMatch(/\bvip\b/);
      expect(text).not.toMatch(/\bfaq\b|frequently asked/);
    });

    test(`no horizontal scroll on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }
});

test("home: Bonus Zone slider first, then refer banner, then the games", async ({ page, isMobile }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("BONUS");
  await expect(page.getByRole("link", { name: /Explore Bonuses/ })).toBeVisible();

  await page.getByRole("tab", { name: "Go to slide 2" }).click();
  await expect(page.getByRole("link", { name: /Explore Games/ })).toBeVisible();
  await expect(page.getByText("Winning Moment")).toBeVisible();
  await expect(page.getByRole("tab", { name: "Go to slide 3" })).toHaveCount(0);  // two slides: Bonus Zone and Games

  // order on the page: slider -> refer your friends -> games
  await expect(page.locator("#refer-title")).toHaveText("Refer your friends");
  const top = async (loc: ReturnType<typeof page.locator>) => (await loc.first().boundingBox())!.y;
  const slider = await top(page.locator("section[aria-roledescription=carousel]"));
  const refer = await top(page.locator("#refer-title"));
  const games = await top(page.getByRole("heading", { name: /In the lobby|Featured games/ }));
  expect(slider).toBeLessThan(refer);
  expect(refer).toBeLessThan(games);

  if (isMobile) await page.getByRole("button", { name: "Open menu" }).click();
  const nav = page.getByRole("navigation", { name: isMobile ? "Mobile" : "Main" });
  for (const label of ["Home", "Games", "Bonus Zone", "Refer a Friend"]) {
    await expect(nav.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(nav.getByRole("link", { name: "Promotions" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Tournaments" })).toHaveCount(0);
});

test("old Promotions and Tournaments addresses lead to the Bonus Zone, which invites signed-out visitors to join", async ({ page }) => {
  await page.goto("/tournaments");
  await expect(page).toHaveURL(/\/bonus-zone/);
  await page.goto("/promotions");
  await expect(page).toHaveURL(/\/bonus-zone/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("BONUS");
  await expect(page.getByRole("link", { name: "Create your account" })).toBeVisible();
});

test("game lobby lists verified catalog entries and filters by search", async ({ page }) => {
  await page.goto("/games");
  await expect(page.getByText(/\d+ games?$/)).toBeVisible();
  await page.getByLabel("Search games").fill("zzzz-no-such-game");
  await expect(page.getByText("No games match your filters")).toBeVisible();
});

test("signed-out visitors are sent to log in to play", async ({ page }) => {
  await page.goto("/games");
  await page.getByRole("button", { name: /^Play / }).first().click();
  await expect(page).toHaveURL(/\/login/);
});

test("register, wallet, game access, Bonus Zone, favorites, log out and back in", async ({ page }) => {
  const id = Date.now().toString(36);
  const user = `e2e_${id}`;
  await page.goto("/register");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Email").fill(`${user}@example.com`);
  await page.getByLabel("Password").fill("Sup3rSecret!x");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: `Hi, ${user}` })).toBeVisible();

  // wallet: header icon opens the Wallet panel; sandbox deposit credits the wallet
  await page.getByRole("button", { name: "Open wallet" }).click();
  await expect(page.getByRole("heading", { name: "Wallet" })).toBeVisible();
  await expect(page.getByTestId("wallet-balance")).toContainText("0.00");
  // choosing a method opens the amount popup. Chime only accepts listed amounts, so chips (no free text) are offered
  await page.getByRole("button", { name: "Chime" }).click();
  const pop = page.getByRole("dialog", { name: "Chime deposit" });
  await expect(pop).toBeVisible();
  await expect(pop.getByLabel("Amount in dollars")).toHaveCount(0);
  await expect(pop.getByTestId("deposit-amount")).toHaveText("$20");
  await pop.getByRole("button", { name: "+5" }).click();           // snaps to the next accepted amount
  await expect(pop.getByTestId("deposit-amount")).toHaveText("$25");
  await pop.getByRole("button", { name: "$20.00", exact: true }).click();
  await expect(pop.getByTestId("deposit-amount")).toHaveText("$20");
  await pop.getByRole("button", { name: "Back" }).click();         // Back returns to the method list without charging anything
  await expect(page.getByTestId("wallet-balance")).toContainText("0.00");

  // PayPal accepts any amount (within limits): full editor with quick buttons
  await page.getByRole("button", { name: "PayPal" }).click();
  const pp = page.getByRole("dialog", { name: "PayPal deposit" });
  await expect(pp.getByTestId("deposit-amount")).toHaveText("$20");
  await pp.getByRole("button", { name: "+10" }).click();
  await pp.getByRole("button", { name: "X2" }).click();
  await expect(pp.getByTestId("deposit-amount")).toHaveText("$60");
  await pp.getByRole("button", { name: "Edit amount" }).click();
  await pp.getByLabel("Amount in dollars").fill("20");
  await pp.getByLabel("Amount in dollars").blur();
  await expect(pp.getByTestId("deposit-amount")).toHaveText("$20");
  await pp.getByRole("button", { name: "Reset amount" }).click();
  await expect(pp.getByTestId("deposit-amount")).toHaveText("$0");
  await expect(pp.getByRole("button", { name: "Continue" })).toBeDisabled();  // below the minimum
  await pp.getByRole("button", { name: "+25" }).click();
  await pp.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/\$25\.00 added \(sandbox test funds\)/)).toBeVisible();
  await expect(page.getByTestId("wallet-balance")).toContainText("25.00");
  await page.getByRole("button", { name: "Close wallet" }).click();

  // Bonus Zone: sandbox accounts start with 30 test diamonds; claim the daily login (+1)
  await page.goto("/bonus-zone");
  await expect(page.getByTestId("diamond-balance")).toHaveText("30");
  await expect(page.getByTestId("zone-bonus-balance")).toHaveText("$0.00");
  await expect(page.getByTestId("boost-banner")).toHaveCount(0);
  await page.getByRole("button", { name: "Claim Daily login" }).click();
  await expect(page.getByTestId("diamond-balance")).toHaveText("31");
  await expect(page.getByRole("button", { name: "Claimed Daily login" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Claim Email" })).toBeDisabled();  // unverifiable tasks stay locked

  // Lucky Shop rewards apply INSTANTLY. $2 free play goes straight to the bonus balance, no agent involved.
  await page.getByRole("button", { name: "What's inside?" }).click();
  await expect(page.getByText("$2 Free Play").first()).toBeVisible();
  await page.getByRole("button", { name: "Open Starter Gift" }).click();
  const gift = page.getByRole("dialog", { name: "Open Starter Gift" });
  await gift.getByRole("button", { name: /^Open for/ }).click();
  await expect(gift.getByTestId("reward-amount")).toHaveText("$2", { timeout: 15000 });
  await expect(gift.getByTestId("reward-note")).toContainText("added to your bonus balance");
  await gift.getByRole("button", { name: "Done" }).click();
  await expect(page.getByTestId("diamond-balance")).toHaveText("26");
  await expect(page.getByTestId("zone-bonus-balance")).toHaveText("$2.00");

  // the 20% box starts a Deposit Boost with a live countdown
  await page.getByRole("button", { name: "Open Crystal Vault" }).click();
  const vault = page.getByRole("dialog", { name: "Open Crystal Vault" });
  await vault.getByRole("button", { name: /^Open for/ }).click();
  await expect(vault.getByTestId("reward-amount")).toHaveText("20%", { timeout: 15000 });
  await expect(vault.getByTestId("reward-note")).toContainText("Deposit Boost active");
  await expect(vault.getByTestId("boost-banner")).toBeVisible();
  await vault.getByRole("button", { name: "Done" }).click();
  await expect(page.getByTestId("diamond-balance")).toHaveText("6");
  await expect(page.getByTestId("boost-banner")).toBeVisible();
  await expect(page.getByTestId("boost-percent")).toHaveText("+20%");
  await expect(page.getByText("Applied").first()).toBeVisible();

  // while the boost lasts every deposit earns extra: deposit $10 -> $10 wallet + $2 bonus
  await page.getByRole("button", { name: "Open wallet" }).click();
  await expect(page.getByTestId("boost-banner")).toHaveCount(2);                       // page + wallet drawer
  await expect(page.getByTestId("bonus-balance")).toHaveText("$2.00");
  await page.getByRole("button", { name: "PayPal" }).click();
  const boosted = page.getByRole("dialog", { name: "PayPal deposit" });
  await boosted.getByRole("button", { name: "Reset amount" }).click();
  await boosted.getByRole("button", { name: "+10" }).click();
  await expect(boosted.getByTestId("deposit-amount")).toHaveText("$10");
  await expect(boosted.getByTestId("boost-preview")).toContainText("+$2.00");
  await expect(boosted.getByTestId("boost-preview")).toContainText("$12.00");
  await boosted.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/\$10\.00 added \+ \$2\.00 bonus \(sandbox test funds\)/)).toBeVisible();
  await expect(page.getByTestId("wallet-balance")).toContainText("35.00");               // 25 + 10 main balance
  await expect(page.getByTestId("bonus-balance")).toHaveText("$4.00");                    // 2 free play + 2 boost bonus
  await page.getByRole("button", { name: "Close wallet" }).click();

  // game access: Get access -> login details -> Add Cash from the wallet
  await page.goto("/games");
  await page.getByRole("button", { name: /^Play / }).first().click();
  await expect(page.getByText("You don't have an account, get your access right now")).toBeVisible();
  await page.getByRole("button", { name: "Get access" }).click();
  await expect(page.getByText("Your login is ready to play!")).toBeVisible();
  await expect(page.getByTestId("home-balance")).toContainText("$0.00");
  await expect(page.getByTestId("last-update")).toContainText("Last update");
  const username = await page.getByTestId("field-username").innerText();
  expect(username).toMatch(/^[a-z]{2}\d{6}$/);
  await expect(page.getByTestId("field-password")).toHaveText("••••••");
  await page.getByRole("button", { name: "Show password" }).click();
  expect((await page.getByTestId("field-password").innerText()).length).toBe(10);
  // reset password: the new one differs; remove login is blocked while the game holds money (checked below)
  await page.getByRole("button", { name: "Reset password" }).click();
  await page.getByTestId("confirm-yes").click();
  await expect(page.getByText(/password was changed/)).toBeVisible();
  await page.getByRole("button", { name: "Add Cash", exact: true }).click();
  await expect(page.getByTestId("balance")).toContainText("$0.00");
  await expect(page.getByTestId("wallet-funds")).toContainText("$35.00");
  await expect(page.getByTestId("bonus-funds")).toContainText("$4.00");
  await expect(page.getByTestId("low-wallet")).toHaveCount(0);                            // wallet is healthy: no nudge
  await page.getByRole("button", { name: "+5" }).click();
  await expect(page.getByTestId("amount")).toHaveText("$15");
  await page.getByRole("button", { name: "Add Cash", exact: true }).click();
  await expect(page.getByText(/\$15\.00 added \(sandbox test credit\)/)).toBeVisible();
  await expect(page.getByTestId("balance")).toContainText("$15.00");
  await expect(page.getByTestId("wallet-funds")).toContainText("$20.00");

  // spend the rest of the wallet; once it is under $1 the bonus balance is one tap away
  await page.getByRole("button", { name: "Edit amount" }).click();
  await page.getByLabel("Amount in dollars").fill("20");
  await page.getByLabel("Amount in dollars").blur();
  await page.getByRole("button", { name: "Add Cash", exact: true }).click();
  await expect(page.getByTestId("wallet-funds")).toContainText("$0.00");
  await expect(page.getByTestId("balance")).toContainText("$35.00");
  await expect(page.getByTestId("low-wallet")).toBeVisible();
  await expect(page.getByTestId("low-wallet")).toContainText("Your wallet is under $1");
  await page.getByTestId("add-all-bonus").click();
  await expect(page.getByText(/\$4\.00 added from your bonus balance/)).toBeVisible();
  await expect(page.getByTestId("balance")).toContainText("$39.00");
  await expect(page.getByTestId("bonus-funds")).toContainText("$0.00");

  // Redeem winnings under the cashout table. Latest deposit $10 -> minimum $50, maximum x12 = $120.
  await page.getByRole("button", { name: "Back" }).click();                              // back to the login panel
  await expect(page.getByTestId("home-balance")).toContainText("$39.00");
  await page.getByTestId("remove-login").click();                                        // money inside: removing is refused
  await page.getByTestId("confirm-yes").click();
  await expect(page.getByText("still has $39.00")).toBeVisible();
  await page.getByRole("button", { name: "Cash Out" }).click();
  await expect(page.getByTestId("redeem-balance")).toHaveText("$39.00");
  await expect(page.getByTestId("redeem-rule")).toContainText("at least $50.00");
  await expect(page.getByTestId("redeem-rule")).toContainText("at most $120.00");
  await expect(page.getByTestId("redeem-reason")).toContainText("at least $50.00");     // $39 is below the minimum
  await expect(page.getByTestId("redeem-submit")).toBeDisabled();
  await page.getByTestId("sandbox-win").click();                                         // +$100 test winnings -> $139
  await expect(page.getByTestId("redeem-balance")).toHaveText("$139.00");
  await expect(page.getByTestId("redeem-payout")).toHaveText("$120.00");
  await expect(page.getByTestId("redeem-voided")).toHaveText("$19.00");                  // above the maximum: voided
  await expect(page.getByTestId("redeem-submit")).toBeDisabled();                        // the void must be confirmed first
  await page.getByTestId("redeem-confirm").check();
  await page.getByTestId("redeem-submit").click();
  await expect(page.getByTestId("redeem-result")).toContainText("$120.00 was added to your wallet");
  await expect(page.getByTestId("redeem-result")).toContainText("$19.00 above your maximum was voided");
  await expect(page.getByTestId("redeem-balance")).toHaveText("$0.00");                  // the whole balance left the game
  await expect(page.getByTestId("redeem-reason")).toContainText("already redeemed");     // one redeem per deposit
  await page.keyboard.press("Escape");

  // the redeemed winnings are in the wallet, and the Cashout tab shows the rules with the player's limits
  await page.getByRole("button", { name: "Open wallet" }).click();
  await expect(page.getByTestId("wallet-balance")).toContainText("120.00");
  await page.getByRole("tab", { name: "Cashout" }).click();
  await expect(page.getByTestId("cashout-rules")).toContainText("latest deposit of $10.00");
  await expect(page.getByTestId("cashout-rules")).toContainText("$50.00");
  await expect(page.getByTestId("cashout-rules")).toContainText("$120.00");
  await expect(page.getByTestId("cashout-rules")).toContainText("voided by the system");
  await page.getByRole("button", { name: "Close wallet" }).click();

  // favorite persists
  await page.getByRole("button", { name: /Add .* to favorites/ }).first().click();
  await page.goto("/games");
  await expect(page.getByRole("button", { name: /Remove .* from favorites/ })).toHaveCount(1);

  // sample special offer (a live promotion) can be claimed once
  await page.goto("/bonus-zone");
  await page.getByRole("button", { name: "Claim reward" }).first().click();
  await expect(page.getByText(/Claim received/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: /Already claimed/ }).first()).toBeDisabled();

  // log out / in
  await page.goto("/");
  await page.getByRole("button", { name: new RegExp(user.slice(0, 8)) }).or(page.locator("header button[aria-haspopup=menu]")).first().click();
  await page.getByRole("menuitem", { name: "Log out" }).click();
  await page.goto("/login");
  await page.getByLabel("Username or email").fill(user);
  await page.getByLabel("Password").fill("Sup3rSecret!x");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
});

test("free spin wheel: locked until a deposit, then one spin, then a 24h cooldown", async ({ page }) => {
  const user = `spin_${Date.now().toString(36)}`;
  await page.goto("/register");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Email").fill(`${user}@example.com`);
  await page.getByLabel("Password").fill("Sup3rSecret!x");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  // no deposit yet: the wheel is locked and says how to unlock it
  await page.goto("/bonus-zone");
  await expect(page.getByText("Spin the wheel and claim your lucky reward")).toBeVisible();
  await expect(page.getByTestId("wheel-timer")).toContainText("Deposit to unlock");
  await expect(page.getByTestId("spin-button")).toHaveCount(0);
  await expect(page.getByText(/% chance/)).toHaveCount(7);                 // Possible Rewards, with the odds shown
  await expect(page.getByText("Freeplay", { exact: true }).first()).toBeVisible();

  // "Deposit now" opens the wallet; a deposit unlocks the spin
  await page.getByTestId("spin-deposit").click();
  await page.getByRole("button", { name: "PayPal" }).click();
  await page.getByRole("dialog", { name: "PayPal deposit" }).getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/added \(sandbox test funds\)/)).toBeVisible();
  await page.getByRole("button", { name: "Close wallet" }).click();

  await page.reload();
  await expect(page.getByTestId("wheel-timer-label")).toHaveText("Time left to spin");
  await expect(page.getByTestId("wheel-timer")).toContainText(/(23|24):\d\d:\d\d/);
  await page.getByTestId("spin-button").click();
  const result = page.getByRole("dialog", { name: "Free spin result" });
  await expect(result).toBeVisible({ timeout: 20000 });
  await expect(result.getByTestId("wheel-note")).toContainText(/diamond|free play|Deposit Boost/i);  // applied instantly
  await result.getByRole("button", { name: "Done" }).click();

  // used: disabled with a countdown to the next spin, and it survives a reload
  await expect(page.getByTestId("wheel-timer-label")).toHaveText("Next spin in");
  await expect(page.getByTestId("spin-button")).toBeDisabled();
  await page.reload();
  await expect(page.getByTestId("wheel-timer-label")).toHaveText("Next spin in");
  await expect(page.getByTestId("spin-button")).toBeDisabled();
});

test("minimum withdrawal is $50: not possible with $25, possible with exactly $50", async ({ page }) => {
  const user = `wd_${Date.now().toString(36)}`;
  await page.goto("/register");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Email").fill(`${user}@example.com`);
  await page.getByLabel("Password").fill("Sup3rSecret!x");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  const depositTwentyFive = async () => {
    await page.getByRole("tab", { name: "Deposit" }).click();
    await page.getByRole("button", { name: "PayPal" }).click();
    const pop = page.getByRole("dialog", { name: "PayPal deposit" });
    await pop.getByRole("button", { name: "Reset amount" }).click();
    await pop.getByRole("button", { name: "+25" }).click();
    await pop.getByRole("button", { name: "Continue" }).click();
    await expect(page.getByText(/\$25\.00 added \(sandbox test funds\)/)).toBeVisible();
  };
  const startCashOut = async () => {
    await page.getByRole("tab", { name: "Cashout" }).click();
    await page.getByRole("button", { name: "CashApp" }).click();
    await page.getByLabel("cashtag").fill("$me");
  };

  await page.getByRole("button", { name: "Open wallet" }).click();
  await depositTwentyFive();
  await expect(page.getByTestId("wallet-balance")).toContainText("25.00");

  // $25 in the wallet: below the $50 minimum, so no withdrawal
  await startCashOut();
  await expect(page.getByTestId("cashout-min-notice")).toContainText("Minimum withdrawal is $50.00");
  await expect(page.getByTestId("cashout-min-notice")).toContainText("$25.00 more");
  await page.getByLabel("Cashout amount in dollars").fill("25");
  await expect(page.getByTestId("cashout-amount-hint")).toContainText("minimum withdrawal is $50.00");
  await expect(page.getByRole("button", { name: /^Cash out/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Withdraw everything/ })).toHaveCount(0);

  // exactly $50 in the wallet: it can be withdrawn
  await depositTwentyFive();
  await expect(page.getByTestId("wallet-balance")).toContainText("50.00");
  await startCashOut();
  await expect(page.getByTestId("cashout-min-notice")).toContainText("You can withdraw up to $50.00 now");
  await page.getByLabel("Cashout amount in dollars").fill("49.99");
  await expect(page.getByTestId("cashout-amount-hint")).toContainText("minimum withdrawal is $50.00");
  await expect(page.getByRole("button", { name: /^Cash out/ })).toBeDisabled();
  await page.getByRole("button", { name: /Withdraw everything/ }).click();
  await expect(page.getByLabel("Cashout amount in dollars")).toHaveValue("50.00");
  await expect(page.getByRole("button", { name: /^Cash out/ })).toBeEnabled();
  await page.getByRole("button", { name: /^Cash out/ }).click();
  await expect(page.getByText(/Cashout requested/)).toBeVisible();
  await expect(page.getByTestId("wallet-balance")).toContainText("0.00");               // the whole $50 is held for the payout
});

test("wrong password shows a generic error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Username or email").fill("nobody");
  await page.getByLabel("Password").fill("not-a-password");
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.locator("[role=alert]:not(#__next-route-announcer__)")).toContainText("Incorrect username/email or password.");
});

test("admin panel has no separate login: signed-out visitors go to the normal login", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("ordinary players get no admin panel link and no access", async ({ page }) => {
  const user = `e2e_${Date.now().toString(36)}`;
  await page.goto("/register");
  await page.getByLabel("Username").fill(user);
  await page.getByLabel("Email").fill(`${user}@example.com`);
  await page.getByLabel("Password").fill("Sup3rSecret!x");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
  await page.locator("header button[aria-haspopup=menu]").click();
  await expect(page.getByRole("menuitem", { name: "Admin panel" })).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByText("You don't have access to the admin panel")).toBeVisible();
});

test("private pages are noindex", async ({ page }) => {
  for (const path of ["/dashboard", "/admin", "/reset-password"]) {
    await page.goto(path);
    await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  }
});
