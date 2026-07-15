const { test, expect } = require('@playwright/test');

const labels = {
  unknown: 'Unknown',
  waiting: 'Waiting',
  action_required: 'Action required',
  healthy: 'Healthy',
  failed: 'Failed',
};

function statusFixture(status = 'healthy') {
  const counts = {
    unknown: 0,
    waiting: 0,
    action_required: 0,
    configuring: 0,
    healthy: 0,
    failed: 0,
  };
  counts[status] = 1;
  return {
    running: false,
    lastStartedAt: 1,
    lastCompletedAt: 1,
    counts,
    services: [{
      id: 'sonarr',
      name: 'Sonarr',
      status,
      detail: `Fixture service is ${status}`,
      link: 'http://umbrel.local:30985',
      checked_at: 1,
      dependencies: [],
      waitingOn: [],
    }],
    events: [],
  };
}

const confirmedSetup = {
  phase: 'confirmed',
  confirmed: true,
  canConfirm: false,
  requiredCount: 13,
  detectedCount: 13,
  detectionComplete: true,
  apps: [],
};

function modularSetup() {
  return {
    ...confirmedSetup,
    phase: 'detect',
    confirmed: false,
    canConfirm: false,
    detectionComplete: false,
    enabledServices: ['umbrelarr', 'prowlarr', 'qbittorrent', 'sonarr'],
    modules: [
      { id: 'prowlarr', name: 'Prowlarr', role: 'indexer_manager', enabled: true, required: true },
      { id: 'qbittorrent', name: 'qBittorrent', role: 'download_client', enabled: true, required: false },
      { id: 'sonarr', name: 'Sonarr', role: 'media_manager', enabled: true, required: false },
      { id: 'privado-vpn', name: 'Privado VPN', role: 'vpn_provider', enabled: true, required: false },
    ],
    vpnProvider: 'privado',
    vpnProviders: [
      { id: 'privado', name: 'Privado VPN', service_id: 'privado-vpn' },
      { id: 'direct', name: 'No VPN', service_id: null },
    ],
    profiles: [
      { id: 'core', name: 'Core only', description: 'Prowlarr only.', enabledServices: ['prowlarr'] },
      { id: 'tv-torrent', name: 'TV with torrents', description: 'Prowlarr, qBittorrent, and Sonarr.', enabledServices: ['prowlarr', 'qbittorrent', 'sonarr'] },
    ],
  };
}

async function mockDashboard(page, status = 'healthy', delay = 0) {
  await page.route('**/api/setup', route => route.fulfill({ json: confirmedSetup }));
  await page.route('**/api/status', async route => {
    if (delay) await new Promise(resolve => setTimeout(resolve, delay));
    await route.fulfill({ json: statusFixture(status) });
  });
}

async function expectNoDocumentOverflow(page) {
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

function storageFixture() {
  const definitions = [
    ['sonarr', 'TV', 'HD'],
    ['sonarr-4k', 'TV', '4K'],
    ['radarr', 'Movies', 'HD'],
    ['radarr-4k', 'Movies', '4K'],
    ['lidarr', 'Music', 'Standard'],
  ];
  const roots = Object.fromEntries(definitions.map(([slug]) => [slug, `/downloads/${slug}`]));
  return {
    mode: 'local',
    roots,
    rootIds: {},
    actionRequired: false,
    presets: { local: roots, network: roots },
    candidates: Object.fromEntries(definitions.map(([slug], index) => [
      slug,
      [{ id: index + 10, path: `/existing/${slug}` }],
    ])),
    libraries: definitions.map(([key, name, variant]) => ({
      key, name, variant, id: key, category: key, root: roots[key], apps: [],
    })),
  };
}

test('shows a loading state without overflowing the viewport', async ({ page }) => {
  await mockDashboard(page, 'healthy', 600);
  await page.goto('/services', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#serviceGrid .empty')).toContainText('Loading managed service health');
  await expectNoDocumentOverflow(page);
  await expect(page.locator('.service-card.healthy')).toBeVisible();
});

for (const status of Object.keys(labels)) {
  test(`renders the ${status} service state without document overflow`, async ({ page }) => {
    await mockDashboard(page, status);
    await page.goto('/services');
    const card = page.locator(`.service-card.${status}`);
    await expect(card).toBeVisible();
    await expect(card.locator('.status')).toContainText(labels[status]);
    await expectNoDocumentOverflow(page);
  });
}

test('supports keyboard filtering and service navigation with visible focus', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/services');
  await expect(page.locator('.service-card.healthy')).toBeVisible();

  await page.locator('#serviceSearch').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#serviceStateFilter')).toBeFocused();
  await page.keyboard.press('Tab');
  const card = page.locator('.service-card').first();
  await expect(card).toBeFocused();
  const outline = await card.evaluate(element => {
    const style = getComputedStyle(element);
    return { style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
  });
  expect(outline.style).not.toBe('none');
  expect(outline.width).toBeGreaterThan(0);
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/services\/sonarr$/);
});

test('submits explicit setup choices and the one-time qBittorrent credential', async ({ page }) => {
  const modular = modularSetup();
  const setup = {
    ...modular,
    phase: 'ready',
    confirmed: false,
    canConfirm: true,
    enabledServices: [
      'umbrelarr', 'prowlarr', 'qbittorrent', 'sonarr', 'sonarr-4k',
      'radarr', 'radarr-4k', 'lidarr',
    ],
    modules: [
      ...modular.modules,
      { id: 'sonarr-4k', name: 'Sonarr 4K', role: 'media_manager', enabled: true, required: false },
      { id: 'radarr', name: 'Radarr', role: 'media_manager', enabled: true, required: false },
      { id: 'radarr-4k', name: 'Radarr 4K', role: 'media_manager', enabled: true, required: false },
      { id: 'lidarr', name: 'Lidarr', role: 'media_manager', enabled: true, required: false },
    ],
    apps: [{
      id: 'qbittorrent',
      name: 'qBittorrent',
      reachable: true,
      credentials: false,
      action: 'temporary_password_required',
      detail: 'A one-time password may be required',
      link: 'http://umbrel.local:30983',
    }],
  };
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/confirm');
  await page.route('**/api/setup/confirm', route => route.fulfill({ json: confirmedSetup }));

  await page.goto('/setup');
  await page.getByLabel('Adopt existing roots').check();
  const roots = page.locator('[data-setup-root]');
  await expect(roots).toHaveCount(5);
  for (let index = 0; index < 5; index += 1) {
    await roots.nth(index).selectOption(String(index + 10));
  }
  await page.locator('#qbittorrentUsername').fill('admin');
  await page.locator('#qbittorrentTemporaryPassword').fill('temporary-fixture-secret');
  await page.locator('#confirmSetup').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('storageMode')).toBe('adopt');
  expect(body.get('qbittorrentUsername')).toBe('admin');
  expect(body.get('qbittorrentTemporaryPassword')).toBe('temporary-fixture-secret');
  expect(JSON.parse(body.get('rootIds'))).toEqual({
    sonarr: 10,
    'sonarr-4k': 11,
    radarr: 12,
    'radarr-4k': 13,
    lidarr: 14,
  });
});

test('detects only the selected service modules and VPN provider', async ({ page }) => {
  const setup = modularSetup();
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: setup }));

  await page.goto('/setup');
  const modules = page.locator('[data-module]');
  await expect(modules).toHaveCount(3);
  await page.locator('[data-module][value="qbittorrent"]').uncheck();
  await page.locator('#vpnProvider').selectOption('direct');
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('vpnProvider')).toBe('direct');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'sonarr']);
  await expectNoDocumentOverflow(page);
});

test('renders Jellyfin and Plex as opt-in modules with actionable credential states', async ({ page }) => {
  const modular = modularSetup();
  const setup = {
    ...modular,
    enabledServices: [...modular.enabledServices, 'jellyfin', 'plex'],
    modules: [
      ...modular.modules,
      { id: 'jellyfin', name: 'Jellyfin', role: 'media_server', enabled: true, required: false },
      { id: 'plex', name: 'Plex', role: 'media_server', enabled: true, required: false },
    ],
    apps: [
      {
        id: 'jellyfin', name: 'Jellyfin', reachable: true, credentials: false,
        action: 'create_api_key', detail: 'Create a Jellyfin API key named umbrelarr',
        link: 'http://umbrel.local:8096',
      },
      {
        id: 'plex', name: 'Plex', reachable: true, credentials: false,
        action: 'claim_server', detail: 'Claim or sign in to this Plex server',
        link: 'http://umbrel.local:32400',
      },
    ],
  };
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));

  await page.goto('/setup');

  await expect(page.locator('[data-module][value="jellyfin"]')).toBeChecked();
  await expect(page.locator('[data-module][value="plex"]')).toBeChecked();
  await expect(page.locator('#setupApps')).toContainText('Create API key');
  await expect(page.locator('#setupApps')).toContainText('Claim server');
  await expectNoDocumentOverflow(page);
});

test('applies a starting profile without coupling it to the VPN provider', async ({ page }) => {
  const setup = modularSetup();
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: setup }));

  await page.goto('/setup');
  await page.locator('#stackProfile').selectOption('core');
  await expect(page.locator('[data-module][value="qbittorrent"]')).not.toBeChecked();
  await expect(page.locator('[data-module][value="sonarr"]')).not.toBeChecked();
  await expect(page.locator('#setupStorageOptions')).toBeHidden();
  await expect(page.locator('#qbittorrentCredentials')).toBeHidden();
  await expect(page.locator('#vpnProvider')).toHaveValue('privado');
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr']);
  expect(body.get('vpnProvider')).toBe('privado');
  await expectNoDocumentOverflow(page);
});

test('contains dependency graph overflow inside its keyboard-scrollable region', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'narrow-chromium', 'Narrow-layout behavior');
  await mockDashboard(page);
  await page.goto('/dependencies');
  const scroller = page.locator('.graph-scroll');
  await expect(scroller).toBeVisible();
  await scroller.focus();
  await expect(scroller).toBeFocused();
  const before = await scroller.evaluate(element => ({
    left: element.scrollLeft,
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(before.scrollWidth).toBeGreaterThan(before.clientWidth);
  await page.keyboard.press('ArrowRight');
  await expect.poll(() => scroller.evaluate(element => element.scrollLeft)).toBeGreaterThan(before.left);
  await expectNoDocumentOverflow(page);
});
