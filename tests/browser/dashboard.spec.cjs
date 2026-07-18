const { test, expect } = require('@playwright/test');

const labels = {
  unknown: 'Unknown',
  waiting: 'Waiting',
  action_required: 'Action required',
  configuring: 'Configuring',
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
      role: 'media_manager',
      status,
      detail: `Fixture service is ${status}`,
      link: 'http://umbrel.local:30985',
      checked_at: Math.floor(Date.now() / 1000),
      checks: [
        { at: Math.floor(Date.now() / 1000) - 60, status: 'waiting' },
        { at: Math.floor(Date.now() / 1000), status },
      ],
      container: {
        state: 'running',
        health: 'healthy',
        name: 'sonarr_server_1',
        updatedAt: Math.floor(Date.now() / 1000),
      },
      resources: {
        source: 'docker',
        updatedAt: Math.floor(Date.now() / 1000),
        cpu: { percent: 31 },
        memory: { percent: 46, usedBytes: 512 * 1024 * 1024, totalBytes: 1024 * 1024 * 1024 },
        blockIo: { readBytes: 12 * 1024 * 1024, writeBytes: 4 * 1024 * 1024 },
        network: { rxBytes: 1536 * 1024, txBytes: 512 * 1024 },
      },
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
  requiredCount: 3,
  detectedCount: 3,
  detectionComplete: false,
  configurationChanged: false,
  enabledServices: ['umbrelarr', 'prowlarr', 'qbittorrent', 'sonarr'],
  activeEnabledServices: ['umbrelarr', 'prowlarr', 'qbittorrent', 'sonarr', 'privado-vpn'],
  modules: [
    { id: 'prowlarr', name: 'Prowlarr', role: 'indexer_manager', enabled: true, active: true, required: true },
    { id: 'qbittorrent', name: 'qBittorrent', role: 'download_client', enabled: true, active: true, required: false },
    { id: 'sonarr', name: 'Sonarr', role: 'media_manager', enabled: true, active: true, required: false },
    { id: 'jellyfin', name: 'Jellyfin', role: 'media_server', enabled: false, active: false, required: false },
    { id: 'privado-vpn', name: 'Privado VPN', role: 'vpn_provider', enabled: true, active: true, required: false },
  ],
  vpnProvider: 'privado',
  vpnProviders: [
    { id: 'privado', name: 'Privado VPN', description: 'Route download traffic through Privado.', service_id: 'privado-vpn' },
    { id: 'direct', name: 'No VPN', description: 'Use the direct app connection.', service_id: null },
  ],
  vpnStatus: { ready: true, status: 'managed_app', detail: 'Privado health is managed after connection' },
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
  };
}

function freshSetupFixture() {
  return {
    phase: 'detect',
    confirmed: false,
    canConfirm: false,
    requiredCount: 1,
    selectedCount: 1,
    detectedCount: 0,
    detectionComplete: false,
    configurationChanged: false,
    enabledServices: ['umbrelarr', 'prowlarr'],
    activeEnabledServices: ['umbrelarr', 'prowlarr'],
    modules: [
      { id: 'prowlarr', name: 'Prowlarr', role: 'indexer_manager', enabled: true, active: true, required: true, requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://prowlarr:9696', credentialConfigured: true, credentialSource: 'environment', environmentCredentialConfigured: true, apiKeyEnvironmentVariable: 'UMBREL_ARR_PROWLARR_API_KEY' },
      { id: 'privado-vpn', name: 'Privado VPN', role: 'vpn_provider', enabled: false, active: false, required: false, requires_api_key: false, connectionUrl: 'http://privado:8080' },
      { id: 'flaresolverr', name: 'FlareSolverr', role: 'challenge_solver', enabled: false, active: false, required: false, requires_api_key: false, connectionUrl: 'http://flaresolverr:8191' },
      { id: 'qbittorrent', name: 'qBittorrent', role: 'download_client', enabled: false, active: false, required: false, requires_api_key: false, connectionUrl: 'http://qbittorrent:8080' },
      { id: 'sonarr', name: 'Sonarr', role: 'media_manager', enabled: false, active: false, required: false, requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://sonarr:8989', credentialConfigured: false, credentialSource: 'missing', environmentCredentialConfigured: false, apiKeyEnvironmentVariable: 'UMBREL_ARR_SONARR_API_KEY' },
      { id: 'bazarr', name: 'Bazarr', role: 'subtitle_manager', enabled: false, active: false, required: false, requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://bazarr:6767', credentialConfigured: false, credentialSource: 'missing', environmentCredentialConfigured: false, apiKeyEnvironmentVariable: 'UMBREL_ARR_BAZARR_API_KEY' },
      { id: 'jellyfin', name: 'Jellyfin', role: 'media_server', enabled: false, active: false, required: false, requires_api_key: true, credentialSetup: 'jellyfin_admin', connectionUrl: 'http://jellyfin:8096', credentialConfigured: false, credentialSource: 'missing', environmentCredentialConfigured: false, apiKeyEnvironmentVariable: 'UMBREL_ARR_JELLYFIN_API_KEY' },
    ],
    vpnProvider: 'direct',
    vpnProviders: [
      { id: 'privado', name: 'Privado VPN', service_id: 'privado-vpn' },
      { id: 'direct', name: 'No VPN', service_id: null },
    ],
    vpnStatus: { ready: true, status: 'healthy', detail: 'Direct app connections selected' },
    apps: [],
  };
}

function sabnzbdSetupFixture() {
  const setup = freshSetupFixture();
  return {
    ...setup,
    modules: [
      ...setup.modules,
      { id: 'sabnzbd', name: 'SABnzbd', role: 'download_client', enabled: false, active: false, required: false, requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://sabnzbd:8080', credentialConfigured: false, credentialSource: 'missing', environmentCredentialConfigured: false, apiKeyEnvironmentVariable: 'UMBREL_ARR_SABNZBD_API_KEY' },
    ],
  };
}

function completeCatalogSetupFixture() {
  const setup = freshSetupFixture();
  const extraModules = [
    { id: 'sabnzbd', name: 'SABnzbd', role: 'download_client', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://sabnzbd:8080', apiKeyEnvironmentVariable: 'UMBREL_ARR_SABNZBD_API_KEY' },
    { id: 'sonarr-4k', name: 'Sonarr 4K', role: 'media_manager', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://sonarr4k:8989', apiKeyEnvironmentVariable: 'UMBREL_ARR_SONARR_4K_API_KEY' },
    { id: 'radarr', name: 'Radarr', role: 'media_manager', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://radarr:7878', apiKeyEnvironmentVariable: 'UMBREL_ARR_RADARR_API_KEY' },
    { id: 'radarr-4k', name: 'Radarr 4K', role: 'media_manager', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://radarr4k:7878', apiKeyEnvironmentVariable: 'UMBREL_ARR_RADARR_4K_API_KEY' },
    { id: 'lidarr', name: 'Lidarr', role: 'media_manager', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://lidarr:8686', apiKeyEnvironmentVariable: 'UMBREL_ARR_LIDARR_API_KEY' },
    { id: 'overseerr', name: 'Overseerr', role: 'request_manager', requires_api_key: true, credentialSetup: 'generated', connectionUrl: 'http://overseerr:5055', apiKeyEnvironmentVariable: 'UMBREL_ARR_OVERSEERR_API_KEY' },
    { id: 'profilarr', name: 'Profilarr', role: 'profile_manager', requires_api_key: false, credentialSetup: 'none', connectionUrl: 'http://profilarr:6868' },
    { id: 'plex', name: 'Plex', role: 'media_server', requires_api_key: true, credentialSetup: 'existing_token', connectionUrl: 'http://plex:32400', apiKeyEnvironmentVariable: 'UMBREL_ARR_PLEX_API_KEY' },
  ].map(module => ({
    ...module,
    enabled: false,
    active: false,
    required: false,
    credentialConfigured: false,
    credentialSource: 'missing',
    environmentCredentialConfigured: false,
  }));
  return {
    ...setup,
    modules: [...setup.modules, ...extraModules],
  };
}

function dockerInventorySetupFixture() {
  const setup = freshSetupFixture();
  return {
    ...setup,
    docker: { configured: true, available: true, updatedAt: 100, error: null },
    modules: setup.modules.map(module => {
      if (module.id === 'qbittorrent') return {
        ...module,
        installed: true,
        container: { state: 'running', health: 'healthy' },
      };
      if (module.id === 'sonarr') return {
        ...module,
        installed: true,
        container: { state: 'exited', health: null },
      };
      if (module.id === 'bazarr') return {
        ...module,
        installed: false,
        container: null,
      };
      return { ...module, installed: false, container: null };
    }),
  };
}

function freshStatusFixture() {
  return {
    running: false,
    lastStartedAt: 0,
    lastCompletedAt: 0,
    counts: { unknown: 0, waiting: 1, action_required: 1, configuring: 0, healthy: 0, failed: 0 },
    services: [
      {
        id: 'umbrelarr', name: 'umbrelarr', role: 'control_plane', status: 'action_required',
        detail: 'Choose the apps you installed, then check and connect them', link: '#',
        checked_at: 0, checks: [], resources: {}, dependencies: [], waitingOn: [],
      },
      {
        id: 'prowlarr', name: 'Prowlarr', role: 'indexer_manager', status: 'waiting',
        detail: 'Waiting for connection setup before the first health check', link: '#',
        checked_at: 0, checks: [], resources: {}, dependencies: [], waitingOn: [],
      },
    ],
    events: [],
  };
}

async function mockDashboard(page, status = 'healthy', delay = 0, mountMismatch = false) {
  await page.route('**/api/setup', route => route.fulfill({ json: confirmedSetup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  await page.route('**/api/storage/browse**', route => {
    const path = new URL(route.request().url()).searchParams.get('path') || '/';
    return route.fulfill({ json: filesystemFixture(path, mountMismatch) });
  });
  await page.route('**/api/status', async route => {
    if (delay) await new Promise(resolve => setTimeout(resolve, delay));
    await route.fulfill({ json: statusFixture(status) });
  });
}

function filesystemFixture(path = '/', mountMismatch = false) {
  const folders = {
    '/': [
      { name: 'downloads', path: '/downloads' },
      { name: 'media', path: '/media' },
    ],
    '/downloads': [
      { name: 'shows', path: '/downloads/shows' },
      { name: 'movies', path: '/downloads/movies' },
    ],
    '/downloads/shows': [{ name: 'Archive', path: '/downloads/shows/Archive' }],
    '/downloads/shows/Archive': [],
    '/media': [{ name: 'sonarr', path: '/media/sonarr' }],
    '/media/sonarr': [],
  };
  const parent = path === '/' ? null : (path.slice(0, path.lastIndexOf('/')) || '/');
  const services = [
    ['sonarr', 'Sonarr'],
    ['sonarr-4k', 'Sonarr 4K'],
    ['radarr', 'Radarr'],
    ['radarr-4k', 'Radarr 4K'],
    ['lidarr', 'Lidarr'],
  ];
  const mounts = services.map(([id, name]) => ({
    id,
    name,
    status: mountMismatch && id === 'radarr' ? 'missing' : 'match',
    detail: mountMismatch && id === 'radarr' ? 'Path is not available' : 'Same path is available',
  }));
  return {
    path,
    parent,
    directories: folders[path] || [],
    service: 'Sonarr',
    mounts,
    allMounted: mounts.every(item => item.status === 'match'),
  };
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
    ['sonarr', 'tv', 'TV', 'HD', 'tv', '/downloads/shows'],
    ['sonarr-4k', 'tv-4k', 'TV', '4K', 'tv-4k', '/downloads/shows-4k'],
    ['radarr', 'movies', 'Movies', 'HD', 'movies', '/downloads/movies'],
    ['radarr-4k', 'movies-4k', 'Movies', '4K', 'movies-4k', '/downloads/movies-4k'],
    ['lidarr', 'music', 'Music', 'Standard', 'music', '/downloads/music'],
  ];
  const roots = Object.fromEntries(definitions.map(([slug, , , , , root]) => [slug, root]));
  const network = Object.fromEntries(definitions.map(([slug, , , , , root]) => [slug, root.replace('/downloads/', '/network/')]));
  return {
    mode: 'local',
    roots,
    rootIds: Object.fromEntries(definitions.map(([slug], index) => [slug, index + 10])),
    actionRequired: false,
    presets: { local: roots, network },
    candidates: Object.fromEntries(definitions.map(([slug], index) => [
      slug,
      [
        { id: index + 10, path: roots[slug] },
        { id: index + 20, path: `/media/${slug}` },
      ],
    ])),
    libraries: definitions.map(([key, id, name, variant, category], index) => ({
      key, id, name, variant, category, root: roots[key], source: 'local',
      rootId: index + 10,
      candidates: [
        { id: index + 10, path: roots[key] },
        { id: index + 20, path: `/media/${key}` },
      ],
      apps: key === 'sonarr' ? ['sonarr'] : [],
    })),
  };
}

test('shows a loading state without overflowing the viewport', async ({ page }) => {
  await mockDashboard(page, 'healthy', 600);
  await page.goto('/services', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('#serviceGrid .empty')).toContainText('Loading service inventory');
  await expectNoDocumentOverflow(page);
  await expect(page.locator('.service-card.healthy')).toBeVisible();
});

test('does not present catalog defaults as local Docker services', async ({ page }) => {
  const status = freshStatusFixture();
  status.services = [status.services[0]];
  status.counts = { unknown: 0, waiting: 0, action_required: 1, configuring: 0, healthy: 0, failed: 0 };
  status.inventory = {
    mode: 'direct', configured: false, available: false, updatedAt: 0,
    error: null, discoveredCount: 0,
  };
  await page.route('**/api/status', route => route.fulfill({ json: status }));
  await page.route('**/api/setup', route => route.fulfill({ json: freshSetupFixture() }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));

  await page.goto('/services');

  await expect(page.locator('.scope-bar')).toHaveCount(0);
  await expect(page.locator('#inventoryNotice')).toContainText('Local Docker inventory is not connected');
  await expect(page.locator('#serviceGrid .service-card')).toHaveCount(1);
  await expect(page.locator('#serviceGrid')).toContainText('umbrelarr');
  await expect(page.locator('#serviceGrid')).not.toContainText('Prowlarr');
  await expect(page.locator('#serviceGrid a[href^="/services/"]')).toHaveCount(0);
  await expect(page.locator('#serviceCount')).toHaveText('1 of 1 visible services');
  await expectNoDocumentOverflow(page);
});

test('shows a discovered unmanaged local service with one Add action', async ({ page }) => {
  const service = statusFixture('unknown').services[0];
  service.managed = false;
  service.discoverySource = 'docker';
  service.detail = 'Installed locally and available to manage';
  const status = {
    ...statusFixture('unknown'),
    services: [service],
    inventory: {
      mode: 'docker', configured: true, available: true,
      updatedAt: Math.floor(Date.now() / 1000), error: null, discoveredCount: 1,
    },
  };
  const setup = freshSetupFixture();
  setup.modules = setup.modules.map(module => module.id === 'sonarr' ? {
    ...module,
    installed: true,
    container: { state: 'running', health: 'healthy' },
  } : module);
  await page.route('**/api/status', route => route.fulfill({ json: status }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));

  await page.goto('/services');

  await expect(page.locator('.scope-bar')).toHaveCount(0);
  await expect(page.locator('#inventoryNotice')).toBeHidden();
  const card = page.locator('.service-card[data-managed="false"]');
  await expect(card).toContainText('Installed locally and available to manage');
  await expect(card.locator('.service-resources-head')).toContainText('Docker');
  await expect(card.getByRole('button', { name: 'Add local Sonarr to managed services' })).toHaveCount(1);
  await card.getByRole('button', { name: 'Add local Sonarr to managed services' }).click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Sonarr');
  await expectNoDocumentOverflow(page);
});

for (const status of Object.keys(labels)) {
  test(`renders the ${status} service state without document overflow`, async ({ page }) => {
    await mockDashboard(page, status);
    await page.goto('/services');
    const card = page.locator(`.service-card.${status}`);
    await expect(card).toBeVisible();
    await expect(card.locator('.status')).toContainText(labels[status]);
    await expect(card.locator('.service-icon img')).toBeVisible();
    await expect(card.locator('.runtime-state.running')).toHaveText('Running');
    await expect(card.locator('.runtime-meta')).toContainText('Docker');
    await expect(card.locator('.runtime-meta')).toContainText('healthy');
    await expect(card.locator('.service-resources')).toContainText('Resources');
    await expect(card.locator('.service-resources-head')).toContainText('Live · Docker');
    await expect(card.locator('.resource-gauge')).toHaveCount(2);
    await expect(card.locator('.resource-gauge').first()).toHaveAttribute('role', 'meter');
    await expect(card.locator('.resource-gauge').first()).toHaveAttribute('aria-valuenow', '31');
    await expect(card.locator('.resource-io')).toContainText('12 MB read · 4 MB written');
    await expect(card.locator('.resource-io')).toContainText('1.5 MB in · 512 KB out');
    await expect(card.locator('.resource-io')).not.toContainText('%');
    await expect(card.locator('.service-quick-metrics')).toContainText('Samples');
    await expect(card.locator('.service-card-foot')).toHaveCount(0);
    await expectNoDocumentOverflow(page);
  });
}

test('shows Docker multicore CPU without clamping the reported value', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/status', route => {
    const fixture = statusFixture();
    fixture.services[0].resources.cpu = {
      percent: 200,
      onlineCpus: 8,
      capacityPercent: 800,
    };
    return route.fulfill({ json: fixture });
  });
  await page.goto('/services');

  const cpu = page.locator('.service-card').first().locator('.resource-gauge').first();
  await expect(cpu.locator('strong')).toHaveText('200%');
  await expect(cpu).toHaveAttribute('aria-valuemax', '800');
  await expect(cpu).toHaveAttribute('aria-valuenow', '200');
  await expect(cpu).toHaveAttribute('aria-valuetext', /2\.0 of 8 CPU cores/);
  await expect(cpu.locator('.resource-gauge-fill')).toHaveAttribute('style', /--resource-value:25%/);
});

test('shows unavailable resource gauges without implying zero usage', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/status', route => {
    const fixture = statusFixture();
    delete fixture.services[0].container;
    fixture.services[0].resources = {};
    return route.fulfill({ json: fixture });
  });
  await page.goto('/services');
  const card = page.locator('.service-card').first();
  await expect(card.locator('.runtime-state.unavailable')).toHaveText('Unavailable');
  await expect(card.locator('.runtime-meta')).toHaveText('Docker data unavailable');
  await expect(card.locator('.service-resources-head')).toContainText('Unavailable · Source unavailable · time unavailable');
  await expect(card.locator('.resource-gauge.unavailable')).toHaveCount(2);
  await expect(card.locator('.resource-gauge').first()).not.toHaveAttribute('aria-valuenow', /.+/);
  await expect(card.locator('.resource-io dd.unavailable')).toHaveCount(2);
  await expectNoDocumentOverflow(page);
});

test('marks stopped containers and retained Docker telemetry as a last sample', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/status', route => {
    const fixture = statusFixture();
    const sampledAt = Math.floor(Date.now() / 1000) - 30;
    fixture.services[0].container = {
      state: 'exited',
      health: null,
      name: 'sonarr_server_1',
      updatedAt: sampledAt,
    };
    fixture.services[0].resources.sampleState = 'last_sample';
    fixture.services[0].resources.updatedAt = sampledAt;
    return route.fulfill({ json: fixture });
  });
  await page.goto('/services');
  const card = page.locator('.service-card').first();
  await expect(card.locator('.runtime-state.stopped')).toHaveText('Stopped');
  await expect(card.locator('.service-resources-head')).toContainText('Last sample · Docker');
  await expect(card.locator('.resource-gauge.stale')).toHaveCount(2);
  await expectNoDocumentOverflow(page);
});

test('marks retained telemetry as a last sample when live Docker stats are unavailable', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/status', route => {
    const fixture = statusFixture();
    const sampledAt = Math.floor(Date.now() / 1000) - 30;
    fixture.services[0].container.updatedAt = Math.floor(Date.now() / 1000);
    fixture.services[0].resources.sampleState = 'last_sample';
    fixture.services[0].resources.updatedAt = sampledAt;
    return route.fulfill({ json: fixture });
  });
  await page.goto('/services');
  const card = page.locator('.service-card').first();
  await expect(card.locator('.runtime-state.running')).toHaveText('Running');
  await expect(card.locator('.service-resources-head')).toContainText('Last sample · Docker');
  await expect(card.locator('.resource-gauge.stale')).toHaveCount(2);
  await expectNoDocumentOverflow(page);
});

test('keeps stale and partial Docker telemetry visibly uncertain', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/status', route => {
    const fixture = statusFixture();
    const sampledAt = Math.floor(Date.now() / 1000) - 5 * 60;
    fixture.services[0].container.updatedAt = sampledAt;
    fixture.services[0].resources = {
      source: 'docker',
      updatedAt: sampledAt,
      cpu: { percent: 18 },
      memory: null,
      blockIo: { readBytes: 2048, writeBytes: 1024 },
      network: null,
    };
    return route.fulfill({ json: fixture });
  });
  await page.goto('/services');
  const card = page.locator('.service-card').first();
  await expect(card.locator('.runtime-state.running.stale')).toHaveText('Running');
  await expect(card.locator('.runtime-meta.stale')).toContainText('5m ago');
  await expect(card.locator('.service-resources-head small.stale')).toContainText('Stale, partial · Docker · 5m ago');
  await expect(card.locator('.resource-gauge')).toHaveCount(2);
  await expect(card.locator('.resource-gauge.unavailable')).toHaveCount(1);
  await expect(card.locator('.resource-io')).toContainText('2 KB read · 1 KB written');
  await expect(card.locator('.resource-io dd.unavailable')).toHaveCount(1);
  await expectNoDocumentOverflow(page);
});

test('only enables catalog services that Docker reports installed and running', async ({ page }) => {
  const setup = dockerInventorySetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));

  await page.goto('/services');
  await page.locator('#manageServices').click();

  const running = page.locator('[data-module-id="qbittorrent"]');
  await expect(running).toHaveAttribute('data-install-state', 'running');
  await expect(running.locator('.module-store-state')).toHaveText('Installed and running');
  await expect(running.getByRole('button', { name: 'Add qBittorrent' })).toBeEnabled();

  const stopped = page.locator('[data-module-id="sonarr"]');
  await expect(stopped).toHaveAttribute('data-install-state', 'stopped');
  await expect(stopped.locator('.module-store-state')).toContainText('Stopped');
  await expect(stopped.locator('.module-store-state')).toContainText('start the container first');
  await expect(stopped.getByRole('button', { name: 'Add Sonarr' })).toBeDisabled();

  const missing = page.locator('[data-module-id="bazarr"]');
  await expect(missing).toHaveAttribute('data-install-state', 'not-installed');
  await expect(missing.locator('.module-store-state')).toContainText('Not installed');
  await expect(missing.locator('.module-store-state')).toContainText('container platform');
  await expect(missing.getByRole('button', { name: 'Add Bazarr' })).toBeDisabled();

  const fallback = page.locator('[data-module-id="flaresolverr"]');
  await expect(fallback).toHaveAttribute('data-install-state', 'not-installed');
  await expect(fallback.locator('.module-store-state')).toContainText('Not installed');
  await expect(fallback.getByRole('button', { name: 'Add FlareSolverr' })).toBeDisabled();
  await expect(page.locator('#serviceCatalogTitle')).toHaveText('Local services');
  await expect(page.locator('#serviceTypeSummary')).toContainText('1 of 6 installed services ready to add');
  await expectNoDocumentOverflow(page);
});

test('does not let a deep link bypass authoritative Docker installation state', async ({ page }) => {
  const setup = dockerInventorySetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));

  await page.goto('/services?add=bazarr');

  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('#serviceChooseStep')).toBeVisible();
  await expect(page.locator('#serviceConnectStep')).toBeHidden();
  await expect(page.locator('[data-module-id="bazarr"] .module-store-state')).toContainText('Not installed');
  await expect(page.getByRole('button', { name: 'Add Bazarr' })).toBeDisabled();
  await expect(page).toHaveURL(/\/services$/);
  expect(new URL(page.url()).search).toBe('');
  await expectNoDocumentOverflow(page);
});

test('supports keyboard filtering and the single service action with visible focus', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/services');
  await expect(page.locator('.service-card.healthy')).toBeVisible();

  await page.locator('#serviceSearch').focus();
  await page.keyboard.press('Tab');
  await expect(page.locator('#serviceStateFilter')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('#manageServices')).toBeFocused();
  await page.keyboard.press('Tab');
  const action = page.getByRole('button', { name: 'Remove Sonarr from managed services' });
  await expect(action).toBeFocused();
  const outline = await action.evaluate(element => {
    const style = getComputedStyle(element);
    return { style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
  });
  expect(outline.style).not.toBe('none');
  expect(outline.width).toBeGreaterThan(0);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'Stop managing Sonarr?' })).toBeVisible();
  await expect(page).toHaveURL(/\/services$/);
});

test('connects a first service without exposing unselected catalog defaults', async ({ page }) => {
  const fresh = freshSetupFixture();
  const reviewed = {
    ...fresh,
    phase: 'ready',
    canConfirm: true,
    requiredCount: 2,
    selectedCount: 2,
    detectedCount: 2,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'sonarr'],
    modules: fresh.modules.map(module => ({
      ...module,
      enabled: module.id === 'prowlarr' || module.id === 'sonarr',
      ...(module.id === 'sonarr' ? { credentialConfigured: true, credentialSource: 'managed_config' } : {}),
    })),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: '#' },
      { id: 'sonarr', name: 'Sonarr', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: '#' },
    ],
  };
  const applied = {
    ...reviewed,
    phase: 'confirmed',
    confirmed: true,
    canConfirm: false,
    configurationChanged: false,
    activeEnabledServices: reviewed.enabledServices,
  };
  let setupResponse = fresh;
  let statusResponse = freshStatusFixture();
  await page.route('**/api/status', route => route.fulfill({ json: statusResponse }));
  await page.route('**/api/setup', route => route.fulfill({ json: setupResponse }));
  const detectRequest = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => {
    setupResponse = reviewed;
    return route.fulfill({ json: reviewed });
  });
  const confirmRequest = page.waitForRequest('**/api/setup/confirm');
  await page.route('**/api/setup/confirm', route => {
    setupResponse = applied;
    statusResponse = statusFixture('healthy');
    return route.fulfill({ json: applied });
  });

  await page.goto('/services');
  await expect(page.locator('.service-card')).toHaveCount(2);
  await expect(page.locator('#serviceGrid')).not.toContainText('Bazarr');
  await expect(page.locator('.service-card.unknown')).toHaveCount(0);
  await expect(page.locator('.service-card').first().locator('.service-quick-metrics')).toContainText('0');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await page.getByRole('button', { name: 'Add Sonarr' }).click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Sonarr');
  await page.locator('#detectApps').click();

  const reviewedRequest = await detectRequest;
  const reviewedBody = new URLSearchParams(reviewedRequest.postData() || '');
  expect(JSON.parse(reviewedBody.get('enabledServices'))).toEqual(['prowlarr', 'sonarr']);
  expect(reviewedBody.get('vpnProvider')).toBe('direct');
  await expect(page.locator('#selectedServiceSummary')).toContainText('Sonarr');
  await expect(page.locator('#setupApps')).toContainText('Connection verified');
  await expect(page.locator('#confirmSetup')).toBeEnabled();
  const navigation = page.waitForNavigation({ waitUntil: 'domcontentloaded' });
  await page.locator('#confirmSetup').click();

  const appliedRequest = await confirmRequest;
  const appliedBody = new URLSearchParams(appliedRequest.postData() || '');
  expect(JSON.parse(appliedBody.get('enabledServices'))).toEqual(['prowlarr', 'sonarr']);
  expect(appliedBody.get('vpnProvider')).toBe('direct');
  await navigation;
  await expect(page.locator('.service-card.healthy')).toContainText('Sonarr');
  await expectNoDocumentOverflow(page);
});

test('blocks apply and explains rejected service credentials', async ({ page }) => {
  const fresh = freshSetupFixture();
  const rejected = {
    ...fresh,
    phase: 'action_required',
    requiredCount: 2,
    selectedCount: 2,
    detectedCount: 2,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'sonarr'],
    modules: fresh.modules.map(module => ({
      ...module,
      enabled: module.id === 'prowlarr' || module.id === 'sonarr',
    })),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: '#' },
      { id: 'sonarr', name: 'Sonarr', reachable: true, credentials: false, action: 'invalid_credentials', detail: 'Stored API credentials were rejected', link: '#' },
    ],
  };
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: rejected }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Sonarr');
  await expect(page.locator('#setupApps')).toContainText('Credentials rejected');
  await expect(page.locator('#setupApps')).toContainText('Stored API credentials were rejected');
  await expect(page.locator('[data-connection-card="sonarr"] .credential-automatic')).toHaveCount(0);
  await expect(page.locator('[data-connection-card="sonarr"] fieldset')).toBeVisible();
  await expect(page.locator('[data-connection-card="sonarr"] [data-connection-source="sonarr"][value="ui"]')).toBeChecked();
  await expect(page.locator('[data-connection-card="sonarr"] [data-connection-key]')).toBeEnabled();
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expect(page.locator('#setupActionHelp')).toContainText('Update the connection above, then check again.');
  await expectNoDocumentOverflow(page);
});

test('explains Docker inventory and stopped-app blockers during review', async ({ page }) => {
  const fresh = freshSetupFixture();
  const reviewed = {
    ...fresh,
    phase: 'action_required',
    selectedCount: 2,
    detectedCount: 0,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'sonarr'],
    modules: fresh.modules.map(module => ({
      ...module,
      enabled: module.required || module.id === 'sonarr',
    })),
    apps: [
      {
        id: 'prowlarr', name: 'Prowlarr', reachable: false, credentials: false,
        action: 'docker_unavailable', detail: 'Docker inventory could not be read.', link: '',
      },
      {
        id: 'sonarr', name: 'Sonarr', reachable: false, credentials: false,
        action: 'start_service', detail: 'The installed container is stopped.', link: 'http://umbrel.local:30985',
      },
    ],
  };
  let setupResponse = fresh;
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setupResponse }));
  await page.route('**/api/setup/detect', route => {
    setupResponse = reviewed;
    return route.fulfill({ json: reviewed });
  });

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await page.getByRole('button', { name: 'Add Sonarr' }).click();
  await page.locator('#detectApps').click();

  await expect(page.locator('#setupApps')).toContainText('Docker unavailable');
  await expect(page.locator('#setupApps')).toContainText('Docker inventory could not be read.');
  await expect(page.locator('#setupApps')).toContainText('Start service');
  await expect(page.locator('#setupApps')).toContainText('The installed container is stopped.');
  await expect(page.locator('#setupApps .open-link')).toHaveCount(1);
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expectNoDocumentOverflow(page);
});

test('accepts a direct service connection without leaving umbrelarr', async ({ page }) => {
  const fresh = sabnzbdSetupFixture();
  const needsConnection = {
    ...fresh,
    phase: 'action_required',
    selectedCount: 2,
    detectedCount: 2,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'sabnzbd'],
    modules: fresh.modules.map(module => module.id === 'sabnzbd' ? {
      ...module,
      enabled: true,
      credentialConfigured: true,
      credentialSource: 'ui',
    } : {
      ...module,
      enabled: module.required,
    }),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: '#' },
      {
        id: 'sabnzbd',
        name: 'SABnzbd',
        reachable: true,
        credentials: false,
        action: 'direct_connection_required',
        detail: 'This address opens a platform login instead of the service API. Enter a direct service address and check again.',
        link: 'http://umbrel.local:8090',
      },
    ],
  };
  const ready = {
    ...needsConnection,
    phase: 'ready',
    canConfirm: true,
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: '#' },
      { id: 'sabnzbd', name: 'SABnzbd', reachable: true, credentials: true, action: 'none', detail: 'Connection verified', link: 'http://sabnzbd:8080' },
    ],
    modules: needsConnection.modules.map(module => module.id === 'sabnzbd'
      ? { ...module, connectionUrl: 'http://sabnzbd:8080', connectionConfigured: true, credentialConfigured: true }
      : module),
  };
  let setupResponse = fresh;
  const detectBodies = [];
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setupResponse }));
  await page.route('**/api/setup/detect', route => {
    detectBodies.push(new URLSearchParams(route.request().postData() || ''));
    setupResponse = detectBodies.length === 1 ? needsConnection : ready;
    return route.fulfill({ json: setupResponse });
  });

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await page.getByRole('button', { name: 'Add SABnzbd' }).click();
  await expect(page.getByRole('group', { name: 'API key source' })).toBeVisible();
  await expect(page.getByLabel('Enter in UI')).toBeChecked();
  await expect(page.locator('[data-credential-panel="environment"]')).toContainText('UMBREL_ARR_SABNZBD_API_KEY');
  const serviceUrl = page.locator('[data-connection-url="sabnzbd"]');
  const apiKey = page.locator('[data-connection-key="sabnzbd"]');
  await page.getByLabel('Environment variable').check();
  await expect(page.locator('[data-credential-panel="environment"]')).toBeVisible();
  await expect(apiKey).toBeDisabled();
  await page.getByLabel('Enter in UI').check();
  await expect(apiKey).toBeEnabled();
  await serviceUrl.fill('http://sabnzbd:8080');
  await apiKey.fill('secret-api-key');
  await page.locator('#detectApps').click();

  await expect(page.locator('#directConnections')).toBeVisible();
  await expect(page.locator('#setupApps')).toContainText('Direct address required');
  await expect(page.locator('#continueInUmbrel')).toHaveCount(0);
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expect(page.getByLabel('Enter in UI')).toBeChecked();
  await expect(apiKey).toHaveValue('');
  await page.locator('#detectApps').click();

  const firstConnections = JSON.parse(detectBodies[0].get('connections'));
  expect(firstConnections.sabnzbd).toEqual({ url: 'http://sabnzbd:8080', apiKey: 'secret-api-key', credentialSource: 'ui' });
  const retriedConnections = JSON.parse(detectBodies[1].get('connections'));
  expect(retriedConnections.sabnzbd).toEqual({ url: 'http://sabnzbd:8080', credentialSource: 'ui' });
  await expect(page).toHaveURL(/\/services$/);
  await expect(page.locator('#confirmSetup')).toBeVisible();
  await expect(page.locator('[data-connection-key="sabnzbd"]')).toHaveValue('');
  await expect(page.locator('[data-connection-key="sabnzbd"]')).toHaveAttribute('type', 'password');
  await expect(page.locator('#serviceManager')).not.toContainText('Umbrel');
  await expectNoDocumentOverflow(page);
});

test('uses a restart-safe environment API key without returning the secret to the browser', async ({ page }) => {
  const fresh = sabnzbdSetupFixture();
  const configured = {
    ...fresh,
    modules: fresh.modules.map(module => module.id === 'sabnzbd' ? {
      ...module,
      credentialConfigured: true,
      credentialSource: 'environment',
      environmentCredentialConfigured: true,
    } : module),
  };
  let submittedConnections = null;
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: configured }));
  await page.route('**/api/setup/detect', route => {
    const body = new URLSearchParams(route.request().postData() || '');
    submittedConnections = JSON.parse(body.get('connections'));
    return route.fulfill({ json: configured });
  });

  await page.goto('/services?add=sabnzbd');

  await expect(page.getByLabel('Environment variable')).toBeChecked();
  await expect(page.locator('[data-credential-panel="environment"]')).toBeVisible();
  await expect(page.locator('[data-credential-panel="environment"]')).toContainText('UMBREL_ARR_SABNZBD_API_KEY');
  await expect(page.locator('[data-credential-panel="environment"]')).toContainText('remains available after restart');
  await expect(page.locator('[data-connection-key="sabnzbd"]')).toBeDisabled();
  await page.locator('#detectApps').click();

  expect(submittedConnections.sabnzbd).toEqual({
    url: 'http://sabnzbd:8080',
    credentialSource: 'environment',
  });
  await expect(page.locator('#serviceManager')).not.toContainText('private-key');
  await expectNoDocumentOverflow(page);
});

test('adopts and validates a generated service API key without exposing a fallback field', async ({ page }) => {
  const fresh = sabnzbdSetupFixture();
  const automatic = {
    ...fresh,
    modules: fresh.modules.map(module => module.id === 'sabnzbd' ? {
      ...module,
      credentialConfigured: true,
      credentialSource: 'managed_config',
    } : module),
  };
  const ready = {
    ...automatic,
    phase: 'ready',
    canConfirm: true,
    selectedCount: 2,
    detectedCount: 2,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'sabnzbd'],
    modules: automatic.modules.map(module => ({
      ...module,
      enabled: module.required || module.id === 'sabnzbd',
    })),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Environment API key verified', link: '#' },
      { id: 'sabnzbd', name: 'SABnzbd', reachable: true, credentials: true, action: 'none', detail: 'API key connected automatically from the installed app', link: 'http://sabnzbd:8080' },
    ],
  };
  let submittedConnections = null;
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: automatic }));
  await page.route('**/api/setup/detect', route => {
    const body = new URLSearchParams(route.request().postData() || '');
    submittedConnections = JSON.parse(body.get('connections'));
    return route.fulfill({ json: ready });
  });

  await page.goto('/services?add=sabnzbd');

  await expect(page.locator('[data-connection-card="sabnzbd"] .credential-automatic')).toContainText('Connected automatically');
  await expect(page.locator('[data-connection-card="sabnzbd"] .credential-automatic')).toContainText('without exposing it');
  await expect(page.locator('[data-connection-card="sabnzbd"] [data-connection-key]')).toHaveCount(0);
  await expect(page.locator('[data-connection-card="sabnzbd"] fieldset')).toHaveCount(0);
  await page.locator('#detectApps').click();

  expect(submittedConnections.sabnzbd).toEqual({ url: 'http://sabnzbd:8080' });
  await expect(page.locator('#setupApps')).toContainText('API key connected automatically');
  await expect(page.locator('#confirmSetup')).toBeVisible();
  await expect(page.locator('#serviceManager')).not.toContainText('sabnzbd-generated-key');
  await expectNoDocumentOverflow(page);
});

test('opens a requested service in the direct Connect step', async ({ page }) => {
  const setup = sabnzbdSetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));

  await page.goto('/services?add=sabnzbd');

  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('#serviceChooseStep')).toBeHidden();
  await expect(page.locator('#serviceConnectStep')).toBeVisible();
  await expect(page.locator('#selectedServiceSummary')).toContainText('SABnzbd');
  await expect(page.locator('#selectedServiceTitle')).toBeFocused();
  await expect(page.locator('#detectApps')).toBeVisible();
  await expect(page.locator('#detectApps')).toHaveText('Check SABnzbd');
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expect(page).toHaveURL(/\/services$/);
  expect(new URL(page.url()).search).toBe('');
  await expectNoDocumentOverflow(page);
});

test('connects FlareSolverr by address without API-key controls', async ({ page }) => {
  const setup = freshSetupFixture();
  const reviewed = {
    ...setup,
    phase: 'action_required',
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'flaresolverr'],
    modules: setup.modules.map(module => ({
      ...module,
      enabled: module.required || module.id === 'flaresolverr',
    })),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, action: 'none', detail: 'Environment API key verified', link: 'http://prowlarr:9696' },
      { id: 'flaresolverr', name: 'FlareSolverr', reachable: false, credentials: true, action: 'install_or_start', detail: 'App was not reachable', link: 'http://flaresolverr:8191' },
    ],
  };
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: reviewed }));

  await page.goto('/services?add=flaresolverr');

  const connection = page.locator('[data-connection-card="flaresolverr"]');
  await expect(page.locator('#selectedServiceSummary')).toContainText('FlareSolverr');
  await expect(connection.locator('[data-connection-url="flaresolverr"]')).toBeVisible();
  await expect(connection.locator('[data-connection-key]')).toHaveCount(0);
  await expect(connection.locator('fieldset')).toHaveCount(0);
  await expect(connection).not.toContainText('API key');
  await expect(page.locator('#directConnectionsHelp')).toHaveText('Enter a service address this process can reach.');
  await expect(page.locator('#directConnectionNote')).toBeHidden();
  await expect(page.locator('#detectApps')).toHaveText('Check FlareSolverr');
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('connections')).flaresolverr).toEqual({
    url: 'http://flaresolverr:8191',
  });
  await expect(page.locator('#setupError')).toBeEmpty();
  const result = page.locator('#setupApps .attention-item').filter({ hasText: 'FlareSolverr' });
  await expect(result).toContainText('Not found');
  await expect(result).not.toContainText('Ready to add');
  await expectNoDocumentOverflow(page);
});

test('keeps required core services out of the single-service add catalog', async ({ page }) => {
  const fresh = freshSetupFixture();
  const proxied = {
    ...fresh,
    phase: 'action_required',
    selectedCount: 1,
    detectedCount: 1,
    detectionComplete: true,
    apps: [{
      id: 'prowlarr',
      name: 'Prowlarr',
      reachable: true,
      credentials: false,
      action: 'direct_connection_required',
      detail: 'Enter a direct service address and check again.',
      link: 'http://umbrel.local:30982',
    }],
  };
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: proxied }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('[data-module-card][data-module-id="prowlarr"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Add Prowlarr' })).toHaveCount(0);
  await expect(page.locator('#moduleCatalog')).not.toContainText('Not found');
  await expectNoDocumentOverflow(page);
});

test('treats Privado as an explicit service addition', async ({ page }) => {
  const fresh = freshSetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: fresh }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: fresh }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.locator('[data-service-type="network"]')).toBeVisible();
  await page.getByRole('button', { name: 'Add Privado VPN' }).click();
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'privado-vpn']);
  expect(body.get('vpnProvider')).toBe('privado');
  await expectNoDocumentOverflow(page);
});

test('keeps pending service choices after a dependency review error', async ({ page }) => {
  const fresh = freshSetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: fresh }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({
    status: 400,
    json: { error: 'Bazarr requires Sonarr and Radarr' },
  }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await page.getByRole('button', { name: 'Add Bazarr' }).click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Bazarr');
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'bazarr']);
  await expect(page.locator('#setupError')).toHaveText('Bazarr requires Sonarr and Radarr');
  await expect(page.locator('#selectedServiceSummary')).toContainText('Bazarr');
  await expect(page.getByRole('button', { name: 'Add Bazarr' })).toHaveCount(0);
  await expect(page.locator('#serviceGrid .service-card')).toHaveCount(2);
  await expect(page.locator('#serviceGrid')).not.toContainText('Bazarr');
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expectNoDocumentOverflow(page);
});

test('adds exactly one service without exposing removal or changing active cards early', async ({ page }) => {
  const reviewed = {
    ...confirmedSetup,
    phase: 'ready',
    canConfirm: true,
    detectionComplete: true,
    configurationChanged: true,
    requiredCount: 5,
    detectedCount: 5,
    enabledServices: ['umbrelarr', 'prowlarr', 'qbittorrent', 'sonarr', 'privado-vpn', 'jellyfin'],
    modules: confirmedSetup.modules.map(module => ({
      ...module,
      enabled: true,
    })),
    apps: [
      { id: 'prowlarr', name: 'Prowlarr', reachable: true, credentials: true, detail: 'Ready', link: '#' },
      { id: 'qbittorrent', name: 'qBittorrent', reachable: true, credentials: true, detail: 'Ready', link: '#' },
      { id: 'sonarr', name: 'Sonarr', reachable: true, credentials: true, detail: 'Ready', link: '#' },
      { id: 'jellyfin', name: 'Jellyfin', reachable: true, credentials: true, detail: 'Ready', link: '#' },
      { id: 'privado-vpn', name: 'Privado VPN', reachable: true, credentials: true, detail: 'Ready', link: '#' },
    ],
  };
  const applied = { ...reviewed, phase: 'confirmed', canConfirm: false, configurationChanged: false };
  let setupResponse = confirmedSetup;
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setupResponse }));
  const detectRequest = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => {
    setupResponse = reviewed;
    return route.fulfill({ json: reviewed });
  });
  const confirmRequest = page.waitForRequest('**/api/setup/confirm');
  await page.route('**/api/setup/confirm', route => {
    setupResponse = applied;
    return route.fulfill({ json: applied });
  });

  await page.goto('/services');
  await page.locator('#manageServices').click();
  const dialog = page.getByRole('dialog', { name: 'Add service' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Add one service');
  await expect(dialog).not.toContainText('Remove');
  await expect(page.locator('[data-module-card]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Add Jellyfin' }).click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Jellyfin');
  await page.locator('#detectApps').click();

  const reviewedRequest = await detectRequest;
  const reviewedBody = new URLSearchParams(reviewedRequest.postData() || '');
  expect(JSON.parse(reviewedBody.get('enabledServices'))).toEqual([
    'prowlarr', 'qbittorrent', 'sonarr', 'privado-vpn', 'jellyfin',
  ]);
  await expect(page.locator('#confirmSetup')).toBeEnabled();
  await expect(page.locator('#serviceGrid')).toContainText('Sonarr');
  await expect(page.locator('#setupApps')).toContainText('Ready to add');
  const appliedNavigation = page.waitForNavigation({ waitUntil: 'domcontentloaded' });
  await page.locator('#confirmSetup').click();

  const appliedRequest = await confirmRequest;
  const appliedBody = new URLSearchParams(appliedRequest.postData() || '');
  expect(JSON.parse(appliedBody.get('enabledServices'))).toEqual([
    'prowlarr', 'qbittorrent', 'sonarr', 'privado-vpn', 'jellyfin',
  ]);
  await appliedNavigation;
  await expect(page).toHaveURL(/\/services$/);
  await expectNoDocumentOverflow(page);
});

test('removes one optional service with confirmation and preserves the installed app', async ({ page }) => {
  let setupResponse = confirmedSetup;
  let statusResponse = statusFixture();
  await page.route('**/api/setup', route => route.fulfill({ json: setupResponse }));
  await page.route('**/api/status', route => route.fulfill({ json: statusResponse }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const removeRequest = page.waitForRequest('**/api/setup/remove');
  await page.route('**/api/setup/remove', route => {
    setupResponse = {
      ...confirmedSetup,
      enabledServices: confirmedSetup.enabledServices.filter(id => id !== 'sonarr'),
      activeEnabledServices: confirmedSetup.activeEnabledServices.filter(id => id !== 'sonarr'),
      modules: confirmedSetup.modules.map(module => (
        module.id === 'sonarr' ? { ...module, enabled: false, active: false } : module
      )),
    };
    statusResponse = {
      ...statusResponse,
      counts: { unknown: 0, waiting: 0, action_required: 0, configuring: 0, healthy: 0, failed: 0 },
      services: [],
    };
    return route.fulfill({ json: setupResponse });
  });

  await page.goto('/services');
  const remove = page.getByRole('button', { name: 'Remove Sonarr from managed services' });
  await expect(remove).toBeVisible();
  await remove.click();

  const dialog = page.getByRole('dialog', { name: 'Stop managing Sonarr?' });
  await expect(dialog).toBeVisible();
  await expect(page.locator('#removeServiceTitle')).toBeFocused();
  await expect(dialog).toContainText('The app stays installed.');
  await expect(dialog).toContainText('configuration, data, and settings remain in place');
  await page.locator('#cancelRemoveService').click();
  await expect(dialog).toBeHidden();
  await expect(remove).toBeFocused();

  await remove.click();
  await page.getByRole('button', { name: 'Remove Sonarr', exact: true }).click();
  const request = await removeRequest;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('serviceId')).toBe('sonarr');

  await expect(dialog).toBeHidden();
  await expect(page.locator('#serviceActionStatus')).toContainText('Sonarr is no longer managed');
  await expect(page.locator('#serviceGrid .service-card')).toHaveCount(0);
  await expect(page.locator('#manageServices')).toBeFocused();
  await expectNoDocumentOverflow(page);
});

test('keeps the removal confirmation open when the managed selection cannot be saved', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/setup/remove', route => route.fulfill({
    status: 400,
    json: { error: 'Cannot remove Sonarr: Bazarr requires Sonarr and Radarr. Remove the dependent service first.' },
  }));

  await page.goto('/services');
  await page.getByRole('button', { name: 'Remove Sonarr from managed services' }).click();
  const dialog = page.getByRole('dialog', { name: 'Stop managing Sonarr?' });
  await page.getByRole('button', { name: 'Remove Sonarr', exact: true }).click();

  await expect(dialog).toBeVisible();
  await expect(page.locator('#removeServiceError')).toContainText('Remove the dependent service first');
  await expect(page.getByRole('button', { name: 'Remove Sonarr', exact: true })).toBeEnabled();
  await expect(page.locator('#serviceGrid .service-card')).toHaveCount(1);
  await expectNoDocumentOverflow(page);
});

test('does not offer removal for required control-plane services', async ({ page }) => {
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: confirmedSetup }));

  await page.goto('/services');

  await expect(page.locator('#serviceGrid')).toContainText('Prowlarr');
  await expect(page.locator('[data-remove-service]')).toHaveCount(0);
  await expectNoDocumentOverflow(page);
});

test('redirects the retired setup route into Services', async ({ page }) => {
  await mockDashboard(page);

  await page.goto('/setup');

  await expect(page).toHaveURL(/\/services$/);
  await expect(page.getByRole('link', { name: 'Setup' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Add service' })).toBeVisible();
});

test('redirects retired service detail routes into the single Services workflow', async ({ page }) => {
  await mockDashboard(page);

  await page.goto('/services/prowlarr');

  await expect(page).toHaveURL(/\/services$/);
  await expect(page.locator('#serviceGrid')).toBeVisible();
  await expect(page.locator('#serviceDetail')).toHaveCount(0);
  await expectNoDocumentOverflow(page);
});

test('returns focus after cancelling the add-service modal with Escape', async ({ page }) => {
  await mockDashboard(page);
  await page.route('**/api/setup/cancel', route => route.fulfill({ json: confirmedSetup }));
  const cancelRequest = page.waitForRequest('**/api/setup/cancel');

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('#serviceManagerTitle')).toBeFocused();
  await page.keyboard.press('Escape');
  await cancelRequest;

  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeHidden();
  await expect(page.locator('#manageServices')).toBeFocused();
  await expect(page.locator('body')).not.toHaveClass(/modal-open/);
  await expectNoDocumentOverflow(page);
});

test('presents libraries as a responsive card grid with dedicated detail pages', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/libraries');

  await expect(page.locator('.library-card')).toHaveCount(5);
  await expect(page.locator('#libraryGrid')).toContainText('TV');
  await expect(page.locator('#libraryGrid')).toContainText('Movies');
  await expect(page.locator('#libraryGrid')).toContainText('Music');
  await expect(page.locator('body')).not.toContainText('Configuration level');
  await expect(page.locator('.mode-tabs')).toHaveCount(0);
  await expectNoDocumentOverflow(page);

  await page.locator('.library-card[href="/libraries/tv"]').click();
  await expect(page).toHaveURL(/\/libraries\/tv$/);
  await expect(page.locator('#libraryDetailName')).toHaveText('TV HD');
  await expect(page.locator('[name="librarySource"]')).toHaveCount(3);
  await expect(page.locator('#libraryBrowser')).toBeVisible();
  await expect(page.locator('#libraryMountCheck .mount-chip')).toHaveCount(5);
  await expect(page.locator('body')).not.toContainText('API only');
  await expect(page.locator('#libraryLocationTitle').locator('xpath=..').locator('p')).toHaveCount(0);
  await expect(page.locator('#libraryConfigTitle')).toContainText('Managed configuration');
  await expectNoDocumentOverflow(page);
});

test('browses the system and saves a path shared by every media service', async ({ page }) => {
  let storage = storageFixture();
  await page.route('**/api/setup', route => route.fulfill({ json: confirmedSetup }));
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/storage', route => route.fulfill({ json: storage }));
  await page.route('**/api/storage/browse**', route => {
    const path = new URL(route.request().url()).searchParams.get('path') || '/';
    return route.fulfill({ json: filesystemFixture(path) });
  });
  const requestPromise = page.waitForRequest('**/api/storage/library');
  await page.route('**/api/storage/library', async route => {
    const library = storage.libraries.find(item => item.key === 'sonarr');
    library.source = 'existing';
    library.rootId = 20;
    library.root = '/media/sonarr';
    storage.roots.sonarr = library.root;
    storage.rootIds.sonarr = library.rootId;
    await route.fulfill({ json: storage });
  });

  await page.goto('/libraries/tv');
  await page.locator('[data-library-browse-path="/"]').click();
  await page.locator('[data-library-browse-path="/media"]').click();
  await page.locator('[data-library-browse-path="/media/sonarr"]').click();
  await expect(page.locator('[name="librarySource"][value="custom"]')).toBeChecked();
  await expect(page.locator('#libraryBrowserPath')).toHaveText('/media/sonarr');
  await expect(page.locator('#libraryMountCheck .mount-chip.match')).toHaveCount(5);
  await expect(page.getByRole('button', { name: 'Save library' })).toBeEnabled();
  await page.getByRole('button', { name: 'Save library' }).click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('libraryKey')).toBe('sonarr');
  expect(body.get('source')).toBe('custom');
  expect(body.get('path')).toBe('/media/sonarr');
  expect(body.get('rootId')).toBeNull();
  await expect(page.locator('#libraryDetailRoot')).toHaveText('/media/sonarr');
  await expect(page.locator('#libraryResult')).toContainText('saved through the installed app APIs');
  await expectNoDocumentOverflow(page);
});

test('blocks a library path that does not match every media-service mount', async ({ page }) => {
  await mockDashboard(page, 'healthy', 0, true);

  await page.goto('/libraries/tv');

  await expect(page.locator('#libraryMountCheck .mount-chip.missing')).toContainText('Radarr');
  await expect(page.locator('#libraryMountCheck')).toContainText('same location in every media service');
  await expect(page.getByRole('button', { name: 'Save library' })).toBeDisabled();
  await expectNoDocumentOverflow(page);
});

test('submits selected services and the one-time qBittorrent credential', async ({ page }) => {
  const fresh = freshSetupFixture();
  const setup = {
    ...fresh,
    phase: 'ready',
    confirmed: false,
    canConfirm: true,
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'qbittorrent'],
    modules: fresh.modules.map(module => ({
      ...module,
      enabled: module.required || module.id === 'qbittorrent',
    })),
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

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('qBittorrent');
  await page.locator('#qbittorrentUsername').fill('admin');
  await page.locator('#qbittorrentTemporaryPassword').fill('temporary-fixture-secret');
  await page.locator('#confirmSetup').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('storageMode')).toBeNull();
  expect(body.get('rootIds')).toBeNull();
  expect(body.get('qbittorrentUsername')).toBe('admin');
  expect(body.get('qbittorrentTemporaryPassword')).toBe('temporary-fixture-secret');
});

test('adds a categorized service and detects only the selected modules from Services', async ({ page }) => {
  const setup = modularSetup();
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: setup }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('dialog', { name: 'Add service' })).toBeVisible();
  await expect(page.locator('[data-service-type="network"]')).toBeVisible();
  await expect(page.locator('[data-service-type="downloads"]')).toBeVisible();
  await expect(page.locator('[data-service-type="media"]')).toBeVisible();
  await page.getByRole('button', { name: 'Add Sonarr' }).click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('Sonarr');
  await expect(page.getByRole('button', { name: 'Add qBittorrent' })).not.toBeVisible();
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(body.get('vpnProvider')).toBe('direct');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'sonarr']);
  await expectNoDocumentOverflow(page);
});

test('creates and connects a dedicated Jellyfin key with retry-safe administrator bootstrap', async ({ page }) => {
  const fresh = freshSetupFixture();
  const jellyfin = fresh.modules.find(module => module.id === 'jellyfin');
  const setup = {
    ...fresh,
    modules: [
      ...fresh.modules.filter(module => module.id !== 'jellyfin'),
      jellyfin,
      { id: 'plex', name: 'Plex', role: 'media_server', enabled: false, active: false, required: false, requires_api_key: true, credentialSetup: 'existing_token', connectionUrl: 'http://plex:32400', credentialConfigured: false, credentialSource: 'missing', environmentCredentialConfigured: false, apiKeyEnvironmentVariable: 'UMBREL_ARR_PLEX_API_KEY' },
    ],
  };
  const reviewed = {
    ...setup,
    phase: 'action_required',
    detectionComplete: true,
    configurationChanged: true,
    enabledServices: ['umbrelarr', 'prowlarr', 'jellyfin'],
    modules: setup.modules.map(module => ({ ...module, enabled: module.required || module.id === 'jellyfin' })),
    apps: [{
      id: 'jellyfin', name: 'Jellyfin', reachable: true, credentials: false,
      action: 'create_api_key', detail: 'Create and connect a dedicated Jellyfin API key with an administrator account',
      link: 'http://jellyfin:8096',
    }],
  };
  const ready = {
    ...reviewed,
    phase: 'ready',
    canConfirm: true,
    detectedCount: 2,
    modules: reviewed.modules.map(module => module.id === 'jellyfin' ? {
      ...module,
      credentialConfigured: true,
      credentialSource: 'service_api',
    } : module),
    apps: [{
      id: 'jellyfin', name: 'Jellyfin', reachable: true, credentials: true,
      action: 'none', detail: 'Dedicated umbrelarr API key created and verified',
      link: 'http://jellyfin:8096',
    }],
  };
  const bootstrapBodies = [];
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: reviewed }));
  await page.route('**/api/setup/credentials/bootstrap', async route => {
    bootstrapBodies.push(new URLSearchParams(route.request().postData() || ''));
    if (bootstrapBodies.length === 1) {
      return route.fulfill({ status: 400, json: { error: 'Jellyfin rejected the administrator username or password' } });
    }
    await new Promise(resolve => setTimeout(resolve, 150));
    return route.fulfill({ json: ready });
  });

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await page.getByRole('button', { name: 'Add Jellyfin' }).click();
  await page.locator('#detectApps').click();
  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'jellyfin']);
  await expect(page.locator('#setupApps')).toContainText('Create API key');
  await expect(page.locator('#setupApps')).not.toContainText('Claim server');
  await expect(page.locator('#selectedServiceSummary')).toContainText('Jellyfin');
  await expect(page.locator('#jellyfinCredentialBootstrap')).toBeVisible();
  await expect(page.locator('#jellyfinCredentialBootstrap')).toContainText('never saved');
  await expect(page.locator('[data-connection-card="jellyfin"] fieldset')).toBeVisible();
  await expect(page.locator('#confirmSetup')).toBeHidden();
  await expect(page.locator('#setupActionHelp')).toContainText('Create the dedicated key below');

  await page.locator('#jellyfinAdminUsername').fill('admin');
  await page.locator('#jellyfinAdminPassword').fill('temporary-admin-secret');
  await page.locator('#bootstrapJellyfinCredential').click();

  await expect(page.locator('#setupError')).toContainText('Jellyfin rejected the administrator username or password');
  await expect(page.locator('#jellyfinAdminUsername')).toHaveValue('');
  await expect(page.locator('#jellyfinAdminPassword')).toHaveValue('');
  await expect(page.locator('#bootstrapJellyfinCredential')).toHaveText('Create and connect');
  await expect(page.locator('#bootstrapJellyfinCredential')).toBeEnabled();
  await expect(page.locator('#serviceManager')).not.toContainText('temporary-admin-secret');

  await page.locator('#jellyfinAdminUsername').fill('admin');
  await page.locator('#jellyfinAdminPassword').fill('temporary-admin-secret');
  await page.locator('#bootstrapJellyfinCredential').click();

  await expect(page.locator('#serviceManager')).toHaveAttribute('aria-busy', 'true');
  await expect(page.locator('#bootstrapJellyfinCredential')).toBeDisabled();
  await expect(page.locator('#bootstrapJellyfinCredential')).toHaveText('Creating API key…');
  await expect.poll(() => bootstrapBodies.length).toBe(2);
  expect(bootstrapBodies).toHaveLength(2);
  expect(bootstrapBodies[1].get('serviceId')).toBe('jellyfin');
  expect(bootstrapBodies[1].get('username')).toBe('admin');
  expect(bootstrapBodies[1].get('password')).toBe('temporary-admin-secret');
  expect(bootstrapBodies[1].has('url')).toBe(false);
  await expect(page.locator('#jellyfinAdminUsername')).toHaveValue('');
  await expect(page.locator('#jellyfinAdminPassword')).toHaveValue('');
  await expect(page.locator('#jellyfinCredentialBootstrap')).toBeHidden();
  await expect(page.locator('[data-connection-card="jellyfin"] .credential-automatic')).toContainText('Connected automatically');
  await expect(page.locator('[data-connection-card="jellyfin"] .credential-automatic')).toContainText('created and verified through the service API');
  await expect(page.locator('#confirmSetup')).toBeVisible();
  await expect(page.locator('#serviceManager')).not.toContainText('temporary-admin-secret');
  await expectNoDocumentOverflow(page);
});

test('starts Services with the required core and exposes typed Add actions', async ({ page }) => {
  const setup = modularSetup();
  await page.route('**/api/status', route => route.fulfill({ json: statusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));
  const requestPromise = page.waitForRequest('**/api/setup/detect');
  await page.route('**/api/setup/detect', route => route.fulfill({ json: setup }));

  await page.goto('/services');
  await page.locator('#manageServices').click();
  await expect(page.getByRole('button', { name: 'Add Prowlarr' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Add qBittorrent' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add Sonarr' })).toBeVisible();
  await expect(page.locator('[data-module]')).toHaveCount(0);
  await expect(page.locator('#qbittorrentCredentials')).toBeHidden();
  await expect(page.locator('#vpnProvider')).toHaveCount(0);
  await expect(page.locator('#setupStorageOptions')).toHaveCount(0);
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await expect(page.locator('#serviceCatalogTitle')).toHaveText('Connect a service');
  await expect(page.locator('#serviceTypeSummary')).toContainText('3 supported services across 3 categories; connect one by API address.');
  await page.getByRole('button', { name: 'Add qBittorrent' }).click();
  await expect(page.locator('#selectedServiceSummary')).toContainText('qBittorrent');
  await page.locator('#detectApps').click();

  const request = await requestPromise;
  const body = new URLSearchParams(request.postData() || '');
  expect(JSON.parse(body.get('enabledServices'))).toEqual(['prowlarr', 'qbittorrent']);
  expect(body.get('vpnProvider')).toBe('direct');
  await expectNoDocumentOverflow(page);
});

test('offers every supported optional service from a clean dashboard', async ({ page }) => {
  const setup = completeCatalogSetupFixture();
  await page.route('**/api/status', route => route.fulfill({ json: freshStatusFixture() }));
  await page.route('**/api/setup', route => route.fulfill({ json: setup }));
  await page.route('**/api/storage', route => route.fulfill({ json: storageFixture() }));

  await page.goto('/services');
  await page.locator('#manageServices').click();

  const optionalServices = [
    'Privado VPN', 'FlareSolverr', 'qBittorrent', 'SABnzbd',
    'Sonarr', 'Sonarr 4K', 'Radarr', 'Radarr 4K', 'Lidarr',
    'Bazarr', 'Overseerr', 'Profilarr', 'Jellyfin', 'Plex',
  ];
  await expect(page.locator('[data-module-card]')).toHaveCount(optionalServices.length);
  await expect(page.locator('.module-type-group')).toHaveCount(6);
  await expect(page.locator('#serviceTypeSummary')).toHaveText(
    '14 supported services across 6 categories; connect one by API address.',
  );
  for (const service of optionalServices) {
    await expect(page.getByRole('button', { name: `Add ${service}`, exact: true })).toBeVisible();
  }
  await expect(page.getByRole('button', { name: 'Add Prowlarr' })).toHaveCount(0);
  await expectNoDocumentOverflow(page);
});

test('uses one primary navigation group without redundant scope chrome', async ({ page }) => {
  await mockDashboard(page);
  await page.goto('/activity');

  const navigation = page.locator('aside[aria-label="Primary navigation"] nav');
  await expect(navigation.locator('.nav-label')).toHaveCount(0);
  await expect(navigation.getByRole('link')).toHaveCount(4);
  await expect(navigation.getByRole('link', { name: 'Overview' })).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Services' })).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Libraries' })).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Activity' })).toBeVisible();
  await expect(navigation.getByRole('link', { name: 'Dependencies' })).toHaveCount(0);
  await expect(page.locator('.sidebar-foot')).toHaveCount(0);
  await expect(page.getByText('Managed scope')).toHaveCount(0);
  await expect(page.getByText('Local Umbrel stack')).toHaveCount(0);
  await expect(page.locator('.scope-bar')).toHaveCount(0);
  await expectNoDocumentOverflow(page);

  await page.goto('/dependencies');
  await expect(page).toHaveURL(/\/services$/);
});
