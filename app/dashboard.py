TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>umbrelarr</title>
  <link rel="icon" href="/icon.png" type="image/png">
  <style>
    :root {
      color-scheme: light;
      --sidebar: #20242a;
      --sidebar-hover: #292e35;
      --sidebar-active: #30363e;
      --canvas: #f5f6f8;
      --surface: #ffffff;
      --surface-muted: #f8f9fa;
      --line: #e1e4e8;
      --line-strong: #ccd1d7;
      --text: #252a31;
      --muted: #69727d;
      --primary: #2e8b57;
      --primary-dark: #237247;
      --primary-soft: #edf7f1;
      --blue: #3e7f9f;
      --blue-dark: #326984;
      --green: #2d965c;
      --green-soft: #eaf6ef;
      --amber: #c88724;
      --amber-soft: #fff6e6;
      --red: #c95256;
      --red-soft: #fcedee;
      --slate: #87909a;
      --shadow: 0 1px 2px rgba(22, 27, 32, .05), 0 4px 12px rgba(22, 27, 32, .035);
      --shadow-hover: var(--shadow);
      --sidebar-width: 232px;
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-width: 320px;
      background: var(--canvas);
      color: var(--text);
      font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      letter-spacing: -.005em;
    }
    button, input, select { font: inherit; }
    button {
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      background: var(--surface);
      color: var(--text);
      padding: 8px 14px;
      cursor: pointer;
      font-weight: 650;
      box-shadow: 0 1px 2px rgba(22, 27, 32, .04);
      transition: background .16s ease, border-color .16s ease, box-shadow .16s ease;
    }
    button:hover { background: #f6f7f8; border-color: #adb4bc; box-shadow: 0 2px 5px rgba(22, 27, 32, .08); }
    button.primary { border-color: var(--primary-dark); background: var(--primary); color: #fff; }
    button.primary:hover { background: var(--primary-dark); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    button:disabled:hover { box-shadow: none; }
    button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible { outline: 3px solid rgba(32, 148, 91, .28); outline-offset: 2px; }
    a { color: var(--blue-dark); text-decoration: none; }
    a:hover { text-decoration: underline; }

    .app-shell { min-height: 100vh; }
    .sidebar {
      position: fixed;
      inset: 0 auto 0 0;
      z-index: 10;
      width: var(--sidebar-width);
      background: var(--sidebar);
      color: #d6d9de;
      border-right: 1px solid #171a1f;
      display: flex;
      flex-direction: column;
    }
    .brand {
      height: 72px;
      padding: 0 17px;
      display: flex;
      align-items: center;
      gap: 11px;
      border-bottom: 1px solid rgba(255,255,255,.07);
    }
    .brand-mark {
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      flex: 0 0 auto;
    }
    .brand-mark img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
      filter: drop-shadow(0 1px 1px rgba(0,0,0,.28));
    }
    .brand-name { font-size: 18px; font-weight: 700; color: #fff; letter-spacing: -.35px; }
    .brand-name span { color: #7fd3a2; }
    .nav { padding: 14px 11px; }
    .nav-label { padding: 13px 10px 7px; color: #7f8791; font-size: 10px; font-weight: 750; letter-spacing: 1px; text-transform: uppercase; }
    .nav a {
      min-height: 44px;
      margin: 3px 0;
      padding: 0 12px;
      display: flex;
      align-items: center;
      gap: 12px;
      color: #b3b9c1;
      border: 1px solid transparent;
      border-radius: 10px;
      font-weight: 550;
      transition: background .16s ease, border-color .16s ease, color .16s ease;
    }
    .nav a:hover { background: var(--sidebar-hover); color: #fff; text-decoration: none; }
    .nav a.active {
      background: var(--sidebar-active);
      color: #fff;
      border-color: #464d56;
      border-radius: 11px;
      box-shadow: 0 1px 2px rgba(0, 0, 0, .18);
    }
    .nav-icon { width: 18px; text-align: center; color: #89919b; font-size: 15px; font-weight: 800; }
    .nav a.active .nav-icon { color: #8ed6aa; }
    .nav-badge { margin-left: auto; min-width: 21px; padding: 2px 6px; border-radius: 999px; background: #404751; color: #e2e5e9; text-align: center; font-size: 11px; }
    .sidebar-foot { margin-top: auto; padding: 16px 18px; border-top: 1px solid rgba(255,255,255,.07); color: #838b95; font-size: 11px; }
    .sidebar-foot strong { color: #b9bfc6; font-weight: 650; }

    .content { min-height: 100vh; margin-left: var(--sidebar-width); }
    .topbar {
      height: 72px;
      position: sticky;
      top: 0;
      z-index: 8;
      padding: 0 28px;
      background: rgba(255,255,255,.96);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
    }
    .page-title { min-width: 0; }
    .page-title h1 { margin: 0; font-size: 21px; line-height: 1.2; font-weight: 700; letter-spacing: -.35px; }
    .page-title p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
    .top-actions { display: flex; align-items: center; gap: 9px; }
    .live-state { display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; white-space: nowrap; }
    .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--slate); }
    .live-dot.healthy { background: var(--green); }
    .live-dot.action_required { background: var(--amber); }
    .live-dot.failed { background: var(--red); }
    .live-dot.waiting, .live-dot.configuring { background: var(--blue); }

    .workspace { width: min(1280px, 100%); margin: 0 auto; padding: 26px 28px 48px; }
    .scope-bar { margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; gap: 15px; color: var(--muted); font-size: 12px; }
    .scope { display: inline-flex; align-items: center; gap: 8px; }
    .scope-tag { padding: 4px 9px; border: 1px solid var(--line-strong); border-radius: 999px; background: #f7f8f9; color: #515963; font-weight: 700; }
    .fresh.stale { color: var(--amber); font-weight: 600; }

    .summary {
      margin-bottom: 18px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--surface);
      box-shadow: var(--shadow);
      overflow: hidden;
      display: grid;
      grid-template-columns: minmax(300px, 1fr) repeat(4, 116px);
    }
    .summary-status { padding: 20px 22px; display: flex; align-items: center; gap: 14px; background: #fff; }
    .status-orb { width: 12px; height: 12px; flex: 0 0 auto; border-radius: 50%; background: var(--slate); box-shadow: 0 0 0 5px #edf1ee; }
    .status-orb.healthy { background: var(--green); box-shadow: 0 0 0 5px var(--green-soft); }
    .status-orb.action_required { background: var(--amber); box-shadow: 0 0 0 5px var(--amber-soft); }
    .status-orb.failed { background: var(--red); box-shadow: 0 0 0 5px var(--red-soft); }
    .status-orb.waiting, .status-orb.configuring { background: var(--blue); box-shadow: 0 0 0 5px #e6f3f5; }
    .summary-status h2 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -.2px; }
    .summary-status p { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
    .metric { padding: 16px; border-left: 1px solid var(--line); display: flex; flex-direction: column; justify-content: center; background: #fff; }
    .metric strong { font-size: 23px; line-height: 1.1; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.4px; }
    .metric span { margin-top: 3px; color: var(--muted); font-size: 11px; }

    .notice { margin-bottom: 18px; border: 1px solid #ead5a8; border-left: 4px solid var(--amber); border-radius: 10px; background: #fffaf0; box-shadow: var(--shadow); overflow: hidden; }
    .notice-head { padding: 14px 17px; border-bottom: 1px solid #eddfc2; display: flex; align-items: center; gap: 11px; }
    .notice-symbol { color: var(--amber); font-size: 17px; }
    .notice h2 { margin: 0; font-size: 14px; font-weight: 700; }
    .notice p { margin: 2px 0 0; color: #786747; font-size: 12px; }
    .vpn-form { padding: 16px 17px; display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto; gap: 12px; align-items: end; }
    .notice > .error { margin: -5px 17px 14px; }

    .panel { margin-bottom: 18px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); box-shadow: var(--shadow); overflow: hidden; }
    .panel:hover { box-shadow: var(--shadow); }
    .panel-head { min-height: 58px; padding: 13px 17px; border-bottom: 1px solid var(--line); background: #fff; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
    .panel-head h2 { margin: 0; font-size: 15px; font-weight: 700; letter-spacing: -.15px; }
    .panel-head p { margin: 2px 0 0; color: var(--muted); font-size: 11px; }
    .panel-body { padding: 18px; }
    label span { display: block; margin-bottom: 6px; color: #525b66; font-size: 11px; font-weight: 700; }
    input {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      padding: 8px 11px;
      background: #fff;
      color: var(--text);
      box-shadow: inset 0 1px 2px rgba(22, 27, 32, .035);
      transition: border-color .16s ease, box-shadow .16s ease;
    }
    input:hover { border-color: #aeb5bd; }
    input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(32, 148, 91, .1); }
    .segmented { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 9px; overflow: hidden; background: #f1f2f4; }
    .segmented input { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); opacity: 0; }
    .segmented label { min-height: 32px; padding: 6px 11px; border-radius: 8px; color: var(--muted); cursor: pointer; font-size: 12px; font-weight: 650; }
    .segmented input:checked + label { background: #fff; color: var(--text); box-shadow: 0 1px 3px rgba(22, 27, 32, .12); }
    .segmented input:focus-visible + label { outline: 3px solid rgba(32,148,91,.28); outline-offset: -2px; }
    .path-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; }
    .panel-actions { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .error { min-height: 18px; color: #a52e34; font-size: 12px; }
    .error:not(:empty) { padding: 8px 10px; border: 1px solid #efc5c7; border-radius: 8px; background: var(--red-soft); }
    .mode-tabs { margin-bottom: 18px; padding: 3px; display: inline-flex; border: 1px solid var(--line); border-radius: 9px; overflow: hidden; background: #eef0f2; }
    .mode-tabs a { min-width: 110px; padding: 8px 14px; border-radius: 7px; color: var(--muted); text-align: center; font-size: 12px; font-weight: 700; }
    .mode-tabs a:hover { background: rgba(255,255,255,.65); text-decoration: none; }
    .mode-tabs a.active { background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(22,27,32,.1); }
    .mode-note { margin: -8px 0 14px; color: var(--muted); font-size: 12px; }
    .root-summary { margin: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: var(--surface-muted); }
    .root-summary div { padding: 12px 14px; border-top: 1px solid var(--line); }
    .root-summary div:nth-child(-n+2) { border-top: 0; }
    .root-summary div:nth-child(even) { border-left: 1px solid var(--line); }
    .root-summary dt { color: var(--muted); font-size: 11px; font-weight: 600; }
    .root-summary dd { margin: 3px 0 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; }
    .library-list { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: #fff; }
    .library-row { min-height: 88px; padding: 14px; border-top: 1px solid var(--line); display: grid; grid-template-columns: 180px minmax(190px, .8fr) minmax(280px, 1.35fr); align-items: center; gap: 16px; }
    .library-row:first-child { border-top: 0; }
    .library-identity { min-width: 0; display: flex; align-items: center; gap: 11px; }
    .library-glyph { width: 38px; height: 38px; flex: 0 0 auto; border-radius: 9px; display: grid; place-items: center; background: #eef3f0; color: #326749; font-size: 10px; font-weight: 800; }
    .library-identity strong { display: block; font-size: 13px; }
    .library-identity small, .library-path small { display: block; margin-top: 2px; color: var(--muted); font-size: 10px; }
    .library-path { min-width: 0; }
    .library-path code { display: block; overflow: hidden; color: #3f4852; font: 11px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
    .library-apps { display: flex; flex-wrap: wrap; gap: 5px; }
    .library-app { min-height: 25px; padding: 3px 7px; border: 1px solid var(--line); border-radius: 999px; display: inline-flex; align-items: center; gap: 5px; background: #f7f8f9; color: #59636e; font-size: 10px; font-weight: 650; }
    .library-app .status-dot { width: 6px; height: 6px; }
    .library-app.healthy .status-dot { background: var(--green); }
    .library-app.failed .status-dot { background: var(--red); }
    .library-app.action_required .status-dot { background: var(--amber); }
    .library-app.waiting .status-dot, .library-app.configuring .status-dot { background: var(--blue); }
    .library-editor-list { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
    .library-editor { padding: 14px; border-top: 1px solid var(--line); display: grid; grid-template-columns: 180px minmax(260px, .9fr) minmax(280px, 1.1fr); align-items: center; gap: 16px; }
    .library-editor:first-child { border-top: 0; }
    .library-editor label > small { display: block; margin-top: 5px; color: var(--muted); font-size: 10px; }
    .library-feedback { margin-right: auto; }
    .success { min-height: 18px; color: #216e43; font-size: 12px; }
    .success:not(:empty) { display: block; padding: 8px 10px; border: 1px solid #b9dec7; border-radius: 8px; background: var(--green-soft); }
    .propagation-list { margin: 0; }
    .propagation-step { padding: 13px 17px; border-top: 1px solid var(--line); display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 16px; }
    .propagation-step:first-child { border-top: 0; }
    .propagation-step dt { font-size: 12px; font-weight: 700; }
    .propagation-step dd { margin: 0; color: var(--muted); font-size: 11px; }
    .attention-list { display: grid; }
    .attention-item { padding: 14px 17px; border-top: 1px solid var(--line); display: grid; grid-template-columns: minmax(160px, 1fr) minmax(240px, 2fr) auto; align-items: center; gap: 14px; transition: background .15s ease; }
    .attention-item:first-child { border-top: 0; }
    .attention-item:hover { background: #f8f9fa; }
    .attention-name { font-weight: 700; }
    .activity-list.full { max-height: none; }
    .setup-intro { padding: 18px; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 18px; }
    .setup-intro h2 { margin: 0; font-size: 16px; }
    .setup-intro p { max-width: 760px; margin: 5px 0 0; color: var(--muted); font-size: 12px; }
    .setup-app-list .attention-item { grid-template-columns: minmax(160px, 1fr) minmax(250px, 2fr) auto; }
    .module-grid { margin: 10px 0 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
    .module-option { min-height: 58px; padding: 10px 12px; display: flex; align-items: flex-start; gap: 9px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface-muted); }
    .module-option input { width: 18px; min-height: 18px; margin: 1px 0 0; padding: 0; flex: 0 0 18px; box-shadow: none; }
    .module-option strong, .module-option small { display: block; }
    .module-option small { margin-top: 2px; color: var(--muted); }
    .profile-select { max-width: 420px; display: grid; gap: 5px; margin-bottom: 14px; }
    .provider-select { display: grid; grid-template-columns: minmax(180px, 320px); gap: 5px; margin-bottom: 14px; }
    .setup-fieldset { margin: 0 0 14px; padding: 0; border: 0; }
    .setup-fieldset > legend { margin-bottom: 8px; font-size: 12px; font-weight: 700; }
    .storage-options { display: flex; flex-wrap: wrap; gap: 8px; }
    .storage-option { min-height: 38px; padding: 8px 11px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface-muted); cursor: pointer; }
    .storage-option input { width: 16px; min-height: 16px; margin: 0; padding: 0; flex: 0 0 16px; box-shadow: none; }
    .credential-fields { max-width: 620px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .credential-fields label { display: grid; gap: 5px; }
    .credential-fields label > small { color: var(--muted); font-size: 10px; }
    .setup-actions { padding: 14px 17px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .setup-feedback { margin-right: auto; }

    .operations { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 18px; align-items: start; }
    .table-wrap { overflow: hidden; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th { padding: 10px 14px; background: #f3f4f6; color: #68717c; font-size: 10px; font-weight: 750; letter-spacing: .55px; text-align: left; text-transform: uppercase; }
    td { padding: 11px 14px; border-top: 1px solid var(--line); vertical-align: middle; overflow-wrap: anywhere; }
    tbody tr { transition: background .14s ease; }
    tbody tr:hover { background: #f7f8f9; }
    tbody tr.failed { background: #fff9f9; }
    tbody tr.action_required { background: #fffdf8; }
    th:nth-child(1), td:nth-child(1) { width: 25%; }
    th:nth-child(2), td:nth-child(2) { width: 19%; }
    th:nth-child(4), td:nth-child(4) { width: 72px; text-align: right; }
    .service-name { display: flex; align-items: center; gap: 11px; font-weight: 700; }
    .service-icon { width: 30px; height: 30px; flex: 0 0 auto; border-radius: 7px; display: grid; place-items: center; background: #eef0f2; color: #5b6570; font-size: 9px; font-weight: 800; letter-spacing: -.2px; }
    tr.healthy .service-icon { background: var(--green-soft); color: #237346; }
    tr.action_required .service-icon { background: var(--amber-soft); color: #97600b; }
    tr.failed .service-icon { background: var(--red-soft); color: #a63a37; }
    .detail { color: var(--muted); font-size: 12px; }
    .status { display: inline-flex; align-items: center; gap: 7px; padding: 4px 8px; border-radius: 999px; background: #eef0f2; color: #59636e; font-size: 11px; font-weight: 700; white-space: nowrap; }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--slate); }
    .status.healthy .status-dot { background: var(--green); }
    .status.failed .status-dot { background: var(--red); }
    .status.waiting .status-dot, .status.configuring .status-dot { background: var(--blue); }
    .status.action_required .status-dot { background: var(--amber); }
    .status.healthy { background: var(--green-soft); color: #216e43; }
    .status.failed { background: var(--red-soft); color: #9f3539; }
    .status.waiting, .status.configuring { background: #e8f3f5; color: #256b79; }
    .status.action_required { background: var(--amber-soft); color: #8b5b0c; }
    .open-link { display: inline-flex; min-height: 28px; align-items: center; padding: 3px 8px; border-radius: 7px; font-size: 12px; font-weight: 700; }
    .open-link:hover { background: #edf3f6; text-decoration: none; }

    .activity-list { max-height: 586px; overflow: auto; }
    .event { padding: 12px 14px; border-bottom: 1px solid var(--line); display: grid; grid-template-columns: 58px 1fr; gap: 10px; align-items: center; font-size: 11px; }
    .event:last-child { border-bottom: 0; }
    .event time { padding: 3px 6px; border-radius: 6px; background: #f0f1f3; color: var(--muted); font-variant-numeric: tabular-nums; text-align: center; }
    .event span { color: #4d5661; }
    .empty { padding: 22px 14px; color: var(--muted); text-align: center; font-size: 12px; }

    .dependency-legend { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; color: var(--muted); font-size: 11px; }
    .legend-item { display: inline-flex; align-items: center; gap: 6px; }
    .legend-line { width: 22px; height: 2px; border-radius: 999px; background: #a8afb7; }
    .legend-line.blocked { height: 0; border-top: 2px dashed var(--amber); background: transparent; }
    .graph-scroll { overflow-x: auto; overscroll-behavior-inline: contain; background: #fafbfc; }
    .dependency-svg { display: block; width: 100%; min-width: 900px; height: auto; }
    .graph-layer-label { fill: #737c87; font-size: 10px; font-weight: 750; letter-spacing: .8px; text-transform: uppercase; }
    .graph-edge { fill: none; stroke: #aab1b9; stroke-width: 1.8; opacity: .8; }
    .graph-edge.blocked { stroke: var(--amber); stroke-dasharray: 5 5; opacity: .9; }
    .graph-node rect { fill: #fff; stroke: var(--line-strong); stroke-width: 1.2; filter: drop-shadow(0 2px 4px rgba(22,27,32,.06)); }
    .graph-node .node-dot { fill: var(--slate); }
    .graph-node .node-title { fill: var(--text); font-size: 12px; font-weight: 700; }
    .graph-node .node-state { fill: var(--muted); font-size: 9px; font-weight: 650; }
    .graph-node.healthy rect { stroke: #9fd0af; }
    .graph-node.healthy .node-dot { fill: var(--green); }
    .graph-node.action_required rect { fill: #fffdf7; stroke: #e5c77e; }
    .graph-node.action_required .node-dot { fill: var(--amber); }
    .graph-node.waiting rect, .graph-node.configuring rect { fill: #f7fbfc; stroke: #9cc7cf; }
    .graph-node.waiting .node-dot, .graph-node.configuring .node-dot { fill: var(--blue); }
    .graph-node.failed rect { fill: #fff9f9; stroke: #dfa0a3; }
    .graph-node.failed .node-dot { fill: var(--red); }
    .graph-hint { padding: 9px 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 10px; text-align: center; }
    .dependency-table th:nth-child(1), .dependency-table td:nth-child(1) { width: 22%; }
    .dependency-table th:nth-child(2), .dependency-table td:nth-child(2) { width: 30%; }
    .dependency-table th:nth-child(3), .dependency-table td:nth-child(3) { width: auto; }
    .dependency-table th:nth-child(4), .dependency-table td:nth-child(4) { width: 132px; text-align: left; }
    .dependency-chips { display: flex; flex-wrap: wrap; gap: 5px; }
    .dependency-chip { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 7px; border: 1px solid var(--line); border-radius: 999px; background: #f3f4f6; color: #5b6570; font-size: 10px; font-weight: 650; }
    .dependency-chip.blocked { border-color: #ead5a8; background: var(--amber-soft); color: #8b5b0c; }
    .blocker-copy { color: var(--muted); font-size: 11px; }
    .blocker-copy strong { color: var(--text); font-weight: 700; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

    .fleet-toolbar { margin-bottom: 14px; display: grid; grid-template-columns: minmax(220px, 1fr) 170px auto; gap: 10px; align-items: center; }
    .fleet-toolbar input, .fleet-toolbar select { min-height: 38px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 7px 10px; background: #fff; color: var(--text); }
    .fleet-toolbar select { width: auto; }
    .fleet-count { justify-self: end; color: var(--muted); font-size: 12px; white-space: nowrap; }
    .service-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .service-card { min-width: 0; min-height: 218px; padding: 16px; border: 1px solid var(--line); border-radius: 10px; background: #fff; box-shadow: var(--shadow); color: var(--text); display: flex; flex-direction: column; transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }
    .service-card:hover { border-color: #b9c0c8; box-shadow: 0 4px 14px rgba(22,27,32,.08); text-decoration: none; transform: translateY(-1px); }
    .service-card:focus-visible { outline-offset: 3px; }
    .service-card.action_required { border-top-color: #ddb96c; }
    .service-card.failed { border-top-color: #d98a8d; }
    .service-card.healthy .service-icon { background: var(--green-soft); color: #237346; }
    .service-card.action_required .service-icon { background: var(--amber-soft); color: #97600b; }
    .service-card.failed .service-icon { background: var(--red-soft); color: #a63a37; }
    .service-hero.healthy .service-icon { background: var(--green-soft); color: #237346; }
    .service-hero.action_required .service-icon { background: var(--amber-soft); color: #97600b; }
    .service-hero.failed .service-icon { background: var(--red-soft); color: #a63a37; }
    .service-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
    .service-card-identity { min-width: 0; display: flex; align-items: center; gap: 11px; }
    .service-card-identity .service-icon { width: 36px; height: 36px; font-size: 10px; }
    .service-card-title { min-width: 0; }
    .service-card-title strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
    .service-card-title small { display: block; margin-top: 2px; color: var(--muted); font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; }
    .service-card-detail { min-height: 38px; margin: 13px 0; color: var(--muted); font-size: 12px; }
    .service-quick-metrics { margin: auto 0 0; padding-top: 13px; border-top: 1px solid var(--line); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
    .service-quick-metrics div { min-width: 0; }
    .service-quick-metrics dt { color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .45px; text-transform: uppercase; }
    .service-quick-metrics dd { margin: 3px 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 650; font-variant-numeric: tabular-nums; }
    .service-card-foot { margin-top: 13px; display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 10px; }
    .service-card-foot strong { color: var(--blue-dark); font-size: 11px; }
    .service-grid-empty { grid-column: 1 / -1; border: 1px dashed var(--line-strong); border-radius: 10px; background: #fff; }

    .back-link { min-height: 32px; margin-bottom: 12px; display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 650; }
    .service-hero { margin-bottom: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 10px; background: #fff; box-shadow: var(--shadow); display: flex; align-items: center; justify-content: space-between; gap: 18px; }
    .service-hero-main { min-width: 0; display: flex; align-items: center; gap: 13px; }
    .service-hero .service-icon { width: 44px; height: 44px; font-size: 12px; }
    .service-hero-title { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; }
    .service-hero-title h2 { margin: 0; font-size: 19px; }
    .service-hero p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .service-open { flex: 0 0 auto; min-height: 38px; padding: 8px 14px; border: 1px solid var(--line-strong); border-radius: 8px; display: inline-flex; align-items: center; font-weight: 700; }
    .service-open:hover { background: #f5f7f8; text-decoration: none; }
    .service-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .description-list { margin: 0; display: grid; grid-template-columns: 120px minmax(0, 1fr); }
    .description-list dt, .description-list dd { margin: 0; padding: 9px 0; border-top: 1px solid var(--line); }
    .description-list dt:nth-of-type(1), .description-list dt:nth-of-type(1) + dd { border-top: 0; }
    .description-list dt { color: var(--muted); font-size: 11px; }
    .description-list dd { font-size: 12px; overflow-wrap: anywhere; }
    .description-list code { font: 10px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .detail-dependencies { display: flex; flex-wrap: wrap; gap: 6px; }
    .detail-dependencies a { min-height: 28px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 999px; background: #f4f5f6; display: inline-flex; align-items: center; font-size: 11px; font-weight: 650; }
    .detail-dependencies a:hover { border-color: #b8c0c8; text-decoration: none; }

    @media (max-width: 1040px) {
      .summary { grid-template-columns: minmax(260px, 1fr) repeat(4, 92px); }
      .operations { grid-template-columns: 1fr; }
      .activity-list { max-height: 280px; }
      .path-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .library-row, .library-editor { grid-template-columns: 160px minmax(220px, 1fr); }
      .library-row .library-apps, .library-editor .library-apps { grid-column: 1 / -1; }
      .service-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
      :root { --sidebar-width: 68px; }
      .brand { padding: 0 13px; }
      .brand-name, .nav-label, .nav-text, .nav-badge, .sidebar-foot { display: none; }
      .nav { padding-inline: 9px; }
      .nav a { padding: 0 15px; }
      .topbar { padding-inline: 18px; }
      .workspace { padding: 18px; }
      .summary { grid-template-columns: repeat(4, 1fr); }
      .summary-status { grid-column: 1 / -1; border-bottom: 1px solid var(--line); }
      .metric { border-left: 1px solid var(--line); }
      .metric:nth-child(2) { border-left: 0; }
      .vpn-form { grid-template-columns: 1fr 1fr; }
      .vpn-form button { grid-column: 1 / -1; justify-self: end; }
      .service-detail-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .sidebar { position: static; width: 100%; height: auto; display: block; }
      .brand { height: 54px; padding-inline: 14px; }
      .brand-name { display: block; }
      .nav { padding: 4px 8px; border-top: 1px solid rgba(255,255,255,.08); display: flex; overflow-x: auto; gap: 4px; }
      .nav-label, .sidebar-foot { display: none; }
      .nav a { min-width: 54px; min-height: 44px; margin: 0; padding: 0 16px; border: 1px solid transparent; border-radius: 9px; justify-content: center; }
      .nav a.active { border-color: #464d56; box-shadow: 0 1px 2px rgba(0, 0, 0, .18); }
      .content { margin-left: 0; }
      .topbar { height: auto; min-height: 62px; position: static; padding: 10px 14px; align-items: flex-start; }
      .page-title p, .live-state, #refresh { display: none; }
      .workspace { padding: 14px; }
      .scope-bar { display: grid; grid-template-columns: 1fr; gap: 7px; align-items: start; }
      .scope { flex-wrap: nowrap; }
      .fresh { justify-self: start; }
      .summary { grid-template-columns: repeat(2, 1fr); }
      .metric:nth-child(4) { border-left: 0; border-top: 1px solid var(--line); }
      .metric:nth-child(5) { border-top: 1px solid var(--line); }
      .vpn-form { grid-template-columns: 1fr; }
      .vpn-form button { grid-column: auto; width: 100%; }
      .panel-head { align-items: flex-start; flex-direction: column; }
      .path-grid { grid-template-columns: 1fr; }
      .library-row, .library-editor { grid-template-columns: 1fr; gap: 10px; }
      .library-row .library-apps, .library-editor .library-apps { grid-column: auto; }
      .library-path code { white-space: normal; overflow-wrap: anywhere; }
      .propagation-step { grid-template-columns: 1fr; gap: 4px; }
      .root-summary { grid-template-columns: 1fr; }
      .root-summary div, .root-summary div:nth-child(even), .root-summary div:nth-child(-n+2) { border-left: 0; border-top: 1px solid var(--line); }
      .root-summary div:first-child { border-top: 0; }
      .attention-item { grid-template-columns: 1fr; gap: 5px; }
      .mode-tabs { display: flex; }
      .mode-tabs a { flex: 1; }
      .panel-actions { align-items: stretch; flex-direction: column; }
      .panel-actions button { width: 100%; }
      table, tbody { display: block; }
      thead { display: none; }
      tr { display: grid; grid-template-columns: 1fr auto; padding: 13px 14px; border-top: 1px solid var(--line); gap: 8px 12px; }
      tbody tr:first-child { border-top: 0; }
      td { display: block; width: auto !important; padding: 0; border: 0; text-align: left !important; }
      td:nth-child(2) { grid-column: 2; grid-row: 1; }
      td:nth-child(3) { grid-column: 1 / -1; padding-left: 37px; }
      td:nth-child(4) { grid-column: 1 / -1; padding-left: 37px; }
      .open-link { display: inline-flex; padding: 4px 8px; }
      .dependency-table td:nth-child(2), .dependency-table td:nth-child(3) { grid-column: 1 / -1; grid-row: auto; padding-left: 37px; }
      .dependency-table td:nth-child(4) { grid-column: 2; grid-row: 1; padding-left: 0; }
      .dependency-legend { align-items: flex-start; flex-direction: column; gap: 6px; }
      .fleet-toolbar { grid-template-columns: 1fr; }
      .fleet-toolbar select { width: 100%; }
      .fleet-count { justify-self: start; }
      .service-grid { grid-template-columns: 1fr; }
      .service-card { min-height: 0; }
      .service-hero { align-items: flex-start; flex-direction: column; }
      .service-open { width: 100%; justify-content: center; }
      .description-list { grid-template-columns: 1fr; }
      .description-list dt { padding-bottom: 2px; }
      .description-list dd { padding-top: 0; border-top: 0; }
      .setup-intro { grid-template-columns: 1fr; }
      .module-grid { grid-template-columns: 1fr; }
      .credential-fields { grid-template-columns: 1fr; }
      .setup-intro button, .setup-actions button { width: 100%; }
      .setup-actions { align-items: stretch; flex-direction: column; }
      .setup-feedback { margin-right: 0; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
<div class="app-shell">
  <aside class="sidebar" aria-label="Primary navigation">
    <div class="brand"><div class="brand-mark"><img src="/icon.png" alt=""></div><div class="brand-name">umbrel<span>arr</span></div></div>
    <nav class="nav">
      <div class="nav-label">System</div>
      <a class="%%NAV_OVERVIEW%%" %%CURRENT_OVERVIEW%% href="/" aria-label="Overview"><span class="nav-icon" aria-hidden="true">⌂</span><span class="nav-text">Overview</span><span class="nav-badge" id="navAttention">0</span></a>
      <a class="%%NAV_SERVICES%%" %%CURRENT_SERVICES%% href="/services" aria-label="Services"><span class="nav-icon" aria-hidden="true">≡</span><span class="nav-text">Services</span></a>
      <a class="%%NAV_DEPENDENCIES%%" %%CURRENT_DEPENDENCIES%% href="/dependencies" aria-label="Dependencies"><span class="nav-icon" aria-hidden="true">⌘</span><span class="nav-text">Dependencies</span></a>
      <div class="nav-label">Settings</div>
      <a class="%%NAV_SETUP%%" %%CURRENT_SETUP%% href="/setup" aria-label="Setup"><span class="nav-icon" aria-hidden="true">✓</span><span class="nav-text">Setup</span></a>
      <a class="%%NAV_LIBRARIES%%" %%CURRENT_LIBRARIES%% href="/libraries" aria-label="Libraries"><span class="nav-icon" aria-hidden="true">▰</span><span class="nav-text">Libraries</span></a>
      <a class="%%NAV_ACTIVITY%%" %%CURRENT_ACTIVITY%% href="/activity" aria-label="Activity"><span class="nav-icon" aria-hidden="true">↻</span><span class="nav-text">Activity</span></a>
    </nav>
    <div class="sidebar-foot">Managed scope<br><strong>Local Umbrel stack</strong></div>
  </aside>

  <div class="content">
    <header class="topbar">
      <div class="page-title"><h1>%%PAGE_TITLE%%</h1><p>%%PAGE_SUBTITLE%%</p></div>
      <div class="top-actions">
        <span class="live-state"><span class="live-dot" id="liveDot"></span><span id="freshTop">Checking status</span></span>
        <button id="refresh">Refresh</button>
        <button class="primary" id="reconcile">Reconcile</button>
      </div>
    </header>

    <main class="workspace">
      <div class="scope-bar"><span class="scope"><span class="scope-tag">Local</span><span>%%SCOPE_COPY%%</span></span><span class="fresh" id="fresh">Not checked yet</span></div>
      %%CONTENT%%
    </main>
  </div>
</div>
<script>
const labels={unknown:'Unknown',waiting:'Waiting',action_required:'Action required',configuring:'Configuring',healthy:'Healthy',failed:'Failed'};
const glyphs={'privado-vpn':'PV',flaresolverr:'FS',prowlarr:'P',qbittorrent:'qB',sabnzbd:'S',sonarr:'S', 'sonarr-4k':'S4',radarr:'R','radarr-4k':'R4',bazarr:'B',overseerr:'O',profilarr:'P',umbrelarr:'ua',lidarr:'L'};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const element=id=>document.getElementById(id);
const setText=(id,value)=>{const target=element(id);if(target)target.textContent=value;};
let storageState=null;
let statusState=null;
let setupState=null;
let moduleSelectionDirty=false;
function ago(epoch){if(!epoch)return['Not checked yet',true];const seconds=Math.max(0,Math.floor(Date.now()/1000-epoch));if(seconds<10)return['Updated just now',false];if(seconds<60)return[`Updated ${seconds}s ago`,false];const minutes=Math.floor(seconds/60);return[`Updated ${minutes}m ago`,minutes>=3];}
function overall(data){const counts=data.counts||{};if(counts.failed)return['failed','Stack needs intervention',`${counts.failed} service${counts.failed===1?'':'s'} failed the last check.`];if(counts.action_required)return['action_required','Setup needs attention',`${counts.action_required} action${counts.action_required===1?'':'s'} required to finish configuration.`];if((counts.waiting||0)+(counts.configuring||0))return['configuring','Stack is configuring','Services are starting or managed settings are being applied.'];if((counts.healthy||0)===data.services.length&&data.services.length)return['healthy','All selected services operational','The selected stack is configured and responding.'];return['unknown','Checking stack','Waiting for current service health information.'];}
function dependencyLayers(services){const remaining=new Map(services.map(service=>[service.id,service]));const placed=new Set();const layers=[];while(remaining.size){const layer=[...remaining.values()].filter(service=>(service.dependencies||[]).every(id=>placed.has(id)||!remaining.has(id)));if(!layer.length){layers.push([...remaining.values()]);break;}layers.push(layer);for(const service of layer){placed.add(service.id);remaining.delete(service.id);}}return layers;}
function dependencyChips(ids,byId,blockedIds=[]){if(!ids.length)return '<span class="detail">None</span>';const blocked=new Set(blockedIds);return `<span class="dependency-chips">${ids.map(id=>`<span class="dependency-chip${blocked.has(id)?' blocked':''}">${esc(byId.get(id)?.name||id)}</span>`).join('')}</span>`;}
function blockerCopy(service,byId){const waiting=service.waitingOn||[];if(waiting.length)return dependencyChips(waiting,byId,waiting);if(service.status==='action_required')return `<span class="blocker-copy"><strong>Own setup:</strong> ${esc(service.detail)}</span>`;if(service.status==='failed')return `<span class="blocker-copy"><strong>Service error:</strong> ${esc(service.detail)}</span>`;if(['waiting','configuring'].includes(service.status))return `<span class="blocker-copy"><strong>Internal step:</strong> ${esc(service.detail)}</span>`;if(service.status==='unknown')return '<span class="blocker-copy">Waiting for the first check</span>';return '<span class="blocker-copy">No blockers</span>';}
function renderDependencies(data){const graph=element('dependencyGraph');const rows=element('dependencyRows');if(!graph&&!rows)return;const services=data.services||[];const byId=new Map(services.map(service=>[service.id,service]));const blocked=services.filter(service=>(service.waitingOn||[]).length||['action_required','failed'].includes(service.status));setText('blockedCount',`${blocked.length} blocked`);if(rows)rows.innerHTML=services.map(service=>`<tr class="${esc(service.status)}"><td><a class="service-name" href="${esc(service.link)}" target="_blank" rel="noreferrer"><span class="service-icon" aria-hidden="true">${esc(glyphs[service.id]||service.name.slice(0,2))}</span>${esc(service.name)}</a></td><td>${dependencyChips(service.dependencies||[],byId)}</td><td>${blockerCopy(service,byId)}</td><td><span class="status ${esc(service.status)}"><span class="status-dot"></span>${esc(labels[service.status]||service.status)}</span></td></tr>`).join('');if(!graph)return;const layers=dependencyLayers(services);const width=1120,height=560,nodeWidth=168,nodeHeight=58,padX=42,padY=58;const xGap=layers.length>1?(width-(padX*2)-nodeWidth)/(layers.length-1):0;const positions=new Map();layers.forEach((layer,layerIndex)=>layer.forEach((service,index)=>{const band=(height-padY-28)/layer.length;positions.set(service.id,{x:padX+(layerIndex*xGap),y:padY+(index*band)+(band-nodeHeight)/2});}));const layerNames=['Foundations','Network and downloads','Media apps','Integrations'];const layerLabels=layers.map((layer,index)=>`<text class="graph-layer-label" x="${padX+(index*xGap)}" y="28">${esc(layerNames[index]||`Stage ${index+1}`)}</text>`).join('');const edges=services.flatMap(service=>(service.dependencies||[]).map(sourceId=>{const source=positions.get(sourceId),target=positions.get(service.id),sourceService=byId.get(sourceId);if(!source||!target)return '';const startX=source.x+nodeWidth,startY=source.y+(nodeHeight/2),endX=target.x,endY=target.y+(nodeHeight/2),bend=(startX+endX)/2;return `<path class="graph-edge${sourceService?.status==='healthy'?'':' blocked'}" d="M ${startX} ${startY} C ${bend} ${startY}, ${bend} ${endY}, ${endX} ${endY}" marker-end="url(#arrow)"/>`;})).join('');const nodes=services.map(service=>{const position=positions.get(service.id);if(!position)return '';return `<g class="graph-node ${esc(service.status)}" transform="translate(${position.x} ${position.y})"><title>${esc(service.name)} — ${esc(labels[service.status]||service.status)}. ${esc(service.detail)}</title><rect width="${nodeWidth}" height="${nodeHeight}" rx="8"/><circle class="node-dot" cx="16" cy="18" r="4"/><text class="node-title" x="27" y="22">${esc(service.name)}</text><text class="node-state" x="16" y="42">${esc(labels[service.status]||service.status)}</text></g>`;}).join('');graph.setAttribute('viewBox',`0 0 ${width} ${height}`);graph.innerHTML=`<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#9ca4ad"/></marker></defs>${layerLabels}${edges}${nodes}`;setText('dependencyGraphDescription',blocked.length?`${blocked.length} services currently have an upstream blocker or require their own setup.`:'All reconciliation dependencies are ready.');}
function selectedModules(){return [...document.querySelectorAll('[data-module]:checked')].map(input=>input.value);}
function updateSetupModuleFields(){const selected=new Set(selectedModules());const hasLibraries=['sonarr','sonarr-4k','radarr','radarr-4k','lidarr'].some(id=>selected.has(id));if(element('setupStorageOptions'))element('setupStorageOptions').hidden=!hasLibraries;if(element('qbittorrentCredentials'))element('qbittorrentCredentials').hidden=!selected.has('qbittorrent');}
function markSetupSelectionDirty(){moduleSelectionDirty=true;setupState.detectionComplete=false;setupState.canConfirm=false;setText('setupCount','Selection changed · run detection again');}
function selectedProfile(){const signature=selectedModules().sort().join(',');return (setupState?.profiles||[]).find(profile=>[...profile.enabledServices].sort().join(',')===signature);}
function syncProfileSelection(){const profile=element('stackProfile');if(!profile)return;profile.value=selectedProfile()?.id||'custom';const selected=(setupState.profiles||[]).find(item=>item.id===profile.value);setText('stackProfileHelp',selected?.description||'Custom selection. Every module remains individually adjustable.');}
function renderModuleCatalog(){
  const target=element('moduleCatalog');
  if(!target||!setupState||moduleSelectionDirty&&target.children.length)return;
  const modules=(setupState.modules||[]).filter(module=>module.role!=='vpn_provider');
  target.innerHTML=modules.map(module=>`<label class="module-option"><input type="checkbox" data-module value="${esc(module.id)}"${module.enabled?' checked':''}${module.required?' disabled':''}><span><strong>${esc(module.name)}</strong><small>${esc(module.role.replaceAll('_',' '))}${module.required?' · required':''}</small></span></label>`).join('');
  const profile=element('stackProfile');
  if(profile){
    profile.innerHTML=[...(setupState.profiles||[]).map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`),'<option value="custom">Custom selection</option>'].join('');
    profile.onchange=()=>{const selected=(setupState.profiles||[]).find(item=>item.id===profile.value);if(!selected)return;const enabled=new Set(selected.enabledServices);document.querySelectorAll('[data-module]').forEach(input=>{input.checked=input.disabled||enabled.has(input.value);});markSetupSelectionDirty();syncProfileSelection();updateSetupModuleFields();renderSetupRoots();};
  }
  const provider=element('vpnProvider');
  if(provider){provider.innerHTML=(setupState.vpnProviders||[]).map(item=>`<option value="${esc(item.id)}"${item.id===setupState.vpnProvider?' selected':''}>${esc(item.name)}</option>`).join('');const describe=()=>setText('vpnProviderHelp',(setupState.vpnProviders||[]).find(item=>item.id===provider.value)?.description||'');describe();provider.onchange=()=>{describe();setText('vpnProviderState','Run detection to verify this routing choice.');markSetupSelectionDirty();renderSetupRoots();};}
  document.querySelectorAll('[data-module]').forEach(input=>input.onchange=()=>{markSetupSelectionDirty();syncProfileSelection();updateSetupModuleFields();renderSetupRoots();});
  syncProfileSelection();
  updateSetupModuleFields();
}
function renderSetup(){if(!setupState)return;renderModuleCatalog();const list=element('setupApps');const apps=setupState.apps||[];if(list){list.innerHTML=apps.length?apps.map(app=>{const state=!app.reachable?'failed':app.credentials?'healthy':'action_required';const label=!app.reachable?'Not found':app.credentials?'Ready':app.action==='temporary_password_required'?'One-time password may be required':'API key pending';return `<div class="attention-item"><div class="attention-name">${esc(app.name)}</div><div><span class="status ${state}"><span class="status-dot"></span>${label}</span><div class="detail">${esc(app.detail)}</div></div><a class="open-link" href="${esc(app.link)}" target="_blank" rel="noreferrer">Open</a></div>`;}).join(''):'<div class="empty">Choose modules, then run read-only detection.</div>';}setText('setupCount',moduleSelectionDirty?'Selection changed · run detection again':setupState.detectionComplete?`${setupState.detectedCount} of ${setupState.requiredCount} selected apps detected`:'Detection has not run yet');setText('setupComplete',setupState.phase==='confirmed'?'Setup complete. Module selection, provider, consent, and storage are restored from API-owned Prowlarr markers.':setupState.confirmed?'Consent is recorded. Finish the action below to complete setup.':'Nothing will be configured until you confirm this setup.');setText('vpnProviderState',setupState.vpnStatus?.detail||'Run detection to verify this routing choice.');const confirm=element('confirmSetup');if(confirm)confirm.disabled=moduleSelectionDirty||!setupState.canConfirm||setupState.phase==='confirmed';const panel=element('setupPanel');if(panel)panel.hidden=setupState.phase==='confirmed';if(element('reconcile'))element('reconcile').disabled=setupState.phase!=='confirmed'||Boolean(statusState?.running);renderSetupRoots();}
function renderSetupRoots(){const target=element('setupRootSelections');if(!target||!storageState)return;const storageRequired=(storageState.libraries||[]).length>0;let selected=document.querySelector('[name="setupStorageMode"]:checked');if(!selected&&storageRequired){const mode=storageState.actionRequired?'adopt':storageState.mode==='adopted'?'adopt':storageState.mode;selected=document.querySelector(`[name="setupStorageMode"][value="${mode}"]`);if(selected)selected.checked=true;}const adopt=storageRequired&&selected?.value==='adopt';target.hidden=!adopt;if(adopt)target.innerHTML=storageState.libraries.map(library=>{const candidates=storageState.candidates?.[library.key]||[];const storedId=storageState.rootIds?.[library.key];const selectedId=storedId??(candidates.length===1?candidates[0].id:null);const placeholder=selectedId==null?'<option value="" disabled selected>Choose a root…</option>':'';return `<label>${esc(library.name)} ${esc(library.variant)}<select data-setup-root="${esc(library.key)}" required>${placeholder}${candidates.map(item=>`<option value="${esc(item.id)}"${String(item.id)===String(selectedId)?' selected':''}>${esc(item.path)}</option>`).join('')}</select></label>`;}).join('');const selects=[...target.querySelectorAll('select')];const rootsReady=!storageRequired||!adopt||selects.length===storageState.libraries.length&&selects.every(select=>select.value);const confirm=element('confirmSetup');if(confirm)confirm.disabled=moduleSelectionDirty||!setupState?.canConfirm||setupState?.phase==='confirmed'||storageRequired&&!selected||!rootsReady;}
async function loadSetup(){const response=await fetch('/api/setup',{cache:'no-store'});if(!response.ok)throw new Error('Unable to load setup state');setupState=await response.json();renderSetup();}
const serviceStatusOrder={failed:0,action_required:1,waiting:2,configuring:2,unknown:3,healthy:4};
function serviceCard(service){return `<a class="service-card ${esc(service.status)}" href="/services/${encodeURIComponent(service.id)}" aria-label="Open ${esc(service.name)} details"><span class="service-card-head"><span class="service-card-identity"><span class="service-icon" aria-hidden="true">${esc(glyphs[service.id]||service.name.slice(0,2))}</span><span class="service-card-title"><strong>${esc(service.name)}</strong><small>${esc(service.id)}</small></span></span><span class="status ${esc(service.status)}"><span class="status-dot"></span>${esc(labels[service.status]||service.status)}</span></span><span class="service-card-detail">${esc(service.detail)}</span><span class="service-card-foot"><span>API health and reconciliation state</span><strong>View details →</strong></span></a>`;}
function renderServiceGrid(){const grid=element('serviceGrid');if(!grid||!statusState)return;const query=(element('serviceSearch')?.value||'').trim().toLowerCase();const state=element('serviceStateFilter')?.value||'all';const services=[...(statusState.services||[])].sort((a,b)=>(serviceStatusOrder[a.status]??9)-(serviceStatusOrder[b.status]??9)||a.name.localeCompare(b.name));const filtered=services.filter(service=>(!query||`${service.name} ${service.id} ${service.detail}`.toLowerCase().includes(query))&&(state==='all'||service.status===state));setText('serviceCount',`${filtered.length} of ${services.length} services`);grid.innerHTML=filtered.length?filtered.map(serviceCard).join(''):'<div class="empty service-grid-empty">No managed services match these filters.</div>';}
function detailDependencyLinks(ids,byId){if(!ids.length)return '<span class="detail">No reconciliation dependencies.</span>';return `<span class="detail-dependencies">${ids.map(id=>`<a href="/services/${encodeURIComponent(id)}">${esc(byId.get(id)?.name||id)}</a>`).join('')}</span>`;}
function renderServiceDetail(){const detail=element('serviceDetail');if(!detail||!statusState)return;const serviceId=detail.dataset.serviceId;const service=(statusState.services||[]).find(item=>item.id===serviceId);if(!service){setText('serviceDetailName','Service unavailable');setText('serviceDetailCopy','This service is not part of the current managed stack.');return;}const byId=new Map(statusState.services.map(item=>[item.id,item]));const hero=element('serviceHero');if(hero)hero.className=`service-hero ${service.status}`;setText('serviceDetailGlyph',glyphs[service.id]||service.name.slice(0,2));setText('serviceDetailName',service.name);setText('serviceDetailCopy',service.detail);const status=element('serviceDetailStatus');if(status){status.className=`status ${service.status}`;status.innerHTML=`<span class="status-dot"></span>${esc(labels[service.status]||service.status)}`;}const open=element('serviceOpen');if(open){open.href=service.link;open.hidden=!service.link;}const dependencies=element('detailDependencies');if(dependencies)dependencies.innerHTML=detailDependencyLinks(service.dependencies||[],byId);const waiting=element('detailWaitingOn');if(waiting)waiting.innerHTML=(service.waitingOn||[]).length?detailDependencyLinks(service.waitingOn,byId):'<span class="detail">No current blockers.</span>';}
async function load(){
  const response=await fetch('/api/status',{cache:'no-store'});
  if(!response.ok)throw new Error('Unable to load stack status');
  const data=await response.json();
  statusState=data;
  const counts=data.counts||{};
  setText('healthy',counts.healthy||0);
  setText('attentionCount',counts.action_required||0);
  setText('navAttention',(counts.action_required||0)+(counts.failed||0));
  setText('waiting',(counts.waiting||0)+(counts.configuring||0));
  setText('failed',counts.failed||0);
  setText('serviceCount',`${data.services.length} services`);
  const [freshLabel,stale]=ago(data.lastCompletedAt);
  setText('fresh',(data.running?'Reconciliation running · ':'')+freshLabel);
  if(element('fresh'))element('fresh').classList.toggle('stale',stale);
  setText('freshTop',data.running?'Reconciling':freshLabel);
  if(element('reconcile'))element('reconcile').disabled=data.running||setupState?.confirmed===false;
  const [state,title,detail]=overall(data);
  if(element('healthMark'))element('healthMark').className=`status-orb ${state}`;
  if(element('liveDot'))element('liveDot').className=`live-dot ${state}`;
  setText('healthTitle',title);
  setText('healthDetail',detail);
  const vpn=data.services.find(service=>service.id==='privado-vpn');
  if(element('vpnPanel'))element('vpnPanel').hidden=!(vpn&&vpn.status==='action_required');
  renderServiceGrid();
  renderServiceDetail();
  renderDependencies(data);
  renderLibraryPlan();
  if(element('attentionRows')){
    const actions=data.services.filter(service=>['failed','action_required'].includes(service.status));
    element('attentionRows').innerHTML=actions.length?actions.map(service=>{const setup=service.id==='umbrelarr';const vpn=service.id==='privado-vpn';const href=setup?'/setup':vpn?'#vpnPanel':service.link;return `<div class="attention-item"><div class="attention-name">${esc(service.name)}</div><div><span class="status ${esc(service.status)}"><span class="status-dot"></span>${esc(labels[service.status])}</span><div class="detail">${esc(service.detail)}</div></div><a class="open-link" href="${esc(href)}"${setup||vpn?'':' target="_blank" rel="noreferrer"'}>${setup?'Set up':vpn?'Configure':'Open'}</a></div>`;}).join(''):'<div class="empty">No services need action.</div>';
  }
  if(element('events'))element('events').innerHTML=data.events.length?data.events.slice(0,50).map(event=>`<div class="event"><time datetime="${new Date(event.at*1000).toISOString()}">${new Date(event.at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time><span>${esc(event.message)}</span></div>`).join(''):'<div class="empty">No reconciliation activity yet.</div>';
}
function setStorageFields(roots){for(const [name,value] of Object.entries(roots||{})){document.querySelectorAll(`[name="${name}"]`).forEach(input=>input.value=value);document.querySelectorAll(`[data-root="${name}"]`).forEach(target=>target.textContent=value);}}
function libraryRootsFromForm(){const roots={};for(const library of storageState?.libraries||[]){const input=document.querySelector(`[name="${library.key}"]`);roots[library.key]=input?.value||library.root;}return roots;}
function libraryAppChips(library){return `<span class="library-apps">${library.apps.map(slug=>{const service=(statusState?.services||[]).find(item=>item.id===slug);const state=service?.status||'unknown';const name=service?.name||slug;return `<span class="library-app ${esc(state)}" title="${esc(name)}: ${esc(labels[state]||state)}"><span class="status-dot"></span>${esc(name)}</span>`;}).join('')}</span>`;}
function renderLibraryPlan(roots=libraryRootsFromForm()){if(!storageState)return;const plan=element('libraryPlan');if(plan){plan.innerHTML=storageState.libraries.map(library=>`<div class="library-row"><span class="library-identity"><span class="library-glyph" aria-hidden="true">${esc(library.variant==='4K'?'4K':library.id==='music'?'♪':'HD')}</span><span><strong>${esc(library.name)}</strong><small>${esc(library.variant)} library</small></span></span><span class="library-path"><code>${esc(roots[library.key]||library.root)}</code><small>${esc(library.category)} download category</small></span>${libraryAppChips(library)}</div>`).join('');}document.querySelectorAll('[data-library-apps]').forEach(target=>{const library=storageState.libraries.find(item=>item.key===target.dataset.libraryApps);if(library)target.innerHTML=libraryAppChips(library);});}
function renderStorageRoots(){const target=element('storageRootSelections');if(!target||!storageState)return;const adopt=document.querySelector('[name="storageMode"]:checked')?.value==='adopt';target.hidden=!adopt;if(!adopt)return;target.innerHTML=storageState.libraries.map(library=>{const candidates=storageState.candidates?.[library.key]||[];const selectedId=storageState.rootIds?.[library.key];const placeholder=selectedId?'':'<option value="" disabled selected>Choose a root…</option>';return `<label>${esc(library.name)} ${esc(library.variant)}<select data-storage-root="${esc(library.key)}" required>${placeholder}${candidates.map(item=>`<option value="${esc(item.id)}"${item.id===selectedId?' selected':''}>${esc(item.path)}</option>`).join('')}</select></label>`;}).join('');}
function selectStorageMode(mode,applyPreset=false){const publicMode=mode==='adopted'?'adopt':mode;const radio=document.querySelector(`[name="storageMode"][value="${publicMode}"]`);if(radio)radio.checked=true;setText('storageScope',publicMode==='network'?'Libraries on linked /network storage':publicMode==='adopt'?'Libraries using selected existing roots':'Libraries on Umbrel /downloads');if(applyPreset&&storageState?.presets[publicMode])renderLibraryPlan(storageState.presets[publicMode]);renderStorageRoots();}
async function loadStorage(){const response=await fetch('/api/storage',{cache:'no-store'});if(!response.ok)throw new Error('Unable to load library locations');storageState=await response.json();selectStorageMode(storageState.mode);renderLibraryPlan(storageState.roots);renderSetupRoots();}
async function mutate(url,options={}){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},...options});if(!response.ok){const data=await response.json().catch(()=>({error:'Request failed'}));throw new Error(data.error||'Request failed');}await load();}
if(element('refresh'))element('refresh').onclick=()=>load().catch(error=>alert(error.message));
if(element('reconcile'))element('reconcile').onclick=()=>mutate('/api/reconcile').catch(error=>alert(error.message));
if(element('detectApps'))element('detectApps').onclick=async()=>{const button=element('detectApps');const error=element('setupError');error.textContent='';button.disabled=true;button.textContent='Detecting selected apps…';const body=new URLSearchParams({enabledServices:JSON.stringify(selectedModules()),vpnProvider:element('vpnProvider')?.value||'privado'});try{const response=await fetch('/api/setup/detect',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw new Error(data.error||'Detection failed');moduleSelectionDirty=false;setupState=data;renderSetup();}catch(value){error.textContent=value.message;}finally{button.disabled=false;button.textContent='Detect selected apps';}};
if(element('confirmSetup'))element('confirmSetup').onclick=async()=>{const button=element('confirmSetup');const error=element('setupError');error.textContent='';button.disabled=true;button.textContent='Connecting selected apps…';const rootIds={};document.querySelectorAll('[data-setup-root]').forEach(select=>rootIds[select.dataset.setupRoot]=Number(select.value));const body=new URLSearchParams({storageMode:document.querySelector('[name="setupStorageMode"]:checked')?.value||'',rootIds:JSON.stringify(rootIds),qbittorrentUsername:element('qbittorrentUsername')?.value||'admin',qbittorrentTemporaryPassword:element('qbittorrentTemporaryPassword')?.value||'',enabledServices:JSON.stringify(selectedModules()),vpnProvider:element('vpnProvider')?.value||'privado'});try{const response=await fetch('/api/setup/confirm',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw new Error(data.error||'Setup failed');setupState=data;renderSetup();window.location='/';}catch(value){error.textContent=value.message;button.disabled=false;button.textContent='Connect selected apps';}};
document.querySelectorAll('[name="setupStorageMode"]').forEach(input=>input.onchange=renderSetupRoots);
if(element('qbittorrentTemporaryPassword'))element('qbittorrentTemporaryPassword').oninput=renderSetupRoots;
if(element('vpnForm'))element('vpnForm').onsubmit=async event=>{event.preventDefault();const error=element('formError');error.textContent='';try{await mutate('/api/vpn/login',{body:new URLSearchParams(new FormData(event.currentTarget))});event.currentTarget.reset();}catch(value){error.textContent=value.message;}};
document.querySelectorAll('[name="storageMode"]').forEach(input=>input.onchange=()=>{setText('storageResult','');selectStorageMode(input.value,true);});
if(element('storageForm'))element('storageForm').onsubmit=async event=>{event.preventDefault();const error=element('storageError');const result=element('storageResult');const button=element('saveLibraries');error.textContent='';result.textContent='';const rootIds={};document.querySelectorAll('[data-storage-root]').forEach(select=>rootIds[select.dataset.storageRoot]=Number(select.value));const data=new URLSearchParams({mode:document.querySelector('[name="storageMode"]:checked').value,rootIds:JSON.stringify(rootIds)});button.disabled=true;button.textContent='Saving library layout…';try{await mutate('/api/storage',{body:data});await loadStorage();result.textContent='Library layout applied through the installed apps APIs.';}catch(value){error.textContent=value.message;}finally{button.disabled=false;button.textContent='Save library layout';}};
if(element('serviceSearch'))element('serviceSearch').oninput=renderServiceGrid;
if(element('serviceStateFilter'))element('serviceStateFilter').onchange=renderServiceGrid;
const initialLoads=[load(),loadSetup()];if(element('storageForm')||element('setupRootSelections'))initialLoads.push(loadStorage());
Promise.all(initialLoads).catch(error=>{setText('healthTitle','Status unavailable');setText('healthDetail',error.message);if(element('healthMark'))element('healthMark').className='status-orb failed';});
setInterval(()=>{load().catch(()=>{});loadSetup().catch(()=>{});},5000);
</script>
</body>
</html>"""


OVERVIEW = r"""
      <section class="summary" aria-label="Stack summary" aria-live="polite">
        <div class="summary-status"><span class="status-orb" id="healthMark"></span><div><h2 id="healthTitle">Checking stack</h2><p id="healthDetail">Waiting for the first reconciliation.</p></div></div>
        <div class="metric"><strong id="healthy">0</strong><span>Healthy</span></div>
        <div class="metric"><strong id="attentionCount">0</strong><span>Attention</span></div>
        <div class="metric"><strong id="waiting">0</strong><span>In progress</span></div>
        <div class="metric"><strong id="failed">0</strong><span>Failed</span></div>
      </section>
      <section class="notice" id="setupPanel" hidden>
        <div class="notice-head"><span class="notice-symbol" aria-hidden="true">⚠</span><div><h2>Connect your installed apps</h2><p>Umbrelarr does not install containers. Detect the Umbrel Arr apps you installed, review them, and explicitly allow management.</p></div></div>
        <div class="setup-actions"><span class="setup-feedback">Configuration remains paused until setup is confirmed.</span><a class="open-link" href="/setup">Open setup →</a></div>
      </section>
      <section class="notice" id="vpnPanel" hidden>
        <div class="notice-head"><span class="notice-symbol" aria-hidden="true">⚠</span><div><h2>Privado login required</h2><p>Credentials are forwarded directly to Privado and are not retained by umbrelarr.</p></div></div>
        <form class="vpn-form" id="vpnForm">
          <label><span>Username</span><input name="username" autocomplete="username" required></label>
          <label><span>Password</span><input name="password" type="password" autocomplete="current-password" required></label>
          <button class="primary" type="submit">Connect Privado</button>
        </form>
        <div class="error" id="formError" role="alert"></div>
      </section>
      <section class="panel" aria-labelledby="attentionTitle">
        <div class="panel-head"><div><h2 id="attentionTitle">Needs attention</h2><p>Complete these items before the stack can finish configuring.</p></div></div>
        <div class="attention-list" id="attentionRows"><div class="empty">Checking managed services.</div></div>
      </section>
"""


SETUP = r"""
      <section class="panel" aria-labelledby="setupTitle">
        <div class="setup-intro"><div><h2 id="setupTitle">Build your Umbrel Arr stack</h2><p>Choose the services and VPN provider you want. Detection is read-only and does not create containers or change app configuration. Confirmation stores the modular selection through Prowlarr's API and starts reconciliation.</p></div><button id="detectApps" type="button">Detect selected apps</button></div>
        <div class="scope-bar panel-body"><span id="setupCount">Detection has not run yet</span><span id="setupComplete">Nothing will be configured until you confirm this setup.</span></div>
        <div class="attention-list setup-app-list" id="setupApps" aria-live="polite"><div class="empty">Loading setup state.</div></div>
        <div class="panel-body" id="setupOptions">
          <label class="profile-select" for="stackProfile"><span>Starting profile</span><select id="stackProfile" aria-describedby="stackProfileHelp"></select><small id="stackProfileHelp">Profiles are shortcuts. Every module remains individually adjustable.</small></label>
          <fieldset class="setup-fieldset"><legend>Service modules</legend><div class="module-grid" id="moduleCatalog"></div></fieldset>
          <label class="provider-select" for="vpnProvider"><span>VPN provider</span><select id="vpnProvider" aria-describedby="vpnProviderHelp vpnProviderState"></select><small id="vpnProviderHelp"></small><small id="vpnProviderState"></small></label>
          <fieldset class="setup-fieldset" id="setupStorageOptions"><legend>Library storage</legend><div class="storage-options"><label class="storage-option"><input type="radio" name="setupStorageMode" value="local"> Umbrel storage</label><label class="storage-option"><input type="radio" name="setupStorageMode" value="network"> Linked network storage</label><label class="storage-option"><input type="radio" name="setupStorageMode" value="adopt"> Adopt existing roots</label></div></fieldset>
          <div id="setupRootSelections" hidden></div>
          <div class="credential-fields" id="qbittorrentCredentials" hidden><label><span>qBittorrent username</span><input id="qbittorrentUsername" value="admin" autocomplete="username"></label><label><span>One-time qBittorrent password</span><input id="qbittorrentTemporaryPassword" type="password" autocomplete="current-password" aria-describedby="qbittorrentPasswordHelp"><small id="qbittorrentPasswordHelp">Only needed when qBittorrent reports a temporary-password action. It stays in memory and is never saved.</small></label></div>
        </div>
        <div class="setup-actions"><span class="setup-feedback"><span class="error" id="setupError" role="alert"></span></span><button class="primary" id="confirmSetup" type="button" disabled>Connect detected apps</button></div>
      </section>
"""


SERVICES = r"""
      <div class="fleet-toolbar" aria-label="Service filters">
        <input id="serviceSearch" type="search" placeholder="Search managed services" aria-label="Search managed services">
        <select id="serviceStateFilter" aria-label="Filter by service status"><option value="all">All statuses</option><option value="healthy">Healthy</option><option value="action_required">Action required</option><option value="waiting">Waiting</option><option value="configuring">Configuring</option><option value="failed">Failed</option><option value="unknown">Unknown</option></select>
        <span class="fleet-count"><span id="serviceCount">0 services</span> · API-derived health</span>
      </div>
      <section class="service-grid" id="serviceGrid" aria-label="Managed services" aria-live="polite"><div class="empty service-grid-empty">Loading managed service health.</div></section>
"""


SERVICE_DETAIL = r"""
      <div id="serviceDetail" data-service-id="%%SERVICE_ID%%">
        <a class="back-link" href="/services">← All services</a>
        <section class="service-hero" id="serviceHero" aria-labelledby="serviceDetailName">
          <div class="service-hero-main"><span class="service-icon" id="serviceDetailGlyph" aria-hidden="true">—</span><div><div class="service-hero-title"><h2 id="serviceDetailName">Loading service</h2><span class="status unknown" id="serviceDetailStatus"><span class="status-dot"></span>Unknown</span></div><p id="serviceDetailCopy">Loading current managed state.</p></div></div>
          <a class="service-open" id="serviceOpen" href="#" target="_blank" rel="noreferrer" hidden>Open app ↗</a>
        </section>
        <div class="scope-bar"><span class="scope"><span class="scope-tag">API only</span><span>Health and managed state come from the installed app</span></span></div>
        <div class="service-detail-grid">
          <section class="panel" aria-labelledby="relationshipsTitle"><div class="panel-head"><div><h2 id="relationshipsTitle">Reconciliation</h2><p>Prerequisites and current blockers.</p></div></div><div class="panel-body"><dl class="description-list"><dt>Depends on</dt><dd id="detailDependencies"><span class="detail">Loading dependencies.</span></dd><dt>Waiting on</dt><dd id="detailWaitingOn"><span class="detail">Checking blockers.</span></dd></dl></div></section>
        </div>
      </div>
"""


DEPENDENCIES_VIEW = r"""
      <section class="panel" aria-labelledby="dependencyGraphTitle">
        <div class="panel-head"><div><h2 id="dependencyGraphTitle">Reconciliation dependency graph</h2><p>Arrows point from each prerequisite to the app that consumes it.</p></div><div class="dependency-legend"><span class="legend-item"><span class="legend-line"></span>Ready path</span><span class="legend-item"><span class="legend-line blocked"></span>Blocked path</span><span class="scope-tag" id="blockedCount">Checking</span></div></div>
        <p class="sr-only" id="dependencyGraphDescription">Checking reconciliation dependencies.</p>
        <div class="graph-scroll" tabindex="0" aria-label="Scrollable reconciliation dependency graph"><svg class="dependency-svg" id="dependencyGraph" role="img" aria-labelledby="dependencyGraphTitle dependencyGraphDescription"></svg></div>
        <div class="graph-hint">Scroll horizontally when the complete graph does not fit.</div>
      </section>
      <section class="panel" aria-labelledby="blockerListTitle">
        <div class="panel-head"><div><h2 id="blockerListTitle">What each app is waiting on</h2><p>The list is the accessible, detailed view of the graph above.</p></div></div>
        <div class="table-wrap"><table class="dependency-table"><thead><tr><th>App</th><th>Depends on</th><th>Current blocker</th><th>Status</th></tr></thead><tbody id="dependencyRows"></tbody></table></div>
      </section>
"""


STORAGE_HEADER = r"""
      <div class="mode-tabs" aria-label="Configuration level">
        <a class="%%MODE_BASIC%%" href="/libraries?mode=basic" %%MODE_CURRENT_BASIC%%>Basic</a>
        <a class="%%MODE_EXPERT%%" href="/libraries?mode=expert" %%MODE_CURRENT_EXPERT%%>Expert</a>
      </div>
      <p class="mode-note">%%MODE_DESCRIPTION%%</p>
"""


LIBRARY_PROPAGATION = r"""
      <section class="panel" aria-labelledby="propagationTitle">
        <div class="panel-head"><div><h2 id="propagationTitle">Reconcile scope</h2><p>What every reconciliation manages using the saved library layout.</p></div></div>
        <dl class="propagation-list">
          <div class="propagation-step"><dt>Root folders</dt><dd>Creates roots only for the selected Sonarr, Radarr, and Lidarr modules without removing existing roots.</dd></div>
          <div class="propagation-step"><dt>Download categories</dt><dd>Configures matching categories in the selected download clients, then links those clients to the selected media managers.</dd></div>
          <div class="propagation-step"><dt>Connected apps</dt><dd>Synchronizes selected media managers into Prowlarr and connects only the enabled Bazarr, Profilarr, and Overseerr integrations.</dd></div>
        </dl>
      </section>
"""


STORAGE_BASIC = STORAGE_HEADER + r"""
      <section class="panel" aria-labelledby="storageTitle">
        <div class="panel-head">
          <div><h2 id="storageTitle">Library layout</h2><p id="storageScope">Libraries on Umbrel /downloads</p></div>
          <div class="segmented" role="radiogroup" aria-label="Library location">
            <input type="radio" id="modeLocal" name="storageMode" value="local" checked><label for="modeLocal">Umbrel storage</label>
            <input type="radio" id="modeNetwork" name="storageMode" value="network"><label for="modeNetwork">Network storage</label>
            <input type="radio" id="modeAdopt" name="storageMode" value="adopt"><label for="modeAdopt">Existing roots</label>
          </div>
        </div>
        <form class="panel-body" id="storageForm" data-level="basic">
          <div id="storageRootSelections" hidden></div>
          <div class="library-list" id="libraryPlan" aria-live="polite"><div class="empty">Loading the shared library plan.</div></div>
          <div class="panel-actions"><span class="library-feedback"><span class="error" id="storageError" role="alert"></span><span class="success" id="storageResult" role="status"></span></span><button class="primary" id="saveLibraries" type="submit">Save library layout</button></div>
        </form>
      </section>
""" + LIBRARY_PROPAGATION


STORAGE_EXPERT = STORAGE_BASIC.replace('data-level="basic"', 'data-level="expert"')


ACTIVITY = r"""
      <section class="panel">
        <div class="panel-head"><div><h2>Reconciliation activity</h2><p>Credential-safe events from managed configuration runs.</p></div></div>
        <div class="activity-list full" id="events"><div class="empty">No reconciliation activity yet.</div></div>
      </section>
"""


PAGE_META = {
    "overview": ("System", "Current stack state and required setup actions", OVERVIEW),
    "setup": ("Setup", "Detect and explicitly connect the apps you installed", SETUP),
    "services": ("Services", "API health and status for every managed app", SERVICES),
    "dependencies": ("Dependencies", "Reconciliation order and current upstream blockers", DEPENDENCIES_VIEW),
    "libraries": ("Libraries", "Define media locations once and reconcile them across the managed apps", STORAGE_BASIC),
    "activity": ("Activity", "Reconciliation history for this managed stack", ACTIVITY),
}


SERVICE_TITLES = {
    "privado-vpn": "Privado VPN", "flaresolverr": "FlareSolverr", "prowlarr": "Prowlarr",
    "qbittorrent": "qBittorrent", "sabnzbd": "SABnzbd", "sonarr": "Sonarr",
    "sonarr-4k": "Sonarr 4K", "radarr": "Radarr", "radarr-4k": "Radarr 4K",
    "bazarr": "Bazarr", "overseerr": "Overseerr", "profilarr": "Profilarr",
    "umbrelarr": "umbrelarr", "lidarr": "Lidarr",
}


def render_page(page="overview", mode="basic", service_id=None):
    if page == "service":
        if service_id not in SERVICE_TITLES:
            raise ValueError(f"Unknown managed service: {service_id}")
        title = SERVICE_TITLES[service_id]
        subtitle = "API status, dependencies, and current blockers"
        content = SERVICE_DETAIL.replace("%%SERVICE_ID%%", service_id)
    elif page not in PAGE_META:
        raise ValueError(f"Unknown dashboard page: {page}")
    else:
        title, subtitle, content = PAGE_META[page]
    if page == "libraries":
        mode = "expert" if mode == "expert" else "basic"
        content = STORAGE_EXPERT if mode == "expert" else STORAGE_BASIC
        content = content.replace("%%MODE_BASIC%%", "active" if mode == "basic" else "")
        content = content.replace("%%MODE_EXPERT%%", "active" if mode == "expert" else "")
        content = content.replace("%%MODE_CURRENT_BASIC%%", 'aria-current="page"' if mode == "basic" else "")
        content = content.replace("%%MODE_CURRENT_EXPERT%%", 'aria-current="page"' if mode == "expert" else "")
        description = (
            "Expert mode can adopt one existing API-reported root ID per library. Arbitrary paths are not accepted."
            if mode == "expert"
            else "Basic mode applies a complete, safe five-library layout from one storage choice."
        )
        content = content.replace("%%MODE_DESCRIPTION%%", description)
    scope_copy = SERVICE_TITLES[service_id] if page == "service" else "All managed services"
    result = TEMPLATE.replace("%%PAGE_TITLE%%", title).replace("%%PAGE_SUBTITLE%%", subtitle).replace("%%SCOPE_COPY%%", scope_copy).replace("%%CONTENT%%", content)
    for destination in ("overview", "setup", "services", "dependencies", "libraries", "activity"):
        active = destination == page or (destination == "services" and page == "service")
        result = result.replace(f"%%NAV_{destination.upper()}%%", "active" if active else "")
        result = result.replace(f"%%CURRENT_{destination.upper()}%%", 'aria-current="page"' if active else "")
    return result


PAGE = render_page()
