from storage import LIBRARY_DEFINITIONS


LIBRARIES_BY_ID = {
    definition["id"]: {"key": key, **definition}
    for key, definition in LIBRARY_DEFINITIONS.items()
}
LIBRARY_TITLES = {
    library_id: f"{definition['name']} {definition['variant']}"
    for library_id, definition in LIBRARIES_BY_ID.items()
}


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>umbrelarr</title>
  <link rel="icon" href="/icon.png" type="image/png">
  <style>
    :root {
      color-scheme: dark;
      --sidebar: #070b10;
      --sidebar-hover: #111922;
      --sidebar-active: #14221c;
      --canvas: #0a0f15;
      --surface: #121922;
      --surface-raised: #17212c;
      --surface-muted: #0e151d;
      --surface-hover: #1b2632;
      --input: #0c131b;
      --line: #24303d;
      --line-strong: #344355;
      --text: #edf3f8;
      --muted: #95a2b2;
      --subtle: #697789;
      --primary: #50d890;
      --primary-dark: #32b970;
      --primary-soft: #102a1d;
      --blue: #66b8e6;
      --blue-dark: #8dcef2;
      --blue-soft: #102632;
      --green: #50d890;
      --green-soft: #102a1d;
      --amber: #f1b957;
      --amber-soft: #2c220f;
      --red: #ef747b;
      --red-soft: #30171b;
      --slate: #7e8a99;
      --slate-soft: #1b2430;
      --shadow: 0 1px 2px rgba(0, 0, 0, .28), 0 12px 32px rgba(0, 0, 0, .18);
      --shadow-hover: 0 1px 2px rgba(0, 0, 0, .32), 0 16px 36px rgba(0, 0, 0, .24);
      --sidebar-width: 220px;
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
    input, select { accent-color: var(--primary); }
    select {
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      padding: 8px 34px 8px 11px;
      background-color: var(--input);
      color: var(--text);
      transition: border-color .16s ease, box-shadow .16s ease;
    }
    select:hover { border-color: #4b5c70; }
    select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(80, 216, 144, .13); }
    input::placeholder { color: #697789; opacity: 1; }
    button {
      min-height: 38px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      background: var(--surface);
      color: var(--text);
      padding: 8px 14px;
      cursor: pointer;
      font-weight: 650;
      box-shadow: 0 1px 2px rgba(0, 0, 0, .22);
      transition: background .16s ease, border-color .16s ease, box-shadow .16s ease;
    }
    button:hover { background: var(--surface-hover); border-color: #4a5b70; box-shadow: 0 4px 12px rgba(0, 0, 0, .24); }
    button.primary { border-color: #62e49c; background: var(--primary); color: #07140d; }
    button.primary:hover { border-color: #78eaaa; background: #62e29c; }
    button.danger { border-color: #7a3d43; background: #3a1c21; color: #ff9da3; }
    button.danger:hover { border-color: #a6535b; background: #4a2329; }
    button:disabled { cursor: not-allowed; opacity: .55; }
    button:disabled:hover { box-shadow: none; }
    a.runtime-action {
      min-height: 38px;
      border: 1px solid #62e49c;
      border-radius: 9px;
      padding: 8px 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--primary);
      color: #07140d;
      font-weight: 700;
      box-shadow: 0 1px 2px rgba(0, 0, 0, .22);
      transition: background .16s ease, border-color .16s ease, box-shadow .16s ease;
    }
    a.runtime-action:hover { border-color: #78eaaa; background: #62e29c; text-decoration: none; box-shadow: 0 4px 12px rgba(0, 0, 0, .24); }
    button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible { outline: 3px solid rgba(80, 216, 144, .34); outline-offset: 2px; }
    a { color: var(--blue-dark); text-decoration: none; }
    a:hover { text-decoration: underline; }

    .app-shell { min-height: 100vh; }
    .sidebar {
      position: fixed;
      inset: 0 auto 0 0;
      z-index: 10;
      width: var(--sidebar-width);
      background: var(--sidebar);
      color: #d3dce6;
      border-right: 1px solid #1b2530;
      box-shadow: 14px 0 34px rgba(0, 0, 0, .18);
      display: flex;
      flex-direction: column;
    }
    .brand {
      height: 72px;
      padding: 0 17px;
      display: flex;
      align-items: center;
      gap: 11px;
      border-bottom: 1px solid rgba(255,255,255,.075);
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
    .brand-name { font-size: 18px; font-weight: 730; color: var(--text); letter-spacing: -.4px; }
    .brand-name span { color: var(--primary); }
    .nav { padding: 16px 10px; display: grid; gap: 4px; }
    .nav a {
      min-height: 44px;
      padding: 0 12px;
      display: flex;
      align-items: center;
      gap: 12px;
      position: relative;
      color: #8f9baa;
      border: 1px solid transparent;
      border-radius: 12px;
      font-weight: 550;
      transition: background .16s ease, border-color .16s ease, color .16s ease;
    }
    .nav a:hover { background: var(--sidebar-hover); color: #e6edf4; text-decoration: none; }
    .nav a.active {
      background: var(--sidebar-active);
      color: #f2f8f5;
      border-color: #214735;
      border-radius: 11px;
      box-shadow: inset 0 0 0 1px rgba(80, 216, 144, .04), 0 4px 14px rgba(0, 0, 0, .18);
    }
    .nav a.active::before { content: ""; position: absolute; inset: 9px auto 9px -7px; width: 3px; border-radius: 0 999px 999px 0; background: var(--primary); box-shadow: 0 0 14px rgba(80, 216, 144, .45); }
    .nav-icon { width: 18px; height: 18px; display: grid; place-items: center; color: #647284; }
    .nav-icon svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
    .nav a.active .nav-icon { color: var(--primary); }
    .nav-badge { margin-left: auto; min-width: 21px; padding: 2px 6px; border: 1px solid #334152; border-radius: 999px; background: #18222d; color: #bdc8d4; text-align: center; font-size: 11px; }
    .content { min-height: 100vh; margin-left: var(--sidebar-width); }
    .topbar {
      height: 72px;
      position: sticky;
      top: 0;
      z-index: 8;
      padding: 0 28px;
      background: rgba(10, 15, 21, .88);
      backdrop-filter: blur(18px) saturate(120%);
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
    .summary-status { padding: 20px 22px; display: flex; align-items: center; gap: 14px; background: var(--surface-raised); }
    .status-orb { width: 12px; height: 12px; flex: 0 0 auto; border-radius: 50%; background: var(--slate); box-shadow: 0 0 0 5px var(--slate-soft); }
    .status-orb.healthy { background: var(--green); box-shadow: 0 0 0 5px var(--green-soft); }
    .status-orb.action_required { background: var(--amber); box-shadow: 0 0 0 5px var(--amber-soft); }
    .status-orb.failed { background: var(--red); box-shadow: 0 0 0 5px var(--red-soft); }
    .status-orb.waiting, .status-orb.configuring { background: var(--blue); box-shadow: 0 0 0 5px var(--blue-soft); }
    .summary-status h2 { margin: 0; font-size: 17px; font-weight: 700; letter-spacing: -.2px; }
    .summary-status p { margin: 2px 0 0; color: var(--muted); font-size: 12px; }
    .metric { padding: 16px; border-left: 1px solid var(--line); display: flex; flex-direction: column; justify-content: center; background: var(--surface); }
    .metric strong { font-size: 23px; line-height: 1.1; font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -.4px; }
    .metric span { margin-top: 3px; color: var(--muted); font-size: 11px; }

    .notice { margin-bottom: 18px; border: 1px solid #5b4720; border-left: 4px solid var(--amber); border-radius: 12px; background: #211b11; box-shadow: var(--shadow); overflow: hidden; }
    .notice-head { padding: 14px 17px; border-bottom: 1px solid #4c3b1d; display: flex; align-items: center; gap: 11px; }
    .notice-symbol { color: var(--amber); font-size: 17px; }
    .notice h2 { margin: 0; font-size: 14px; font-weight: 700; }
    .notice p { margin: 2px 0 0; color: #c8b78f; font-size: 12px; }
    .vpn-form { padding: 16px 17px; display: grid; grid-template-columns: minmax(180px, 1fr) minmax(180px, 1fr) auto; gap: 12px; align-items: end; }
    .notice > .error { margin: -5px 17px 14px; }

    .panel { margin-bottom: 18px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow); overflow: hidden; }
    .panel:hover { box-shadow: var(--shadow); }
    .panel-head { min-height: 58px; padding: 13px 17px; border-bottom: 1px solid var(--line); background: var(--surface-raised); display: flex; align-items: center; justify-content: space-between; gap: 16px; }
    .panel-head h2 { margin: 0; font-size: 15px; font-weight: 700; letter-spacing: -.15px; }
    .panel-head p { margin: 2px 0 0; color: var(--muted); font-size: 11px; }
    .panel-body { padding: 18px; }
    label span { display: block; margin-bottom: 6px; color: #b2bdc9; font-size: 11px; font-weight: 700; }
    input {
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 9px;
      padding: 8px 11px;
      background: var(--input);
      color: var(--text);
      box-shadow: inset 0 1px 2px rgba(0, 0, 0, .24);
      transition: border-color .16s ease, box-shadow .16s ease;
    }
    input:hover { border-color: #4b5c70; }
    input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(80, 216, 144, .13); }
    .segmented { display: inline-flex; padding: 3px; border: 1px solid var(--line); border-radius: 9px; overflow: hidden; background: var(--input); }
    .segmented input { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); opacity: 0; }
    .segmented label { min-height: 32px; padding: 6px 11px; border-radius: 8px; color: var(--muted); cursor: pointer; font-size: 12px; font-weight: 650; }
    .segmented input:checked + label { background: var(--surface-raised); color: var(--text); box-shadow: 0 1px 3px rgba(0, 0, 0, .28); }
    .segmented input:focus-visible + label { outline: 3px solid rgba(80,216,144,.34); outline-offset: -2px; }
    .path-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; }
    .panel-actions { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .error { min-height: 18px; color: #ff9298; font-size: 12px; }
    .error:not(:empty) { padding: 8px 10px; border: 1px solid #6b3035; border-radius: 8px; background: var(--red-soft); }
    .library-overview { margin-bottom: 16px; padding: 17px 18px; border: 1px solid var(--line); border-radius: 12px; background: linear-gradient(135deg, #15211d, var(--surface)); box-shadow: var(--shadow); display: flex; align-items: center; justify-content: space-between; gap: 18px; }
    .library-overview h2 { margin: 0; font-size: 16px; }
    .library-overview p { max-width: 680px; margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .library-count { flex: 0 0 auto; padding: 6px 10px; border: 1px solid #285a40; border-radius: 999px; background: var(--primary-soft); color: #8be7b4; font-size: 11px; font-weight: 750; }
    .library-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 14px; }
    .library-card { min-width: 0; min-height: 260px; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; background: var(--surface); box-shadow: var(--shadow); display: flex; flex-direction: column; color: var(--text); transition: transform .16s ease, border-color .16s ease, box-shadow .16s ease; }
    .library-card:hover { border-color: #3b5949; box-shadow: var(--shadow-hover); transform: translateY(-2px); text-decoration: none; }
    .library-card-head { padding: 17px 17px 12px; display: flex; align-items: center; gap: 13px; }
    .library-icon { width: 58px; height: 58px; position: relative; flex: 0 0 auto; border: 1px solid #285a40; border-radius: 15px; background: linear-gradient(145deg, #183827, #10251b); color: #76e5aa; box-shadow: inset 0 1px 0 rgba(255,255,255,.06), 0 8px 20px rgba(0,0,0,.22); display: grid; place-items: center; }
    .library-icon.movies { border-color: #31546a; background: linear-gradient(145deg, #183143, #10222e); color: #8dcef2; }
    .library-icon.music { border-color: #5a4770; background: linear-gradient(145deg, #302241, #21172e); color: #c29af1; }
    .library-icon svg { width: 31px; height: 31px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.7; }
    .library-icon-badge { position: absolute; right: -5px; bottom: -5px; min-width: 25px; padding: 3px 5px; border: 2px solid var(--surface); border-radius: 7px; background: var(--primary); color: #07140d; font-size: 8px; font-weight: 900; letter-spacing: .2px; text-align: center; }
    .library-card-title { min-width: 0; }
    .library-card-title strong { display: block; font-size: 16px; letter-spacing: -.2px; }
    .library-card-title small { display: block; margin-top: 3px; color: var(--muted); font-size: 11px; }
    .library-card-body { padding: 0 17px 15px; display: flex; flex: 1; flex-direction: column; }
    .library-root { min-width: 0; padding: 10px 11px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface-muted); }
    .library-root span { display: block; margin-bottom: 4px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .45px; text-transform: uppercase; }
    .library-root code { display: block; overflow: hidden; color: #d6e0e8; font: 11px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
    .library-card-meta { margin: 12px 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .library-card-meta div { min-width: 0; }
    .library-card-meta dt { color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .4px; text-transform: uppercase; }
    .library-card-meta dd { margin: 3px 0 0; overflow: hidden; font-size: 11px; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
    .library-apps { display: flex; flex-wrap: wrap; gap: 5px; }
    .library-app { min-height: 25px; padding: 3px 7px; border: 1px solid var(--line); border-radius: 999px; display: inline-flex; align-items: center; gap: 5px; background: var(--surface-muted); color: #aab6c3; font-size: 10px; font-weight: 650; }
    .library-app .status-dot { width: 6px; height: 6px; }
    .library-app.healthy .status-dot { background: var(--green); }
    .library-app.failed .status-dot { background: var(--red); }
    .library-app.action_required .status-dot { background: var(--amber); }
    .library-app.waiting .status-dot, .library-app.configuring .status-dot { background: var(--blue); }
    .library-card-foot { min-height: 43px; margin-top: auto; padding: 10px 17px; border-top: 1px solid var(--line); background: var(--surface-muted); display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 10px; }
    .library-card-foot strong { color: var(--blue-dark); font-size: 11px; }
    .library-detail-hero { margin-bottom: 14px; padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(135deg, #15231d, var(--surface)); box-shadow: var(--shadow); display: flex; align-items: center; justify-content: space-between; gap: 18px; }
    .library-detail-main { min-width: 0; display: flex; align-items: center; gap: 15px; }
    .library-detail-main .library-icon { width: 70px; height: 70px; border-radius: 17px; }
    .library-detail-main .library-icon svg { width: 37px; height: 37px; }
    .library-detail-title { min-width: 0; }
    .library-detail-title h2 { margin: 0; font-size: 21px; letter-spacing: -.3px; }
    .library-detail-title p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }
    .library-detail-root { min-width: 0; max-width: 380px; text-align: right; }
    .library-detail-root span { display: block; margin-bottom: 4px; color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .45px; text-transform: uppercase; }
    .library-detail-root code { display: block; overflow: hidden; color: #d6e0e8; font: 11px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; text-overflow: ellipsis; white-space: nowrap; }
    .library-detail-layout { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(300px, .75fr); gap: 14px; align-items: start; }
    .library-source-fieldset { margin: 0; padding: 0; border: 0; }
    .library-source-fieldset legend { margin-bottom: 10px; color: #b2bdc9; font-size: 11px; font-weight: 700; }
    .library-source-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
    .library-source-option { min-width: 0; min-height: 92px; padding: 12px; border: 1px solid var(--line); border-radius: 11px; background: var(--surface-muted); cursor: pointer; transition: border-color .16s ease, background .16s ease; }
    .library-source-option:hover { border-color: #405166; background: var(--surface-hover); }
    .library-source-option:has(input:checked) { border-color: #3b8a60; background: var(--primary-soft); box-shadow: inset 0 0 0 1px rgba(80,216,144,.1); }
    .library-source-option:has(input:disabled) { cursor: not-allowed; opacity: .48; }
    .library-source-option input { width: 16px; min-height: 16px; margin: 0 0 9px; box-shadow: none; }
    .library-source-option strong, .library-source-option small { display: block; }
    .library-source-option strong { font-size: 12px; }
    .library-source-option small { margin-top: 3px; color: var(--muted); font-size: 10px; font-weight: 450; }
    .filesystem-browser { margin-top: 14px; border: 1px solid var(--line); border-radius: 11px; overflow: hidden; background: var(--input); }
    .filesystem-browser-head { min-height: 48px; padding: 9px 11px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .filesystem-browser-title { min-width: 0; }
    .filesystem-browser-title strong, .filesystem-browser-title small { display: block; }
    .filesystem-browser-title strong { font-size: 12px; }
    .filesystem-browser-title small { margin-top: 2px; color: var(--muted); font-size: 9px; }
    .filesystem-browser-actions { display: flex; gap: 6px; }
    button.filesystem-browser-action { width: 32px; min-height: 32px; padding: 0; display: grid; place-items: center; box-shadow: none; }
    .filesystem-browser-action svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
    .filesystem-breadcrumbs { min-height: 39px; padding: 5px 8px; border-top: 1px solid var(--line); display: flex; align-items: center; gap: 2px; overflow-x: auto; scrollbar-width: thin; }
    button.filesystem-crumb { min-height: 28px; padding: 4px 7px; border-color: transparent; background: transparent; box-shadow: none; color: #b9c6d2; font: 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; white-space: nowrap; }
    button.filesystem-crumb:hover { border-color: var(--line); background: var(--surface-hover); box-shadow: none; }
    .filesystem-separator { color: #536173; font-size: 10px; }
    .filesystem-list { min-height: 168px; max-height: 292px; border-top: 1px solid var(--line); overflow-y: auto; }
    button.filesystem-row { width: 100%; min-height: 44px; padding: 8px 11px; border: 0; border-top: 1px solid var(--line); border-radius: 0; background: var(--surface-muted); box-shadow: none; display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; align-items: center; gap: 9px; text-align: left; }
    button.filesystem-row:first-child { border-top: 0; }
    button.filesystem-row:hover { border-color: var(--line); background: var(--surface-hover); box-shadow: none; }
    .filesystem-folder-icon { width: 28px; height: 28px; border: 1px solid #31546a; border-radius: 7px; background: var(--blue-soft); color: var(--blue-dark); display: grid; place-items: center; }
    .filesystem-folder-icon svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
    .filesystem-row-copy { min-width: 0; }
    .filesystem-row-copy strong, .filesystem-row-copy code { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .filesystem-row-copy strong { font-size: 11px; }
    .filesystem-row-copy code { margin-top: 1px; color: var(--muted); font: 8px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .filesystem-row-arrow { color: #627184; }
    .filesystem-message { min-height: 168px; padding: 24px 16px; display: grid; place-items: center; color: var(--muted); font-size: 11px; text-align: center; }
    .filesystem-message.error { margin: 0; border: 0; border-radius: 0; background: var(--red-soft); color: #ff9aa0; }
    .filesystem-browser-foot { min-height: 43px; padding: 8px 11px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--surface-muted); }
    .filesystem-browser-foot span { color: var(--muted); font-size: 9px; }
    .filesystem-browser-foot code { min-width: 0; overflow-wrap: anywhere; color: #d6e0e8; font: 9px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: right; }
    .filesystem-mount-check { padding: 10px 11px; border-top: 1px solid var(--line); background: var(--surface); }
    .filesystem-mount-check > strong { display: block; margin-bottom: 7px; color: #b8c4d0; font-size: 9px; letter-spacing: .35px; text-transform: uppercase; }
    .filesystem-mounts { display: flex; flex-wrap: wrap; gap: 6px; }
    .mount-chip { min-height: 24px; padding: 4px 7px; border: 1px solid var(--line); border-radius: 999px; display: inline-flex; align-items: center; gap: 5px; color: var(--muted); font-size: 9px; font-weight: 700; }
    .mount-chip .status-dot { width: 6px; height: 6px; }
    .mount-chip.match { border-color: #285a40; background: var(--green-soft); color: #7ee2ac; }
    .mount-chip.match .status-dot { background: #50d890; }
    .mount-chip.missing { border-color: #763b40; background: var(--red-soft); color: #ff9aa0; }
    .mount-chip.missing .status-dot { background: #f16c75; }
    .mount-chip.unavailable { border-color: #71582d; background: var(--amber-soft); color: #f5c56d; }
    .mount-chip.unavailable .status-dot { background: #e7aa3d; }
    .filesystem-mount-summary { margin-top: 7px; color: var(--muted); font-size: 9px; }
    .filesystem-mount-summary.success { min-height: 0; padding: 0; border: 0; background: transparent; color: #7ee2ac; }
    .filesystem-mount-summary.error { margin: 7px 0 0; padding: 0; border: 0; background: transparent; color: #ff9aa0; }
    .library-config-list { margin: 0; }
    .library-config-list div { padding: 12px 0; border-top: 1px solid var(--line); }
    .library-config-list div:first-child { padding-top: 0; border-top: 0; }
    .library-config-list dt { color: var(--muted); font-size: 10px; }
    .library-config-list dd { margin: 4px 0 0; font-size: 12px; overflow-wrap: anywhere; }
    .library-config-list code { font: 10px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .library-feedback { margin-right: auto; }
    .success { min-height: 18px; color: #7ee2ac; font-size: 12px; }
    .success:not(:empty) { display: block; padding: 8px 10px; border: 1px solid #285a40; border-radius: 8px; background: var(--green-soft); }
    .attention-list { display: grid; }
    .attention-item { padding: 14px 17px; border-top: 1px solid var(--line); display: grid; grid-template-columns: minmax(160px, 1fr) minmax(240px, 2fr) auto; align-items: center; gap: 14px; transition: background .15s ease; }
    .attention-item:first-child { border-top: 0; }
    .attention-item:hover { background: var(--surface-hover); }
    .attention-name { font-weight: 700; }
    .activity-list.full { max-height: none; }
    body.modal-open { overflow: hidden; }
    dialog.service-setup-dialog {
      width: min(760px, calc(100vw - 32px));
      max-width: none;
      max-height: min(760px, calc(100dvh - 32px));
      margin: auto;
      padding: 0;
      border: 1px solid var(--line-strong);
      border-radius: 16px;
      overflow: hidden;
      background: var(--surface);
      color: var(--text);
      box-shadow: 0 28px 90px rgba(0, 0, 0, .58);
    }
    dialog.service-setup-dialog:not([open]) { display: none; }
    dialog.service-setup-dialog::backdrop { background: rgba(2, 6, 10, .74); backdrop-filter: blur(5px); }
    .service-setup-shell { max-height: min(760px, calc(100dvh - 32px)); display: flex; flex-direction: column; }
    .setup-dialog-head { padding: 18px 20px 16px; border-bottom: 1px solid var(--line); display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; background: var(--surface-raised); }
    .setup-dialog-kicker { display: block; margin-bottom: 5px; color: var(--primary); font-size: 9px; font-weight: 800; letter-spacing: .9px; text-transform: uppercase; }
    .setup-dialog-head h2 { margin: 0; font-size: 18px; letter-spacing: -.25px; }
    .setup-dialog-head p { max-width: 600px; margin: 5px 0 0; color: var(--muted); font-size: 11px; }
    button.setup-dialog-close { min-width: 38px; width: 38px; padding: 0; border-radius: 999px; color: var(--muted); font-size: 20px; line-height: 1; }
    .setup-steps { padding: 10px 20px; border-bottom: 1px solid var(--line); display: flex; align-items: center; gap: 8px; background: var(--surface-muted); }
    .setup-step { display: inline-flex; align-items: center; gap: 7px; color: var(--subtle); font-size: 10px; font-weight: 750; }
    .setup-step + .setup-step::before { content: ""; width: 26px; height: 1px; margin-right: 1px; background: var(--line-strong); }
    .setup-step b { width: 21px; height: 21px; border: 1px solid var(--line-strong); border-radius: 50%; display: grid; place-items: center; background: var(--surface); font-size: 9px; }
    .setup-step.active { color: #dce6ee; }
    .setup-step.active b { border-color: #3b8f61; background: var(--primary-soft); color: var(--primary); }
    .setup-step.complete { color: #8f9cab; }
    .setup-step.complete b { border-color: #285a40; color: #7ee2ac; }
    .setup-dialog-body { min-height: 280px; padding: 18px 20px 20px; overflow: auto; }
    .setup-dialog-section[hidden] { display: none; }
    .setup-app-list { margin-top: 16px; border: 1px solid var(--line); border-radius: 11px; overflow: hidden; background: var(--surface-muted); }
    .setup-app-list .attention-item { grid-template-columns: minmax(130px, .8fr) minmax(220px, 1.8fr) auto; }
    .catalog-head h3, .module-type-head h4 { margin: 0; }
    .catalog-head h3 { font-size: 13px; }
    .catalog-head p { margin: 4px 0 0; color: var(--muted); font-size: 11px; }
    .catalog-head { margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; gap: 14px; }
    .module-grid.module-store { margin: 0; display: grid; gap: 18px; }
    .module-type-group { display: grid; gap: 8px; }
    .module-type-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
    .module-type-head h4 { color: #d8e1e9; font-size: 11px; }
    .module-type-head span { color: var(--muted); font-size: 9px; }
    .module-type-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
    .module-store-item {
      min-height: 82px;
      padding: 12px;
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr) auto;
      align-items: center;
      gap: 11px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: var(--surface-muted);
      transition: border-color .16s ease, background .16s ease, transform .16s ease;
    }
    .module-store-item:hover { border-color: #344354; background: var(--surface-hover); transform: translateY(-1px); }
    .module-store-item[data-selection-state="selected"] { border-color: #3b8f61; background: #10231a; }
    .module-store-item[data-install-state="stopped"], .module-store-item[data-install-state="not-installed"], .module-store-item[data-install-state="unavailable"] { border-color: #3a4048; }
    .module-store-item[data-install-state="stopped"]:hover, .module-store-item[data-install-state="not-installed"]:hover, .module-store-item[data-install-state="unavailable"]:hover { border-color: #3a4048; background: var(--surface-muted); transform: none; }
    .module-store-item .service-icon { width: 44px; height: 44px; border-radius: 10px; }
    .module-store-copy { min-width: 0; }
    .module-store-copy strong, .module-store-copy small, .module-store-state { display: block; }
    .module-store-copy strong { overflow: hidden; color: var(--text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
    .module-store-copy small { margin-top: 2px; overflow: hidden; color: var(--muted); font-size: 10px; text-overflow: ellipsis; text-transform: capitalize; white-space: nowrap; }
    .module-store-state { margin-top: 6px; color: #9ba8b7; font-size: 10px; font-weight: 700; }
    .module-store-item[data-install-state="running"] .module-store-state { color: #7ee2ac; }
    .module-store-item[data-install-state="stopped"] .module-store-state { color: #f3c873; }
    .module-store-item[data-install-state="not-installed"] .module-store-state, .module-store-item[data-install-state="unavailable"] .module-store-state { color: #9aa6b5; }
    button.module-action { min-width: 82px; min-height: 36px; padding: 7px 12px; border-radius: 999px; font-size: 11px; }
    button.module-action.add { border-color: #326d4d; background: #153323; color: #8be7b4; }
    button.module-action.add:hover { border-color: #50d890; background: #19432c; }
    button.module-action.add:disabled { border-color: var(--line-strong); background: #18212b; color: #758395; opacity: 1; }
    .selected-service { padding: 15px; border: 1px solid #285a40; border-radius: 12px; display: grid; grid-template-columns: 48px minmax(0, 1fr); align-items: center; gap: 12px; background: var(--primary-soft); }
    .selected-service .service-icon { width: 48px; height: 48px; border-radius: 11px; }
    .selected-service strong, .selected-service span { display: block; }
    .selected-service strong { font-size: 15px; }
    .selected-service span { margin-top: 3px; color: var(--muted); font-size: 11px; }
    .change-service { margin-bottom: 12px; padding: 0; border: 0; min-height: 28px; background: transparent; box-shadow: none; color: var(--blue-dark); font-size: 11px; }
    .change-service:hover { border: 0; background: transparent; box-shadow: none; text-decoration: underline; }
    .setup-fieldset { margin: 0 0 14px; padding: 0; border: 0; }
    .setup-fieldset > legend { margin-bottom: 8px; font-size: 12px; font-weight: 700; }
    .credential-fields { max-width: 620px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .credential-fields label { display: grid; gap: 5px; }
    .credential-fields label > small { color: var(--muted); font-size: 10px; }
    .direct-connections { margin-top: 16px; padding: 15px 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface-muted); }
    .direct-connections > h3 { margin: 0; font-size: 13px; }
    .direct-connections > p { margin: 4px 0 12px; color: var(--muted); font-size: 11px; }
    .direct-connection-list { display: grid; gap: 12px; }
    .direct-connection-card { padding-top: 12px; border-top: 1px solid var(--line); }
    .direct-connection-card:first-child { padding-top: 0; border-top: 0; }
    .direct-connection-card > strong { display: block; margin-bottom: 8px; font-size: 12px; }
    .direct-connection-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; gap: 10px; }
    .direct-connection-fields label { min-width: 0; display: grid; align-content: start; gap: 5px; }
    .direct-connection-fields small, .direct-connection-note { color: var(--muted); font-size: 10px; }
    .direct-connection-note { display: block; margin-top: 10px; }
    .credential-source { min-width: 0; margin: 0; padding: 0; border: 0; display: grid; gap: 8px; }
    .credential-source legend { margin-bottom: 1px; padding: 0; color: var(--text); font-size: 11px; font-weight: 700; }
    .credential-source-options { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    label.credential-source-option { min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: 9px; display: flex; align-items: flex-start; gap: 8px; background: var(--surface); cursor: pointer; }
    label.credential-source-option:has(input:checked) { border-color: var(--primary); background: var(--primary-soft); box-shadow: inset 0 0 0 1px rgba(75, 214, 143, .14); }
    .credential-source-option input { width: 15px; min-height: 15px; margin: 1px 0 0; accent-color: var(--primary); }
    .credential-source-option span { min-width: 0; display: grid; gap: 2px; }
    .credential-source-option strong { font-size: 11px; }
    .credential-source-option small { line-height: 1.35; }
    .credential-source-panel { min-width: 0; padding: 10px; border: 1px solid var(--line); border-radius: 9px; background: var(--surface); }
    .credential-source-panel[hidden] { display: none; }
    .credential-source-panel label { display: grid; gap: 5px; }
    .credential-source-panel code { display: block; overflow-wrap: anywhere; color: var(--text); font: 600 10px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .credential-source-panel p { margin: 4px 0 0; color: var(--muted); font-size: 10px; line-height: 1.45; }
    .credential-source-panel .configured { color: var(--primary); }
    .credential-automatic { min-width: 0; padding: 11px 12px; border: 1px solid #286d49; border-radius: 9px; display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 9px; align-items: start; background: var(--primary-soft); }
    .credential-automatic-symbol { width: 26px; height: 26px; border: 1px solid #2b8c59; border-radius: 8px; display: grid; place-items: center; color: var(--primary); font-size: 14px; font-weight: 800; }
    .credential-automatic strong, .credential-automatic small { display: block; }
    .credential-automatic strong { font-size: 11px; }
    .credential-automatic small { margin-top: 2px; color: var(--muted); font-size: 10px; line-height: 1.4; }
    .credential-bootstrap { margin-top: 16px; padding: 15px 16px; border: 1px solid #286d49; border-radius: 12px; background: linear-gradient(135deg, rgba(24, 111, 68, .2), rgba(16, 25, 34, .94)); }
    .credential-bootstrap[hidden] { display: none; }
    .credential-bootstrap h3 { margin: 0; font-size: 13px; }
    .credential-bootstrap > p { margin: 4px 0 12px; max-width: 680px; color: var(--muted); font-size: 11px; line-height: 1.5; }
    .credential-bootstrap-form { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; align-items: end; gap: 10px; }
    .credential-bootstrap-form label { min-width: 0; display: grid; gap: 5px; }
    .credential-bootstrap-form label > span { font-size: 11px; font-weight: 700; }
    .credential-bootstrap-form button { min-height: 42px; white-space: nowrap; }
    .credential-bootstrap-note { display: block; margin-top: 9px; color: var(--muted); font-size: 10px; line-height: 1.45; }
    .setup-actions { padding: 14px 17px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; gap: 12px; }
    .setup-feedback { margin-right: auto; }
    .setup-dialog-foot { padding: 14px 20px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; gap: 10px; background: var(--surface-raised); }
    .setup-dialog-feedback { min-width: 0; margin-right: auto; display: grid; gap: 4px; }
    .setup-action-help { max-width: 42ch; color: var(--muted); font-size: 10px; }
    .setup-dialog-feedback .error { margin: 0; }

    .operations { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 18px; align-items: start; }
    .table-wrap { overflow: hidden; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th { padding: 10px 14px; background: var(--surface-muted); color: #8390a0; font-size: 10px; font-weight: 750; letter-spacing: .55px; text-align: left; text-transform: uppercase; }
    td { padding: 11px 14px; border-top: 1px solid var(--line); vertical-align: middle; overflow-wrap: anywhere; }
    tbody tr { transition: background .14s ease; }
    tbody tr:hover { background: var(--surface-hover); }
    tbody tr.failed { background: #211316; }
    tbody tr.action_required { background: #211b11; }
    th:nth-child(1), td:nth-child(1) { width: 25%; }
    th:nth-child(2), td:nth-child(2) { width: 19%; }
    th:nth-child(4), td:nth-child(4) { width: 72px; text-align: right; }
    .service-name { display: flex; align-items: center; gap: 11px; font-weight: 700; }
    .service-icon { width: 30px; height: 30px; flex: 0 0 auto; border: 1px solid #3a4654; border-radius: 8px; display: grid; place-items: center; overflow: hidden; background: #f3f6f8; color: #4b5664; box-shadow: 0 2px 8px rgba(0,0,0,.22); font-size: 9px; font-weight: 800; letter-spacing: -.2px; }
    .service-icon img { width: 100%; height: 100%; display: block; object-fit: cover; }
    .service-icon-fallback { display: grid; width: 100%; height: 100%; place-items: center; background: #e7ebef; }
    tr.healthy .service-icon { border-color: #3f9d68; }
    tr.action_required .service-icon { border-color: #a8782e; }
    tr.failed .service-icon { border-color: #aa4d54; }
    .detail { color: var(--muted); font-size: 12px; }
    .status { display: inline-flex; align-items: center; gap: 7px; padding: 4px 8px; border: 1px solid #2b3745; border-radius: 999px; background: var(--slate-soft); color: #a7b2bf; font-size: 11px; font-weight: 700; white-space: nowrap; }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--slate); }
    .status.healthy .status-dot { background: var(--green); }
    .status.failed .status-dot { background: var(--red); }
    .status.waiting .status-dot, .status.configuring .status-dot { background: var(--blue); }
    .status.action_required .status-dot { background: var(--amber); }
    .status.healthy { border-color: #285a40; background: var(--green-soft); color: #7ee2ac; }
    .status.failed { border-color: #673238; background: var(--red-soft); color: #ff9298; }
    .status.waiting, .status.configuring { border-color: #28536a; background: var(--blue-soft); color: #8ed2f4; }
    .status.action_required { border-color: #5b4720; background: var(--amber-soft); color: #f3c873; }
    .open-link { display: inline-flex; min-height: 28px; align-items: center; padding: 3px 8px; border-radius: 7px; font-size: 12px; font-weight: 700; }
    .open-link:hover { background: var(--surface-hover); text-decoration: none; }

    .activity-list { max-height: 586px; overflow: auto; }
    .event { padding: 12px 14px; border-bottom: 1px solid var(--line); display: grid; grid-template-columns: 58px 1fr; gap: 10px; align-items: center; font-size: 11px; }
    .event:last-child { border-bottom: 0; }
    .event time { padding: 3px 6px; border-radius: 6px; background: var(--surface-muted); color: var(--muted); font-variant-numeric: tabular-nums; text-align: center; }
    .event span { color: #b8c3ce; }
    .empty { padding: 22px 14px; color: var(--muted); text-align: center; font-size: 12px; }

    .fleet-toolbar { margin-bottom: 14px; display: grid; grid-template-columns: minmax(220px, 1fr) 170px auto auto; gap: 10px; align-items: center; }
    .fleet-toolbar input, .fleet-toolbar select { min-height: 38px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 7px 10px; background: var(--input); color: var(--text); }
    .fleet-toolbar select { width: auto; }
    .fleet-count { justify-self: end; color: var(--muted); font-size: 12px; white-space: nowrap; }
    .service-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .service-card { min-width: 0; min-height: 338px; border: 1px solid var(--line); border-radius: 13px; overflow: hidden; background: var(--surface); box-shadow: var(--shadow); color: var(--text); display: flex; flex-direction: column; transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease; }
    .service-card:hover { border-color: #405267; box-shadow: var(--shadow-hover); }
    .service-card-link { min-width: 0; display: flex; flex: 1; flex-direction: column; color: var(--text); }
    .service-card-link:hover { text-decoration: none; }
    .service-card-link:focus-visible { outline-offset: -4px; }
    .service-card.action_required { border-color: #5b4720; }
    .service-card.failed { border-color: #673238; }
    .service-card.healthy .service-icon, .service-hero.healthy .service-icon { border-color: #3f9d68; }
    .service-card.action_required .service-icon, .service-hero.action_required .service-icon { border-color: #a8782e; }
    .service-card.failed .service-icon, .service-hero.failed .service-icon { border-color: #aa4d54; }
    .service-card-head { padding: 16px 16px 12px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
    .service-card-identity { min-width: 0; display: flex; align-items: center; gap: 11px; }
    .service-card-identity .service-icon { width: 46px; height: 46px; border-radius: 11px; font-size: 10px; }
    .service-card-title { min-width: 0; }
    .service-card-title strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 15px; letter-spacing: -.12px; }
    .service-card-title small { display: block; margin-top: 3px; overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; font-size: 10px; font-weight: 650; text-transform: capitalize; }
    .service-card-body { padding: 0 16px 15px; display: flex; flex: 1; flex-direction: column; }
    .service-card-detail { min-height: 36px; margin: 0 0 12px; color: var(--muted); font-size: 12px; }
    .service-resources { margin-top: auto; padding: 10px 11px 11px; border: 1px solid var(--line); border-radius: 9px; overflow: hidden; background: var(--surface-muted); display: block; }
    .service-runtime { margin-bottom: 10px; padding-bottom: 9px; border-bottom: 1px solid var(--line); display: flex; align-items: center; gap: 7px; }
    .runtime-state { min-width: 0; display: inline-flex; align-items: center; gap: 6px; color: #c8d3de; font-size: 10px; font-weight: 750; }
    .runtime-state::before { width: 7px; height: 7px; flex: 0 0 auto; border-radius: 50%; background: var(--slate); content: ""; }
    .runtime-state.running::before { background: var(--green); }
    .runtime-state.stopped { color: #f3c873; }
    .runtime-state.stopped::before { background: var(--amber); }
    .runtime-state.stale::before { opacity: .58; }
    .runtime-meta { min-width: 0; margin-left: auto; overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; font-size: 9px; font-weight: 650; font-variant-numeric: tabular-nums; }
    .runtime-meta.stale { color: #f3c873; }
    .service-resources-head { margin-bottom: 9px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .service-resources-head strong { color: #a7b3c0; font-size: 10px; font-weight: 750; }
    .service-resources-head small { overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; font-size: 9px; font-weight: 650; font-variant-numeric: tabular-nums; }
    .service-resources-head small.stale { color: #f3c873; }
    .resource-gauges { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .resource-gauge { min-width: 0; display: block; }
    .resource-gauge-copy { margin-bottom: 6px; display: flex; align-items: baseline; justify-content: space-between; gap: 5px; }
    .resource-gauge-copy span { overflow: hidden; color: var(--muted); text-overflow: ellipsis; white-space: nowrap; font-size: 8px; font-weight: 750; letter-spacing: .35px; text-transform: uppercase; }
    .resource-gauge-copy strong { color: #d7e0e8; font-size: 9px; font-weight: 750; font-variant-numeric: tabular-nums; }
    .resource-gauge-track { position: relative; height: 6px; overflow: hidden; border-radius: 999px; background: #263241; display: block; }
    .resource-gauge-fill { width: var(--resource-value); height: 100%; border-radius: inherit; background: var(--green); display: block; transition: width .18s ease; }
    .resource-gauge.warning .resource-gauge-fill { background: var(--amber); }
    .resource-gauge.critical .resource-gauge-fill { background: var(--red); }
    .resource-gauge.stale .resource-gauge-fill { opacity: .55; }
    .resource-gauge.unavailable .resource-gauge-track { background: repeating-linear-gradient(135deg, #263241 0 4px, #1e2935 4px 8px); }
    .resource-gauge.unavailable .resource-gauge-copy strong { color: #68778a; }
    .resource-io { margin: 10px 0 0; padding-top: 9px; border-top: 1px solid var(--line); display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .resource-io div { min-width: 0; }
    .resource-io dt { color: var(--muted); font-size: 8px; font-weight: 750; letter-spacing: .35px; text-transform: uppercase; }
    .resource-io dd { margin: 3px 0 0; overflow: hidden; color: #c6d0da; text-overflow: ellipsis; white-space: nowrap; font-size: 9px; font-weight: 650; font-variant-numeric: tabular-nums; }
    .resource-io dd.unavailable { color: #68778a; }
    .service-quick-metrics { margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
    .service-quick-metrics div { min-width: 0; border-left: 1px solid var(--line); padding-left: 9px; }
    .service-quick-metrics div:first-child { border-left: 0; padding-left: 0; }
    .service-quick-metrics dt { color: var(--muted); font-size: 9px; font-weight: 750; letter-spacing: .45px; text-transform: uppercase; }
    .service-quick-metrics dd { margin: 3px 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 650; font-variant-numeric: tabular-nums; }
    .service-card-actions { min-height: 49px; padding: 8px 16px 10px; border-top: 1px solid var(--line); display: flex; align-items: center; justify-content: flex-end; background: var(--surface-muted); }
    button.service-remove { min-height: 30px; padding: 5px 10px; border-color: transparent; background: transparent; color: #d98a90; box-shadow: none; font-size: 10px; }
    button.service-remove:hover { border-color: #673238; background: var(--red-soft); color: #ff9da3; box-shadow: none; }
    button.service-add { min-height: 30px; padding: 5px 11px; border-color: #326d4d; background: #153323; color: #8be7b4; box-shadow: none; font-size: 10px; }
    button.service-add:hover { border-color: #50d890; background: #19432c; box-shadow: none; }
    .service-grid-empty { grid-column: 1 / -1; border: 1px dashed var(--line-strong); border-radius: 10px; background: var(--surface); }

    dialog.service-remove-dialog { width: min(520px, calc(100vw - 32px)); }
    .service-remove-dialog .service-setup-shell { max-height: min(560px, calc(100dvh - 32px)); }
    .service-remove-dialog .setup-dialog-body { min-height: 0; }
    .remove-service-summary { padding: 14px; border: 1px solid var(--line); border-radius: 11px; display: grid; grid-template-columns: 44px minmax(0, 1fr); align-items: center; gap: 11px; background: var(--surface-muted); }
    .remove-service-summary .service-icon { width: 44px; height: 44px; border-radius: 10px; }
    .remove-service-summary strong, .remove-service-summary span { display: block; }
    .remove-service-summary strong { font-size: 14px; }
    .remove-service-summary span { margin-top: 2px; color: var(--muted); font-size: 11px; text-transform: capitalize; }
    .remove-service-copy { margin: 15px 0 0; color: #c3ced8; font-size: 12px; }
    .safe-removal-note { margin-top: 12px; padding: 11px 12px; border: 1px solid #3f4b59; border-radius: 9px; background: #111923; color: var(--muted); font-size: 11px; }
    .safe-removal-note strong { color: #dce5ed; }
    .service-action-status { margin: 0 0 14px; padding: 10px 12px; border: 1px solid #285a40; border-radius: 9px; background: var(--green-soft); color: #9be8bd; font-size: 11px; }
    .inventory-notice { margin: 0 0 14px; padding: 12px 14px; border: 1px solid #394756; border-radius: 10px; display: grid; gap: 3px; background: #121b25; }
    .inventory-notice strong { color: var(--text); font-size: 12px; }
    .inventory-notice span { color: var(--muted); font-size: 11px; line-height: 1.45; }
    .inventory-notice.error { border-color: #6f5523; background: #211c12; }

    .back-link { min-height: 32px; margin-bottom: 12px; display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 650; }
    .service-hero { margin-bottom: 14px; padding: 18px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow); display: flex; align-items: center; justify-content: space-between; gap: 18px; }
    .service-hero-main { min-width: 0; display: flex; align-items: center; gap: 13px; }
    .service-hero .service-icon { width: 44px; height: 44px; font-size: 12px; }
    .service-hero-title { display: flex; align-items: center; flex-wrap: wrap; gap: 9px; }
    .service-hero-title h2 { margin: 0; font-size: 19px; }
    .service-hero p { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
    .service-open { flex: 0 0 auto; min-height: 38px; padding: 8px 14px; border: 1px solid var(--line-strong); border-radius: 8px; display: inline-flex; align-items: center; font-weight: 700; }
    .service-open:hover { background: var(--surface-hover); text-decoration: none; }
    .service-detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .description-list { margin: 0; display: grid; grid-template-columns: 120px minmax(0, 1fr); }
    .description-list dt, .description-list dd { margin: 0; padding: 9px 0; border-top: 1px solid var(--line); }
    .description-list dt:nth-of-type(1), .description-list dt:nth-of-type(1) + dd { border-top: 0; }
    .description-list dt { color: var(--muted); font-size: 11px; }
    .description-list dd { font-size: 12px; overflow-wrap: anywhere; }
    .description-list code { font: 10px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
    .detail-dependencies { display: flex; flex-wrap: wrap; gap: 6px; }
    .detail-dependencies a { min-height: 28px; padding: 4px 8px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface-muted); display: inline-flex; align-items: center; font-size: 11px; font-weight: 650; }
    .detail-dependencies a:hover { border-color: #46586d; text-decoration: none; }

    @media (max-width: 1040px) {
      .summary { grid-template-columns: minmax(260px, 1fr) repeat(4, 92px); }
      .operations { grid-template-columns: 1fr; }
      .activity-list { max-height: 280px; }
      .path-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .library-detail-layout { grid-template-columns: 1fr; }
      .service-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .fleet-toolbar { grid-template-columns: minmax(220px, 1fr) 170px; }
      .fleet-count { justify-self: start; }
    }
    @media (max-width: 760px) {
      :root { --sidebar-width: 68px; }
      .brand { padding: 0 13px; }
      .brand-name, .nav-text, .nav-badge { display: none; }
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
      .nav a { min-width: 54px; min-height: 44px; margin: 0; padding: 0 16px; border: 1px solid transparent; border-radius: 9px; justify-content: center; }
      .nav a.active { border-color: #214735; box-shadow: 0 1px 2px rgba(0, 0, 0, .24); }
      .content { margin-left: 0; }
      .topbar { height: auto; min-height: 62px; position: static; padding: 10px 14px; align-items: flex-start; }
      .page-title p, .live-state, #refresh { display: none; }
      .workspace { padding: 14px; }
      .summary { grid-template-columns: repeat(2, 1fr); }
      .metric:nth-child(4) { border-left: 0; border-top: 1px solid var(--line); }
      .metric:nth-child(5) { border-top: 1px solid var(--line); }
      .vpn-form { grid-template-columns: 1fr; }
      .vpn-form button { grid-column: auto; width: 100%; }
      .panel-head { align-items: flex-start; flex-direction: column; }
      .path-grid { grid-template-columns: 1fr; }
      .library-overview, .library-detail-hero { align-items: flex-start; flex-direction: column; }
      .library-count { align-self: flex-start; }
      .library-detail-root { max-width: 100%; text-align: left; }
      .library-detail-root code { white-space: normal; overflow-wrap: anywhere; }
      .library-source-options { grid-template-columns: 1fr; }
      .library-source-option { min-height: 0; }
      .attention-item { grid-template-columns: 1fr; gap: 5px; }
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
      dialog.service-setup-dialog { width: calc(100vw - 16px); max-height: calc(100dvh - 16px); border-radius: 12px; }
      .service-setup-shell { max-height: calc(100dvh - 16px); }
      .setup-dialog-head { padding: 15px 16px 13px; }
      .setup-dialog-head p { max-width: 35ch; }
      .setup-steps { padding-inline: 16px; }
      .setup-dialog-body { min-height: 0; padding: 15px 16px 18px; }
      .catalog-head { align-items: stretch; flex-direction: column; }
      .catalog-head button { width: 100%; }
      .module-type-grid { grid-template-columns: 1fr; }
      .module-store-item { grid-template-columns: 42px minmax(0, 1fr) auto; }
      .module-store-item .service-icon { width: 42px; height: 42px; }
      .credential-fields { grid-template-columns: 1fr; }
      .direct-connection-fields { grid-template-columns: 1fr; }
      .credential-source-options { grid-template-columns: 1fr; }
      .credential-bootstrap-form { grid-template-columns: 1fr; }
      .setup-actions button { width: 100%; }
      .setup-actions { align-items: stretch; flex-direction: column; }
      .setup-feedback { margin-right: 0; }
      .setup-dialog-foot { padding: 12px 16px; align-items: stretch; flex-direction: column; }
      .setup-dialog-feedback { margin-right: 0; }
      .setup-dialog-foot button { width: 100%; }
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
      <a class="%%NAV_OVERVIEW%%" %%CURRENT_OVERVIEW%% href="/" aria-label="Overview"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 11 12 4l8.5 7v8.5a.5.5 0 0 1-.5.5h-5v-6H9v6H4a.5.5 0 0 1-.5-.5Z"/></svg></span><span class="nav-text">Overview</span><span class="nav-badge" id="navAttention">0</span></a>
      <a class="%%NAV_SERVICES%%" %%CURRENT_SERVICES%% href="/services" aria-label="Services"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="6" rx="2"/><rect x="4" y="14" width="16" height="6" rx="2"/><path d="M8 7h.01M8 17h.01M12 7h5M12 17h5"/></svg></span><span class="nav-text">Services</span></a>
      <a class="%%NAV_LIBRARIES%%" %%CURRENT_LIBRARIES%% href="/libraries" aria-label="Libraries"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3.5 7.5h6l2-2h9v13a1.5 1.5 0 0 1-1.5 1.5H5a1.5 1.5 0 0 1-1.5-1.5Z"/><path d="M3.5 9.5h17"/></svg></span><span class="nav-text">Libraries</span></a>
      <a class="%%NAV_ACTIVITY%%" %%CURRENT_ACTIVITY%% href="/activity" aria-label="Activity"><span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3 12h4l2.3-5 4.2 10 2.4-5H21"/></svg></span><span class="nav-text">Activity</span></a>
    </nav>
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
      %%CONTENT%%
    </main>
  </div>
</div>
<script>
const labels={unknown:'Unknown',waiting:'Waiting',action_required:'Action required',configuring:'Configuring',healthy:'Healthy',failed:'Failed'};
const glyphs={'privado-vpn':'PV',flaresolverr:'FS',prowlarr:'P',qbittorrent:'qB',sabnzbd:'S',sonarr:'S', 'sonarr-4k':'S4',radarr:'R','radarr-4k':'R4',bazarr:'B',overseerr:'O',profilarr:'P',umbrelarr:'ua',lidarr:'L',jellyfin:'J',plex:'Px'};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const element=id=>document.getElementById(id);
const setText=(id,value)=>{const target=element(id);if(target)target.textContent=value;};
let storageState=null;
let statusState=null;
let setupState=null;
let addServiceId=null;
let addServiceStage='choose';
let addServiceBaseIds=[];
let addServiceDraftServerSide=false;
let connectionDrafts={};
let addServiceDeepLinkHandled=false;
let removeServiceId=null;
let removeServiceReturnFocus=null;
function ago(epoch){if(!epoch)return['Not checked yet',true];const seconds=Math.max(0,Math.floor(Date.now()/1000-epoch));if(seconds<10)return['Updated just now',false];if(seconds<60)return[`Updated ${seconds}s ago`,false];const minutes=Math.floor(seconds/60);return[`Updated ${minutes}m ago`,minutes>=3];}
function checkedAgo(epoch){if(!epoch)return'Never';return ago(epoch)[0].replace(/^Updated /,'');}
function serviceMark(service){const fallback=glyphs[service.id]||service.name.slice(0,2);const icon=service.id==='umbrelarr'?'/icon.png':`/service-icons/${encodeURIComponent(service.id)}.svg`;return `<span class="service-icon" aria-hidden="true"><img src="${icon}" alt="" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false"><span class="service-icon-fallback" hidden>${esc(fallback)}</span></span>`;}
const serviceResourceDefinitions=[{key:'cpu',label:'CPU',warning:75,critical:90},{key:'memory',label:'Memory',warning:75,critical:90}];
const resourceStaleAfterSeconds=120;
function resourcePercent(raw){if(typeof raw==='number')return raw;if(!raw||typeof raw!=='object')return null;for(const key of ['percent','usage','value']){const candidate=raw[key];if(candidate===null||candidate===undefined||candidate==='')continue;const value=Number(candidate);if(Number.isFinite(value))return value;}const used=Number(raw.used??raw.usedBytes);const total=Number(raw.total??raw.totalBytes);return Number.isFinite(used)&&Number.isFinite(total)&&total>0?used/total*100:null;}
function telemetryEpoch(raw){if(raw===null||raw===undefined||raw==='')return 0;if(typeof raw==='string'&&!/^\d+(\.\d+)?$/.test(raw)){const parsed=Date.parse(raw);return Number.isFinite(parsed)?parsed/1000:0;}const value=Number(raw);if(!Number.isFinite(value)||value<=0)return 0;return value>1e12?value/1000:value;}
function telemetryAge(raw){const epoch=telemetryEpoch(raw);if(!epoch)return{epoch:0,stale:true,label:'Update time unavailable'};const seconds=Math.max(0,Math.floor(Date.now()/1000-epoch));if(seconds<10)return{epoch,stale:false,label:'just now'};if(seconds<60)return{epoch,stale:false,label:`${seconds}s ago`};const minutes=Math.floor(seconds/60);if(minutes<60)return{epoch,stale:seconds>resourceStaleAfterSeconds,label:`${minutes}m ago`};const hours=Math.floor(minutes/60);return{epoch,stale:true,label:`${hours}h ago`};}
function formatBytes(raw){const value=Number(raw);if(!Number.isFinite(value)||value<0)return null;const units=['B','KB','MB','GB','TB'];let amount=value;let unit=0;while(amount>=1024&&unit<units.length-1){amount/=1024;unit+=1;}const digits=amount>=10||unit===0?0:1;return `${new Intl.NumberFormat(undefined,{maximumFractionDigits:digits}).format(amount)} ${units[unit]}`;}
function runtimeState(service){const container=service.container;if(!container||typeof container!=='object'){return `<span class="service-runtime"><span class="runtime-state unavailable">Unavailable</span><small class="runtime-meta">Docker data unavailable</small></span>`;}const rawState=String(container.state||'').toLowerCase();const running=rawState==='running';const known=Boolean(rawState)&&!['unknown','unavailable'].includes(rawState);const state=running?'running':known?'stopped':'unavailable';const label=running?'Running':known?'Stopped':'Unavailable';const age=telemetryAge(container.updatedAt);const health=String(container.health||'').toLowerCase();const healthCopy=['healthy','unhealthy','starting'].includes(health)?` · ${health}`:'';const source=state==='unavailable'?'Docker state unavailable':`Docker${healthCopy} · ${age.label}`;const staleClass=age.stale?' stale':'';const stateCopy=age.stale?`Last reported ${label.toLowerCase()}`:label;const name=container.name?` container ${container.name}`:'';return `<span class="service-runtime" aria-label="${esc(stateCopy)}${esc(name)}. ${esc(source)}"><span class="runtime-state ${state}${staleClass}">${esc(label)}</span><small class="runtime-meta${staleClass}">${esc(source)}</small></span>`;}
function ioCopy(raw,readKey,writeKey,readLabel,writeLabel){if(!raw||typeof raw!=='object')return null;const read=formatBytes(raw[readKey]);const write=formatBytes(raw[writeKey]);if(!read&&!write)return null;return `${read||'—'} ${readLabel} · ${write||'—'} ${writeLabel}`;}
function serviceResourceGauges(service){
  const resources=service.resources&&typeof service.resources==='object'?service.resources:{};
  const age=telemetryAge(resources.updatedAt);
  const source=String(resources.source||'').toLowerCase()==='docker'?'Docker':'Source unavailable';
  const stopped=service.container&&String(service.container.state||'').toLowerCase()!=='running';
  const retained=resources.sampleState==='last_sample';
  let available=0;
  const gauges=serviceResourceDefinitions.map(definition=>{
    const raw=resources[definition.key];
    const measured=resourcePercent(raw);
    const hasValue=Number.isFinite(measured);
    const declaredCapacity=definition.key==='cpu'&&raw&&typeof raw==='object'?Number(raw.capacityPercent):100;
    const meterMax=Number.isFinite(declaredCapacity)&&declaredCapacity>0?declaredCapacity:100;
    const utilization=hasValue?Math.max(0,Math.min(100,measured/meterMax*100)):0;
    if(hasValue)available+=1;
    const tone=!hasValue?'unavailable':utilization>=definition.critical?'critical':utilization>=definition.warning?'warning':'normal';
    const stale=age.stale||stopped||retained;
    const staleClass=stale&&hasValue?' stale':'';
    const value=hasValue?`${Math.round(measured)}%`:'—';
    let detail='';
    if(definition.key==='cpu'&&raw&&typeof raw==='object'){
      const onlineCpus=Number(raw.onlineCpus);
      if(Number.isFinite(onlineCpus)&&onlineCpus>0)detail=` (${(measured/100).toFixed(1)} of ${onlineCpus} CPU cores)`;
    }else if(definition.key==='memory'&&raw&&typeof raw==='object'){
      const used=formatBytes(raw.usedBytes??raw.used);
      const total=formatBytes(raw.totalBytes??raw.total);
      if(used&&total)detail=` (${used} of ${total})`;
    }
    const meter=hasValue?`role="meter" aria-valuemin="0" aria-valuemax="${Math.round(meterMax)}" aria-valuenow="${Math.round(measured)}" aria-valuetext="${value}${esc(detail)}"`:'role="img"';
    return `<span class="resource-gauge ${tone}${staleClass}" ${meter} aria-label="${esc(definition.label)} usage for ${esc(service.name)}${hasValue?`: ${value}${detail}`:': unavailable'}"><span class="resource-gauge-copy"><span>${esc(definition.label)}</span><strong>${value}</strong></span><span class="resource-gauge-track" aria-hidden="true"><span class="resource-gauge-fill" style="--resource-value:${utilization}%"></span></span></span>`;
  }).join('');
  const disk=ioCopy(resources.blockIo,'readBytes','writeBytes','read','written');
  const network=ioCopy(resources.network,'rxBytes','txBytes','in','out');
  const ioAvailable=Boolean(disk||network);
  const stale=age.stale||stopped||retained;
  const coverage=available+Number(ioAvailable);
  const partial=Boolean(coverage)&&(available<serviceResourceDefinitions.length||!disk||!network);
  let summary='Unavailable';
  if(coverage){
    if(!age.epoch)summary=partial?'Freshness unavailable, partial':'Freshness unavailable';
    else if(stale)summary=(stopped||retained)?(partial?'Last sample, partial':'Last sample'):(partial?'Stale, partial':'Stale');
    else summary=partial?'Partial':'Live';
  }
  const freshness=age.epoch?age.label:'time unavailable';
  const sourceCopy=`${summary} · ${source} · ${freshness}`;
  return `<span class="service-resources">${runtimeState(service)}<span class="service-resources-head"><strong>Resources</strong><small class="${stale?'stale':''}">${esc(sourceCopy)}</small></span><span class="resource-gauges">${gauges}</span><dl class="resource-io" aria-label="Cumulative container I/O for ${esc(service.name)}"><div><dt>Disk I/O</dt><dd class="${disk?'':'unavailable'}">${esc(disk||'—')}</dd></div><div><dt>Network I/O</dt><dd class="${network?'':'unavailable'}">${esc(network||'—')}</dd></div></dl></span>`;
}
function overall(data){const counts=data.counts||{};if(counts.failed)return['failed','Stack needs intervention',`${counts.failed} service${counts.failed===1?'':'s'} failed the last check.`];if(counts.action_required)return['action_required','Service connection needs attention',`${counts.action_required} action${counts.action_required===1?'':'s'} required to finish configuration.`];if((counts.waiting||0)+(counts.configuring||0))return['configuring','Stack is configuring','Services are starting or managed settings are being applied.'];if((counts.healthy||0)===data.services.length&&data.services.length)return['healthy','All selected services operational','The selected stack is configured and responding.'];return['unknown','Checking stack','Waiting for current service health information.'];}
const roleLabels={indexer_manager:'Indexer manager',vpn_provider:'Network service',challenge_solver:'Challenge solver',download_client:'Download client',media_manager:'Media manager',subtitle_manager:'Subtitle manager',request_manager:'Request manager',profile_manager:'Profile manager',media_server:'Media server'};
const serviceTypes=[{id:'discovery',name:'Discovery',roles:['indexer_manager','challenge_solver']},{id:'network',name:'Network services',roles:['vpn_provider']},{id:'downloads',name:'Download clients',roles:['download_client']},{id:'media',name:'Media managers',roles:['media_manager']},{id:'companions',name:'Companion apps',roles:['subtitle_manager','request_manager','profile_manager']},{id:'servers',name:'Media servers',roles:['media_server']}];
function freshServiceSelection(){return !setupState?.confirmed&&setupState?.phase==='detect'&&!setupState?.configurationChanged&&!(setupState?.apps||[]).length;}
function moduleIsActive(module){if(freshServiceSelection())return Boolean(module.required);if(typeof module.active==='boolean')return module.active;const active=setupState?.activeEnabledServices;if(Array.isArray(active))return active.includes(module.id);return Boolean(module.enabled);}
function activeServiceModuleIds(){return (setupState?.modules||[]).filter(module=>module.required||moduleIsActive(module)).map(module=>module.id);}
function selectedModules(){return [...new Set([...addServiceBaseIds,addServiceId].filter(Boolean))];}
function selectedServiceModule(){return (setupState?.modules||[]).find(module=>module.id===addServiceId)||null;}
function selectedVpnProvider(){const selected=new Set(selectedModules());if(selected.has('privado-vpn'))return'privado';return setupState?.vpnProvider==='privado'?'direct':setupState?.vpnProvider||'direct';}
function moduleAvailability(module){if(module?.installed===false)return{eligible:false,state:'not-installed',copy:'Not installed — install it in your container platform'};if(module?.installed===true){const state=String(module.container?.state||'').toLowerCase();if(state==='running')return{eligible:true,state:'running',copy:'Installed and running'};if(state&&!['unknown','unavailable'].includes(state))return{eligible:false,state:'stopped',copy:'Stopped — start the container first'};return{eligible:false,state:'unavailable',copy:'Docker state unavailable — refresh and try again'};}if(setupState?.docker?.configured)return{eligible:false,state:'unavailable',copy:'Docker inventory unavailable — refresh and try again'};return{eligible:true,state:'direct',copy:'Connect by API address'};}
function moduleCanAdd(module){return Boolean(module)&&moduleAvailability(module).eligible;}
function chooseService(moduleId){const module=(setupState?.modules||[]).find(item=>item.id===moduleId);if(!moduleCanAdd(module))return;addServiceId=moduleId;addServiceStage='connect';renderSetup();requestAnimationFrame(()=>element('selectedServiceTitle')?.focus());}
function setupReviewBlockers(apps){return apps.filter(app=>!app.reachable||(!app.credentials&&app.id!=='qbittorrent'));}
function connectionModules(module,blockers){const ids=new Set(module?[module.id]:[]);blockers.forEach(app=>ids.add(app.id));return [...ids].map(id=>(setupState?.modules||[]).find(item=>item.id===id)).filter(Boolean);}
function apiKeyEnvironmentVariable(item){return item.apiKeyEnvironmentVariable||`UMBREL_ARR_${item.id.toUpperCase().replaceAll('-','_')}_API_KEY`;}
function automaticCredentialSource(item){return['managed_config','service_api'].includes(item?.credentialSource)&&item?.credentialConfigured;}
function initialCredentialSource(item,draft){if(automaticCredentialSource(item))return'automatic';if(draft.credentialSource)return draft.credentialSource;if(item.credentialSource==='ui')return'ui';if(item.credentialSource==='environment'||item.credentialConfigured)return'environment';return'ui';}
function collectConnectionDrafts(){
  document.querySelectorAll('[data-connection-source]:checked').forEach(input=>{const id=input.dataset.connectionSource;connectionDrafts[id]={...(connectionDrafts[id]||{}),credentialSource:input.value};});
  document.querySelectorAll('[data-connection-url]').forEach(input=>{const id=input.dataset.connectionUrl;connectionDrafts[id]={...(connectionDrafts[id]||{}),url:input.value.trim()};});
  document.querySelectorAll('[data-connection-key]').forEach(input=>{const id=input.dataset.connectionKey;const draft=connectionDrafts[id]||{};if(!input.disabled&&input.value.trim())draft.apiKey=input.value.trim();else delete draft.apiKey;connectionDrafts[id]=draft;});
  Object.entries(connectionDrafts).forEach(([id,draft])=>{const module=(setupState?.modules||[]).find(item=>item.id===id);if(module&&!module.requires_api_key){delete draft.apiKey;delete draft.credentialSource;}else if(draft.credentialSource==='environment')delete draft.apiKey;});
  return connectionDrafts;
}
function applyCredentialSource(card,source){
  card.querySelectorAll('[data-credential-panel]').forEach(panel=>{const active=panel.dataset.credentialPanel===source;panel.hidden=!active;panel.querySelectorAll('input').forEach(input=>input.disabled=!active);});
}
function renderDirectConnections(module,blockers){
  const section=element('directConnections');const target=element('directConnectionFields');if(!section||!target)return;
  const modules=connectionModules(module,blockers);section.hidden=!modules.length;
  const usesCredentials=modules.some(item=>item.requires_api_key);setText('directConnectionsHelp',usesCredentials?'Enter an API address this process can reach. Automatically discovered credentials are validated without exposing them.':'Enter a service address this process can reach.');const credentialNote=element('directConnectionNote');if(credentialNote)credentialNote.hidden=!usesCredentials;
  target.innerHTML=modules.map(item=>{
    const draft=connectionDrafts[item.id]||{};const address=draft.url??item.connectionUrl??'';const keyValue=draft.apiKey||'';
    const app=(setupState.apps||[]).find(value=>value.id===item.id);const rejectedAutomatic=automaticCredentialSource(item)&&app?.action==='invalid_credentials';
    const source=item.requires_api_key?(rejectedAutomatic?'ui':initialCredentialSource(item,draft)):'';if(!item.requires_api_key){delete draft.apiKey;delete draft.credentialSource;}else if(source==='automatic')delete draft.credentialSource;else draft.credentialSource=source;connectionDrafts[item.id]=draft;
    const environmentVariable=apiKeyEnvironmentVariable(item);
    const environmentActive=item.credentialSource==='environment'&&item.credentialConfigured;
    const uiActive=item.credentialSource==='ui'&&item.credentialConfigured;
    const environmentHelp=environmentActive?`Configured through ${environmentVariable}. It remains available after restart.`:`Set ${environmentVariable} on the umbrelarr process, then restart it.`;
    const uiHelp=uiActive?'A UI-provided key is active. Leave this blank to keep using it for this process.':'Stored only in memory for this running process; it must be entered again after restart.';
    const finishSignIn=app?.action==='complete_sign_in';
    const automaticCopy=finishSignIn?'Finish Plex sign-in in Overseerr. Its generated API key will be adopted automatically when you check again.':item.credentialSource==='service_api'?'Dedicated umbrelarr API key created and verified through the service API.':item.id==='plex'?'Existing Plex token found and verified without exposing it.':'Generated API key found in the installed app and verified without exposing it.';
    const automaticHeading=finishSignIn?'Finish sign-in first':'Connected automatically';
    const credentialFields=item.requires_api_key?(source==='automatic'?`<div class="credential-automatic" role="status"><span class="credential-automatic-symbol" aria-hidden="true">${finishSignIn?'→':'✓'}</span><span><strong>${esc(automaticHeading)}</strong><small>${esc(automaticCopy)}</small></span></div>`:`<fieldset class="credential-source"><legend>API key source</legend><div class="credential-source-options"><label class="credential-source-option"><input type="radio" name="credential-source-${esc(item.id)}" value="environment" data-connection-source="${esc(item.id)}"${source==='environment'?' checked':''}><span><strong>Environment variable</strong><small>Restart-safe deployment configuration</small></span></label><label class="credential-source-option"><input type="radio" name="credential-source-${esc(item.id)}" value="ui" data-connection-source="${esc(item.id)}"${source==='ui'?' checked':''}><span><strong>Enter in UI</strong><small>Fast setup for this running process</small></span></label></div><div class="credential-source-panel" data-credential-panel="environment"${source==='environment'?'':' hidden'}><code>${esc(environmentVariable)}</code><p class="${environmentActive?'configured':''}">${esc(environmentHelp)}</p></div><div class="credential-source-panel" data-credential-panel="ui"${source==='ui'?'':' hidden'}><label><span>API key</span><input type="password" autocomplete="new-password" data-connection-key="${esc(item.id)}" value="${esc(keyValue)}" aria-describedby="connection-key-help-${esc(item.id)}"${source==='ui'?'':' disabled'}><small id="connection-key-help-${esc(item.id)}">${esc(uiHelp)}</small></label></div></fieldset>`):'';
    return `<div class="direct-connection-card" data-connection-card="${esc(item.id)}"><strong>${esc(item.name)}</strong><div class="direct-connection-fields"><label><span>Service address</span><input type="url" inputmode="url" autocomplete="url" spellcheck="false" data-connection-url="${esc(item.id)}" value="${esc(address)}" placeholder="http://service:port" required></label>${credentialFields}</div></div>`;
  }).join('');
  target.querySelectorAll('[data-connection-source]').forEach(input=>input.onchange=()=>{const card=input.closest('[data-connection-card]');const draft=connectionDrafts[input.dataset.connectionSource]||{};draft.credentialSource=input.value;if(input.value==='environment'){delete draft.apiKey;const keyInput=card.querySelector('[data-connection-key]');if(keyInput)keyInput.value='';}connectionDrafts[input.dataset.connectionSource]=draft;applyCredentialSource(card,input.value);collectConnectionDrafts();});
  target.querySelectorAll('[data-connection-card]').forEach(card=>applyCredentialSource(card,card.querySelector('[data-connection-source]:checked')?.value||'ui'));
  target.querySelectorAll('[data-connection-url],[data-connection-key]').forEach(input=>input.oninput=()=>collectConnectionDrafts());
}
function renderModuleCatalog(){
  const target=element('moduleCatalog');
  if(!target||!setupState)return;
  const modules=(setupState.modules||[]).filter(module=>!module.required&&!moduleIsActive(module));
  const groups=[];
  for(const type of serviceTypes){const items=modules.filter(module=>type.roles.includes(module.role));if(items.length)groups.push({type,items});}
  const knownRoles=new Set(serviceTypes.flatMap(type=>type.roles));const other=modules.filter(module=>!knownRoles.has(module.role));if(other.length)groups.push({type:{id:'other',name:'Other services'},items:other});
  setText('serviceCatalogTitle',setupState.docker?.configured?'Local services':'Connect a service');
  target.classList.add('module-store');
  target.innerHTML=groups.length?groups.map(({type,items})=>`<section class="module-type-group" data-service-type="${esc(type.id)}"><div class="module-type-head"><h4>${esc(type.name)}</h4><span>${items.length} service${items.length===1?'':'s'}</span></div><div class="module-type-grid">${items.map(module=>{const availability=moduleAvailability(module);const stateId=`module-state-${module.id}`;return `<article class="module-store-item" data-module-card data-module-id="${esc(module.id)}" data-install-state="${esc(availability.state)}" data-selection-state="${module.id===addServiceId?'selected':availability.eligible?'available':'unavailable'}">${serviceMark(module)}<span class="module-store-copy"><strong>${esc(module.name)}</strong><small>${esc(roleLabels[module.role]||module.role.replaceAll('_',' '))}</small><span class="module-store-state" id="${esc(stateId)}">${esc(availability.copy)}</span></span><button class="module-action add" type="button" data-module-action aria-label="Add ${esc(module.name)}" aria-describedby="${esc(stateId)}"${availability.eligible?'':' disabled'}>Add</button></article>`;}).join('')}</div></section>`).join(''):'<div class="empty">Every available catalog service is already managed.</div>';
  const availableCount=modules.filter(module=>moduleCanAdd(module)).length;
  const summary=setupState.docker?.configured?`${availableCount} of ${modules.length} installed services ready to add.`:`${modules.length} supported service${modules.length===1?'':'s'} across ${groups.length} categor${groups.length===1?'y':'ies'}; connect one by API address.`;
  setText('serviceTypeSummary',modules.length?summary:'There are no more services to add.');
  target.querySelectorAll('[data-module-card]').forEach(card=>{const action=card.querySelector('[data-module-action]');if(!action.disabled)action.onclick=()=>chooseService(card.dataset.moduleId);});
}
function setupAppRow(app){const pendingLabels={temporary_password_required:'One-time password required',create_api_key:'Create API key',claim_server:'Claim server',complete_sign_in:'Finish sign-in',invalid_credentials:'Credentials rejected',connection_error:'Connection check failed',wait_for_api_key:'API key required',direct_connection_required:'Direct address required',docker_unavailable:'Docker unavailable',start_service:'Start service'};const actionState=app.action==='docker_unavailable'?'failed':app.action==='start_service'?'action_required':null;const state=!app.reachable?(actionState||'failed'):app.credentials?'healthy':actionState||'action_required';const label=!app.reachable?(pendingLabels[app.action]||'Not found'):app.credentials?'Ready to add':pendingLabels[app.action]||'API key pending';const open=app.link&&!['direct_connection_required','docker_unavailable'].includes(app.action)?`<a class="open-link" href="${esc(app.link)}" target="_blank" rel="noreferrer">Open</a>`:'';return `<div class="attention-item"><div class="attention-name">${esc(app.name)}</div><div><span class="status ${state}"><span class="status-dot"></span>${esc(label)}</span><div class="detail">${esc(app.detail)}</div></div>${open}</div>`;}
function prepareAddServiceFlow(){connectionDrafts={};addServiceBaseIds=activeServiceModuleIds();const pending=(setupState?.detectionComplete?(setupState.modules||[]).filter(module=>!module.required&&!moduleIsActive(module)&&module.enabled):[]);addServiceId=pending.length===1?pending[0].id:null;addServiceStage=addServiceId?'reviewed':'choose';addServiceDraftServerSide=Boolean(addServiceId);}
function renderSetup(){
  if(!setupState)return;
  const manager=element('serviceManager');
  const panel=element('setupPanel');
  if(panel)panel.hidden=setupState.phase==='confirmed';
  if(element('reconcile'))element('reconcile').disabled=setupState.phase!=='confirmed'||Boolean(statusState?.running);
  if(!manager)return;
  renderModuleCatalog();
  const module=selectedServiceModule();
  const choose=element('serviceChooseStep');
  const connect=element('serviceConnectStep');
  if(choose)choose.hidden=addServiceStage!=='choose';
  if(connect)connect.hidden=addServiceStage==='choose';
  manager.querySelectorAll('[data-add-step]').forEach(step=>{const connectStep=step.dataset.addStep==='connect';step.classList.toggle('active',connectStep?addServiceStage!=='choose':addServiceStage==='choose');step.classList.toggle('complete',!connectStep&&addServiceStage!=='choose');});
  const selected=element('selectedServiceSummary');
  if(selected&&module)selected.innerHTML=`${serviceMark(module)}<span><strong id="selectedServiceTitle" tabindex="-1">${esc(module.name)}</strong><span>${esc(roleLabels[module.role]||module.role.replaceAll('_',' '))} · umbrelarr will connect directly to this service.</span></span>`;
  const list=element('setupApps');
  const apps=setupState.apps||[];
  const reviewed=addServiceStage==='reviewed';
  const blockers=reviewed?setupReviewBlockers(apps):[];
  if(list){
    const relevant=reviewed?apps.filter(app=>app.id===addServiceId||!app.reachable||!app.credentials):[];
    list.innerHTML=reviewed?(relevant.length?relevant.map(setupAppRow).join(''):'<div class="empty">The service check did not return a result. Check again.</div>'):`<div class="empty">Enter the direct API connection above, then check ${esc(module?.name||'this service')}.</div>`;
  }
  renderDirectConnections(module,blockers);
  const selectedApp=apps.find(app=>app.id===addServiceId);
  const jellyfinBootstrap=element('jellyfinCredentialBootstrap');
  const showJellyfinBootstrap=Boolean(
    reviewed&&module?.id==='jellyfin'&&selectedApp?.reachable&&
    selectedApp?.action==='create_api_key'&&!module.environmentCredentialConfigured
  );
  if(jellyfinBootstrap)jellyfinBootstrap.hidden=!showJellyfinBootstrap;
  const qbitAction=apps.find(app=>app.id==='qbittorrent')?.action;
  if(element('qbittorrentCredentials'))element('qbittorrentCredentials').hidden=!(addServiceId==='qbittorrent'&&qbitAction==='temporary_password_required');
  const detect=element('detectApps');
  if(detect){detect.hidden=addServiceStage==='choose'||!module;detect.disabled=false;detect.textContent=addServiceStage==='reviewed'?'Check again':`Check ${module?.name||'service'}`;}
  const confirm=element('confirmSetup');
  if(confirm){confirm.hidden=!reviewed||!module||!setupState.canConfirm||setupState.phase==='confirmed';confirm.disabled=false;confirm.textContent=`Add ${module?.name||'service'}`;}
  const help=element('setupActionHelp');
  if(help){
    if(showJellyfinBootstrap)help.textContent='Create the dedicated key below, then add Jellyfin.';
    else if(reviewed&&module?.environmentCredentialConfigured&&selectedApp?.action==='invalid_credentials')help.textContent=`Replace or remove ${apiKeyEnvironmentVariable(module)}, restart umbrelarr, then check again.`;
    else help.textContent=reviewed&&!setupState.canConfirm?'Update the connection above, then check again.':'';
  }
}
async function loadSetup(){const response=await fetch('/api/setup',{cache:'no-store'});if(!response.ok)throw new Error('Unable to load setup state');setupState=await response.json();renderSetup();renderServiceGrid();}
const serviceStatusOrder={failed:0,action_required:1,waiting:2,configuring:2,unknown:3,healthy:4};
function removableServiceModule(serviceId){return (setupState?.modules||[]).find(module=>module.id===serviceId&&!module.required&&moduleIsActive(module))||null;}
function serviceCard(service){const role=(service.role||service.id).replaceAll('_',' ');const blockers=(service.waitingOn||[]).length;const dependencies=(service.dependencies||[]).length;const checkCount=(service.checks||[]).length;const removable=service.managed!==false?removableServiceModule(service.id):null;const addable=service.managed===false;const action=removable?`<button class="service-remove" type="button" data-remove-service="${esc(service.id)}" aria-label="Remove ${esc(service.name)} from managed services">Remove</button>`:addable?`<button class="service-add" type="button" data-add-local-service="${esc(service.id)}" aria-label="Add local ${esc(service.name)} to managed services">Add service</button>`:'';return `<article class="service-card ${esc(service.status)}" data-managed="${service.managed===false?'false':'true'}"><div class="service-card-link"><span class="service-card-head"><span class="service-card-identity">${serviceMark(service)}<span class="service-card-title"><strong>${esc(service.name)}</strong><small>${esc(role)}</small></span></span><span class="status ${esc(service.status)}"><span class="status-dot"></span>${esc(labels[service.status]||service.status)}</span></span><span class="service-card-body"><span class="service-card-detail">${esc(service.detail)}</span>${serviceResourceGauges(service)}<dl class="service-quick-metrics"><div><dt>Checked</dt><dd>${esc(checkedAgo(service.checked_at))}</dd></div><div><dt>Samples</dt><dd>${checkCount}</dd></div><div><dt>Links</dt><dd>${blockers?`${blockers} blocked`:dependencies?`${dependencies} ready`:'None'}</dd></div></dl></span></div>${action?`<footer class="service-card-actions">${action}</footer>`:''}</article>`;}
function renderInventoryContext(){const inventory=statusState?.inventory;if(!inventory)return;const notice=element('inventoryNotice');if(inventory.configured){if(notice){notice.hidden=Boolean(inventory.available);notice.classList.toggle('error',!inventory.available);setText('inventoryNoticeTitle','Local Docker inventory is unavailable');setText('inventoryNoticeCopy',inventory.error?`The last inventory refresh failed: ${inventory.error}`:'Waiting for the read-only Docker inventory broker.');}}else if(notice){notice.hidden=false;notice.classList.remove('error');setText('inventoryNoticeTitle','Local Docker inventory is not connected');setText('inventoryNoticeCopy','Only this umbrelarr process and explicitly connected services are shown. Local containers appear after the read-only Docker inventory broker is connected.');}}
function renderServiceGrid(){const grid=element('serviceGrid');if(!grid||!statusState)return;renderInventoryContext();const query=(element('serviceSearch')?.value||'').trim().toLowerCase();const state=element('serviceStateFilter')?.value||'all';const services=[...(statusState.services||[])].sort((a,b)=>(serviceStatusOrder[a.status]??9)-(serviceStatusOrder[b.status]??9)||a.name.localeCompare(b.name));const filtered=services.filter(service=>(!query||`${service.name} ${service.id} ${service.detail}`.toLowerCase().includes(query))&&(state==='all'||service.status===state));setText('serviceCount',`${filtered.length} of ${services.length} visible services`);grid.innerHTML=filtered.length?filtered.map(serviceCard).join(''):'<div class="empty service-grid-empty">No visible services match these filters.</div>';}
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
  const [freshLabel]=ago(data.lastCompletedAt);
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
  renderLibraryGrid();
  renderLibraryApps();
  if(element('attentionRows')){
    const actions=data.services.filter(service=>['failed','action_required'].includes(service.status));
    element('attentionRows').innerHTML=actions.length?actions.map(service=>{const setup=service.id==='umbrelarr';const vpn=service.id==='privado-vpn';const href=setup?'/services':vpn?'#vpnPanel':service.link;return `<div class="attention-item"><div class="attention-name">${esc(service.name)}</div><div><span class="status ${esc(service.status)}"><span class="status-dot"></span>${esc(labels[service.status])}</span><div class="detail">${esc(service.detail)}</div></div><a class="open-link" href="${esc(href)}"${setup||vpn?'':' target="_blank" rel="noreferrer"'}>${setup?'Manage':vpn?'Configure':'Open'}</a></div>`;}).join(''):'<div class="empty">No services need action.</div>';
  }
  if(element('events'))element('events').innerHTML=data.events.length?data.events.slice(0,50).map(event=>`<div class="event"><time datetime="${new Date(event.at*1000).toISOString()}">${new Date(event.at*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time><span>${esc(event.message)}</span></div>`).join(''):'<div class="empty">No reconciliation activity yet.</div>';
}
function libraryAppChips(library){return `<span class="library-apps">${library.apps.map(slug=>{const service=(statusState?.services||[]).find(item=>item.id===slug);const state=service?.status||'unknown';const name=service?.name||slug;return `<span class="library-app ${esc(state)}" title="${esc(name)}: ${esc(labels[state]||state)}"><span class="status-dot"></span>${esc(name)}</span>`;}).join('')}</span>`;}
const librarySourceLabels={local:'Umbrel storage',network:'Network storage',existing:'System folder',custom:'System folder'};
let libraryBrowserPath='';
let libraryBrowserRequest=0;
let libraryMountsValid=false;
function libraryIcon(library){let type='tv',drawing='<rect x="3" y="5" width="18" height="13" rx="3"/><path d="M8 22h8M12 18v4M7 10h10"/>';if(library.id.startsWith('movies')){type='movies';drawing='<path d="M4 8h16v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"/><path d="m4 8 2-5 4 5 2-5 4 5 2-5 2 5M10 12.5l5 2.7-5 2.8Z"/>';}else if(library.id==='music'){type='music';drawing='<path d="M9 18V6l10-2v12"/><circle cx="6" cy="18" r="3"/><circle cx="16" cy="16" r="3"/><path d="M9 9l10-2"/>';}const badge=library.variant==='4K'?'<span class="library-icon-badge">4K</span>':'';return `<span class="library-icon ${type}" aria-hidden="true"><svg viewBox="0 0 24 24">${drawing}</svg>${badge}</span>`;}
function renderLibraryApps(){if(!storageState)return;document.querySelectorAll('[data-library-apps]').forEach(target=>{const library=storageState.libraries.find(item=>item.key===target.dataset.libraryApps);if(library)target.innerHTML=libraryAppChips(library);});}
function renderLibraryGrid(){const grid=element('libraryGrid');if(!grid||!storageState)return;const libraries=storageState.libraries||[];setText('librarySummary',`${libraries.length} managed ${libraries.length===1?'library':'libraries'}`);grid.innerHTML=libraries.length?libraries.map(library=>`<a class="library-card" href="/libraries/${encodeURIComponent(library.id)}" aria-label="Open ${esc(library.name)} ${esc(library.variant)} library"><span class="library-card-head">${libraryIcon(library)}<span class="library-card-title"><strong>${esc(library.name)}</strong><small>${esc(library.variant)} library</small></span></span><span class="library-card-body"><span class="library-root"><span>Current root</span><code>${esc(library.root)}</code></span><dl class="library-card-meta"><div><dt>Source</dt><dd>${esc(librarySourceLabels[library.source]||'System folder')}</dd></div><div><dt>Category</dt><dd>${esc(library.category)}</dd></div></dl>${libraryAppChips(library)}</span><span class="library-card-foot"><span>${library.apps.length} connected service${library.apps.length===1?'':'s'}</span><strong>Open library →</strong></span></a>`).join(''):'<div class="empty service-grid-empty">No media libraries are managed yet. Add a media manager from Services first.</div>';}
function activeLibrary(){const detail=element('libraryDetail');if(!detail||!storageState)return null;return storageState.libraries.find(item=>item.id===detail.dataset.libraryId)||null;}
function filesystemFolderIcon(){return '<span class="filesystem-folder-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M3 7.5h6l2 2h10v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 9.5V6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1.5"/></svg></span>';}
function filesystemCrumbs(path){const parts=String(path||'/').split('/').filter(Boolean);let current='';const values=[`<button class="filesystem-crumb" type="button" data-library-browse-path="/" aria-label="Open filesystem root">Root</button>`];parts.forEach(part=>{current+=`/${part}`;values.push('<span class="filesystem-separator" aria-hidden="true">/</span>',`<button class="filesystem-crumb" type="button" data-library-browse-path="${esc(current)}">${esc(part)}</button>`);});return values.join('');}
function renderLibraryMountChecks(mounts,allMounted){const target=element('libraryMountCheck');if(!target)return;const values=Array.isArray(mounts)?mounts:[];const chips=values.map(item=>`<span class="mount-chip ${esc(item.status)}" title="${esc(item.detail||'')}"><span class="status-dot"></span>${esc(item.name)}</span>`).join('');const summary=allMounted?'Every media service can use this exact path.':'Choose a path mounted at the same location in every media service.';target.innerHTML=`<strong>Same path in every media service</strong><div class="filesystem-mounts">${chips}</div><div class="filesystem-mount-summary ${allMounted?'success':'error'}">${esc(summary)}</div>`;}
async function loadLibraryBrowser(path,chooseCustom=false){const library=activeLibrary();if(!library||!element('libraryBrowser'))return;const request=++libraryBrowserRequest;const nextPath=String(path||'/').trim()||'/';libraryBrowserPath=nextPath;libraryMountsValid=false;if(chooseCustom){const custom=document.querySelector('[name="librarySource"][value="custom"]');if(custom)custom.checked=true;}if(element('libraryPath'))element('libraryPath').value=nextPath;setText('libraryBrowserPath',nextPath);if(element('libraryBrowserCrumbs'))element('libraryBrowserCrumbs').innerHTML=filesystemCrumbs(nextPath);if(element('libraryBrowserList'))element('libraryBrowserList').innerHTML='<div class="filesystem-message">Loading folders…</div>';if(element('libraryMountCheck'))element('libraryMountCheck').innerHTML='<strong>Same path in every media service</strong><div class="filesystem-mount-summary">Checking service mounts…</div>';if(element('saveLibrary'))element('saveLibrary').disabled=true;try{const query=new URLSearchParams({libraryKey:library.key,path:nextPath});const response=await fetch(`/api/storage/browse?${query}`,{cache:'no-store'});const data=await response.json().catch(()=>({error:'Unable to browse this folder'}));if(request!==libraryBrowserRequest)return;if(!response.ok)throw new Error(data.error||'Unable to browse this folder');libraryBrowserPath=data.path||nextPath;if(element('libraryPath'))element('libraryPath').value=libraryBrowserPath;setText('libraryBrowserPath',libraryBrowserPath);setText('libraryBrowserService',`${data.service} filesystem · folders only`);if(element('libraryBrowserCrumbs'))element('libraryBrowserCrumbs').innerHTML=filesystemCrumbs(libraryBrowserPath);const up=element('libraryBrowserUp');if(up){up.disabled=!data.parent;if(data.parent)up.dataset.libraryBrowsePath=data.parent;else delete up.dataset.libraryBrowsePath;}const directories=Array.isArray(data.directories)?data.directories:[];if(element('libraryBrowserList'))element('libraryBrowserList').innerHTML=directories.length?directories.map(item=>`<button class="filesystem-row" type="button" data-library-browse-path="${esc(item.path)}">${filesystemFolderIcon()}<span class="filesystem-row-copy"><strong>${esc(item.name)}</strong><code>${esc(item.path)}</code></span><span class="filesystem-row-arrow" aria-hidden="true">›</span></button>`).join(''):'<div class="filesystem-message">This folder has no subfolders. You can select it as the library location.</div>';libraryMountsValid=Boolean(data.allMounted);renderLibraryMountChecks(data.mounts,libraryMountsValid);if(element('saveLibrary'))element('saveLibrary').disabled=!libraryMountsValid;}catch(value){if(request!==libraryBrowserRequest)return;const up=element('libraryBrowserUp');if(up)up.disabled=true;if(element('libraryBrowserList'))element('libraryBrowserList').innerHTML=`<div class="filesystem-message error">${esc(value.message)}</div>`;if(element('libraryMountCheck'))element('libraryMountCheck').innerHTML=`<strong>Same path in every media service</strong><div class="filesystem-mount-summary error">${esc(value.message)}</div>`;setText('libraryBrowserService','Filesystem unavailable');}}
function updateLibrarySourceFields(){const library=activeLibrary();if(!library)return;const source=document.querySelector('[name="librarySource"]:checked')?.value||(library.source==='existing'?'custom':library.source);let path=libraryBrowserPath||library.root;if(source==='local')path=storageState.presets?.local?.[library.key]||library.root;if(source==='network')path=storageState.presets?.network?.[library.key]||library.root;if(source==='custom'&&!libraryBrowserPath)path=library.root;loadLibraryBrowser(path,false);}
function renderLibraryDetail(){const detail=element('libraryDetail');if(!detail||!storageState)return;const library=activeLibrary();if(!library){setText('libraryDetailName','Library unavailable');setText('libraryDetailCopy','This library is not part of the current managed stack.');return;}const icon=element('libraryDetailIcon');if(icon)icon.innerHTML=libraryIcon(library);const sourceLabel=librarySourceLabels[library.source]||'System folder';setText('libraryDetailName',`${library.name} ${library.variant}`);setText('libraryDetailCopy',`${sourceLabel} · ${library.category} download category`);setText('libraryDetailRoot',library.root);setText('libraryCategory',library.category);setText('librarySourceValue',sourceLabel);setText('libraryRootValue',library.root);setText('libraryServiceCount',`${library.apps.length} services`);const form=element('libraryForm');if(form)form.dataset.libraryKey=library.key;const sourceValue=library.source==='existing'?'custom':library.source;const source=document.querySelector(`[name="librarySource"][value="${sourceValue}"]`);if(source)source.checked=true;const apps=element('libraryDetailApps');if(apps)apps.innerHTML=libraryAppChips(library);libraryBrowserPath=library.root;if(element('libraryPath'))element('libraryPath').value=library.root;loadLibraryBrowser(library.root,false);}
async function loadStorage(){const response=await fetch('/api/storage',{cache:'no-store'});if(!response.ok)throw new Error('Unable to load library locations');storageState=await response.json();renderLibraryGrid();renderLibraryDetail();}
async function mutate(url,options={}){const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},...options});if(!response.ok){const data=await response.json().catch(()=>({error:'Request failed'}));throw new Error(data.error||'Request failed');}await load();}
if(element('refresh'))element('refresh').onclick=()=>load().catch(error=>alert(error.message));
if(element('reconcile'))element('reconcile').onclick=()=>mutate('/api/reconcile').catch(error=>alert(error.message));
async function openServiceManager(preselectedId=''){const manager=element('serviceManager');if(!manager)return;if(!setupState){try{await loadSetup();}catch(value){alert(value.message);return;}}prepareAddServiceFlow();if(preselectedId){const module=(setupState.modules||[]).find(item=>item.id===preselectedId);if(!module||module.required||moduleIsActive(module)||!moduleCanAdd(module))return;addServiceBaseIds=activeServiceModuleIds();addServiceId=module.id;addServiceStage='connect';addServiceDraftServerSide=false;}renderSetup();if(!manager.open)manager.showModal();document.body.classList.add('modal-open');requestAnimationFrame(()=>(preselectedId?element('selectedServiceTitle'):element('serviceManagerTitle'))?.focus());}
function closeRemoveServiceDialog(restoreFocus=true){const dialog=element('removeServiceDialog');if(dialog?.open)dialog.close();document.body.classList.remove('modal-open');const focusTarget=removeServiceReturnFocus;removeServiceId=null;removeServiceReturnFocus=null;if(restoreFocus&&focusTarget?.isConnected)requestAnimationFrame(()=>focusTarget.focus());}
function openRemoveService(serviceId,trigger){const module=removableServiceModule(serviceId);const service=(statusState?.services||[]).find(item=>item.id===serviceId);const dialog=element('removeServiceDialog');if(!module||!service||!dialog)return;removeServiceId=serviceId;removeServiceReturnFocus=trigger||document.activeElement;setText('removeServiceTitle',`Stop managing ${module.name}?`);setText('removeServiceDescription',`Remove ${module.name} from this managed fleet.`);const summary=element('removeServiceSummary');if(summary)summary.innerHTML=`${serviceMark(service)}<span><strong>${esc(module.name)}</strong><span>${esc(roleLabels[module.role]||module.role.replaceAll('_',' '))}</span></span>`;const confirm=element('confirmRemoveService');if(confirm){confirm.disabled=false;confirm.textContent=`Remove ${module.name}`;}if(element('cancelRemoveService'))element('cancelRemoveService').disabled=false;setText('removeServiceError','');if(!dialog.open)dialog.showModal();document.body.classList.add('modal-open');requestAnimationFrame(()=>element('removeServiceTitle')?.focus());}
async function confirmServiceRemoval(){const module=removableServiceModule(removeServiceId);const dialog=element('removeServiceDialog');const button=element('confirmRemoveService');const cancel=element('cancelRemoveService');const error=element('removeServiceError');if(!module||!dialog||!button)return;error.textContent='';button.disabled=true;if(cancel)cancel.disabled=true;button.textContent=`Removing ${module.name}…`;dialog.setAttribute('aria-busy','true');try{const response=await fetch('/api/setup/remove',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({serviceId:module.id})});const data=await response.json().catch(()=>({error:`Unable to remove ${module.name}`}));if(!response.ok)throw new Error(data.error||`Unable to remove ${module.name}`);setupState=data;if(statusState)statusState={...statusState,services:(statusState.services||[]).flatMap(service=>service.id!==module.id?[service]:service.discoverySource==='docker'?[{...service,managed:false,status:'unknown',detail:'Installed locally and available to manage',checked_at:0,checks:[],dependencies:[],waitingOn:[]}]:[])};const removedName=module.name;closeRemoveServiceDialog(false);renderServiceGrid();const notice=element('serviceActionStatus');if(notice){notice.hidden=false;notice.textContent=`${removedName} is no longer managed. The installed app and its settings were left unchanged.`;}requestAnimationFrame(()=>element('manageServices')?.focus());load().catch(value=>{if(notice)notice.textContent=`${removedName} was removed, but the latest service status could not be refreshed: ${value.message}`;});}catch(value){error.textContent=value.message;button.disabled=false;if(cancel)cancel.disabled=false;button.textContent=`Remove ${module.name}`;}finally{dialog.removeAttribute('aria-busy');}}
function openDeepLinkedService(){if(addServiceDeepLinkHandled||!setupState||!element('serviceManager'))return;const url=new URL(window.location.href);const requested=url.searchParams.get('add');if(!requested)return;addServiceDeepLinkHandled=true;url.searchParams.delete('add');history.replaceState(null,'',`${url.pathname}${url.search}${url.hash}`);const module=(setupState.modules||[]).find(item=>item.id===requested);if(!module||module.required||moduleIsActive(module))return;if(!moduleCanAdd(module)){openServiceManager();return;}openServiceManager(requested);}
if(element('manageServices'))element('manageServices').onclick=()=>openServiceManager();
if(element('serviceGrid'))element('serviceGrid').onclick=event=>{const remove=event.target.closest('[data-remove-service]');if(remove){openRemoveService(remove.dataset.removeService,remove);return;}const add=event.target.closest('[data-add-local-service]');if(add)openServiceManager(add.dataset.addLocalService);};
if(element('cancelRemoveService'))element('cancelRemoveService').onclick=()=>{if(!element('removeServiceDialog')?.hasAttribute('aria-busy'))closeRemoveServiceDialog(true);};
if(element('confirmRemoveService'))element('confirmRemoveService').onclick=confirmServiceRemoval;
if(element('removeServiceDialog')){element('removeServiceDialog').addEventListener('cancel',event=>{event.preventDefault();if(!event.currentTarget.hasAttribute('aria-busy'))closeRemoveServiceDialog(true);});element('removeServiceDialog').addEventListener('click',event=>{if(event.target===element('removeServiceDialog')&&!event.currentTarget.hasAttribute('aria-busy'))closeRemoveServiceDialog(true);});}
async function discardServiceDraft(closeDialog=true){const error=element('setupError');if(error)error.textContent='';try{const response=await fetch('/api/setup/cancel',{method:'POST'});const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to discard the service draft');setupState=data;connectionDrafts={};addServiceId=null;addServiceStage='choose';addServiceBaseIds=activeServiceModuleIds();addServiceDraftServerSide=false;renderSetup();const manager=element('serviceManager');if(closeDialog){if(manager?.open)manager.close();document.body.classList.remove('modal-open');element('manageServices')?.focus();}else{element('serviceCatalogTitle')?.focus();}}catch(value){if(error)error.textContent=value.message;}}
if(element('closeServiceManager'))element('closeServiceManager').onclick=()=>discardServiceDraft(true);
if(element('cancelServiceChanges'))element('cancelServiceChanges').onclick=()=>discardServiceDraft(true);
if(element('changeSelectedService'))element('changeSelectedService').onclick=async()=>{if(addServiceDraftServerSide){await discardServiceDraft(false);return;}connectionDrafts={};addServiceId=null;addServiceStage='choose';renderSetup();requestAnimationFrame(()=>element('serviceCatalogTitle')?.focus());};
if(element('serviceManager')){element('serviceManager').addEventListener('cancel',event=>{event.preventDefault();discardServiceDraft(true);});element('serviceManager').addEventListener('click',event=>{if(event.target===element('serviceManager'))discardServiceDraft(true);});}
if(element('jellyfinCredentialBootstrapForm'))element('jellyfinCredentialBootstrapForm').onsubmit=async event=>{event.preventDefault();const button=element('bootstrapJellyfinCredential');const manager=element('serviceManager');const error=element('setupError');const username=element('jellyfinAdminUsername')?.value.trim()||'';const password=element('jellyfinAdminPassword')?.value||'';error.textContent='';if(!username||!password){error.textContent='Enter the Jellyfin administrator username and password.';return;}button.disabled=true;button.textContent=button.dataset.busyLabel||'Creating API key…';manager.setAttribute('aria-busy','true');collectConnectionDrafts();const detectBody=new URLSearchParams({enabledServices:JSON.stringify(selectedModules()),vpnProvider:selectedVpnProvider(),connections:JSON.stringify(connectionDrafts)});try{const detectedResponse=await fetch('/api/setup/detect',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:detectBody});const detected=await detectedResponse.json();if(!detectedResponse.ok)throw new Error(detected.error||'Unable to check Jellyfin');setupState=detected;addServiceDraftServerSide=true;addServiceStage='reviewed';Object.values(connectionDrafts).forEach(draft=>{delete draft.apiKey;});const jellyfin=(detected.apps||[]).find(app=>app.id==='jellyfin');if(jellyfin?.credentials){renderSetup();element('confirmSetup')?.focus();return;}if(jellyfin?.action!=='create_api_key')throw new Error(jellyfin?.detail||'Jellyfin is not ready to create an API key');const body=new URLSearchParams({serviceId:'jellyfin',username,password});const response=await fetch('/api/setup/credentials/bootstrap',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to create the Jellyfin API key');setupState=data;renderSetup();const confirm=element('confirmSetup');if(confirm&&!confirm.hidden)confirm.focus();else{const list=element('setupApps');list?.setAttribute('tabindex','-1');list?.focus();}}catch(value){error.textContent=value.message;}finally{if(element('jellyfinAdminUsername'))element('jellyfinAdminUsername').value='';if(element('jellyfinAdminPassword'))element('jellyfinAdminPassword').value='';button.disabled=false;button.textContent='Create and connect';manager.removeAttribute('aria-busy');renderSetup();}};
if(element('detectApps'))element('detectApps').onclick=async()=>{const button=element('detectApps');const manager=element('serviceManager');const error=element('setupError');const module=selectedServiceModule();if(!module)return;error.textContent='';button.disabled=true;button.textContent=button.dataset.busyLabel||'Checking service…';manager.setAttribute('aria-busy','true');addServiceDraftServerSide=true;collectConnectionDrafts();const body=new URLSearchParams({enabledServices:JSON.stringify(selectedModules()),vpnProvider:selectedVpnProvider(),connections:JSON.stringify(connectionDrafts)});try{const response=await fetch('/api/setup/detect',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw new Error(data.error||`Unable to check ${module.name}`);setupState=data;Object.values(connectionDrafts).forEach(draft=>{delete draft.apiKey;});addServiceStage='reviewed';renderSetup();const confirm=element('confirmSetup');if(confirm&&!confirm.hidden)confirm.focus();else{const input=element('directConnectionFields')?.querySelector('input');if(input)input.focus();else{const list=element('setupApps');list.setAttribute('tabindex','-1');list.focus();}}}catch(value){error.textContent=value.message;}finally{manager.removeAttribute('aria-busy');renderSetup();}};
if(element('confirmSetup'))element('confirmSetup').onclick=async()=>{const button=element('confirmSetup');const manager=element('serviceManager');const error=element('setupError');const module=selectedServiceModule();if(!module)return;error.textContent='';button.disabled=true;button.textContent=button.dataset.busyLabel||'Adding service…';manager.setAttribute('aria-busy','true');const body=new URLSearchParams({qbittorrentUsername:element('qbittorrentUsername')?.value||'admin',qbittorrentTemporaryPassword:element('qbittorrentTemporaryPassword')?.value||'',enabledServices:JSON.stringify(selectedModules()),vpnProvider:selectedVpnProvider()});try{const response=await fetch('/api/setup/confirm',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await response.json();if(!response.ok)throw new Error(data.error||`Unable to add ${module.name}`);setupState=data;window.location=button.dataset.completionUrl||'/services';}catch(value){error.textContent=value.message;manager.removeAttribute('aria-busy');renderSetup();}};
if(element('vpnForm'))element('vpnForm').onsubmit=async event=>{event.preventDefault();const error=element('formError');error.textContent='';try{await mutate('/api/vpn/login',{body:new URLSearchParams(new FormData(event.currentTarget))});event.currentTarget.reset();}catch(value){error.textContent=value.message;}};
document.querySelectorAll('[name="librarySource"]').forEach(input=>input.onchange=()=>{setText('libraryResult','');updateLibrarySourceFields();});
if(element('libraryBrowser'))element('libraryBrowser').onclick=event=>{const target=event.target.closest('[data-library-browse-path]');if(target&&!target.disabled)loadLibraryBrowser(target.dataset.libraryBrowsePath,true);};
if(element('libraryBrowserRefresh'))element('libraryBrowserRefresh').onclick=event=>{event.stopPropagation();loadLibraryBrowser(libraryBrowserPath,false);};
if(element('libraryForm'))element('libraryForm').onsubmit=async event=>{event.preventDefault();const error=element('libraryError');const result=element('libraryResult');const button=element('saveLibrary');error.textContent='';result.textContent='';if(!libraryMountsValid){error.textContent='Choose a path mounted at the same location in every media service.';return;}const source=document.querySelector('[name="librarySource"]:checked')?.value||'';const data=new URLSearchParams({libraryKey:event.currentTarget.dataset.libraryKey,source,path:element('libraryPath')?.value||libraryBrowserPath});button.disabled=true;button.textContent='Saving library…';try{await mutate('/api/storage/library',{body:data});await loadStorage();result.textContent='Library configuration saved through the installed app APIs.';}catch(value){error.textContent=value.message;}finally{button.disabled=!libraryMountsValid;button.textContent='Save library';}};
if(element('serviceSearch'))element('serviceSearch').oninput=renderServiceGrid;
if(element('serviceStateFilter'))element('serviceStateFilter').onchange=renderServiceGrid;
const initialLoads=[load(),loadSetup()];if(element('libraryGrid')||element('libraryDetail'))initialLoads.push(loadStorage());
Promise.all(initialLoads).then(openDeepLinkedService).catch(error=>{setText('healthTitle','Status unavailable');setText('healthDetail',error.message);if(element('healthMark'))element('healthMark').className='status-orb failed';});
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
        <div class="notice-head"><span class="notice-symbol" aria-hidden="true">⚠</span><div><h2>Connect your installed apps</h2><p>umbrelarr does not install containers. Detect the supported services you installed, review them, and explicitly allow management.</p></div></div>
        <div class="setup-actions"><span class="setup-feedback">Configuration remains paused until services are reviewed and connected.</span><a class="open-link" href="/services">Manage services →</a></div>
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


SERVICES = r"""
      <div class="fleet-toolbar" aria-label="Service filters">
        <input id="serviceSearch" type="search" placeholder="Search visible services" aria-label="Search visible services">
        <select id="serviceStateFilter" aria-label="Filter by service status"><option value="all">All statuses</option><option value="healthy">Healthy</option><option value="action_required">Action required</option><option value="waiting">Waiting</option><option value="configuring">Configuring</option><option value="failed">Failed</option><option value="unknown">Unknown</option></select>
        <span class="fleet-count"><span id="serviceCount">0 services</span> · API-derived health</span>
        <button id="manageServices" type="button" aria-haspopup="dialog" aria-controls="serviceManager">Add service</button>
      </div>
      <section class="inventory-notice" id="inventoryNotice" role="status" aria-live="polite" hidden><strong id="inventoryNoticeTitle"></strong><span id="inventoryNoticeCopy"></span></section>
      <dialog class="service-setup-dialog" id="serviceManager" aria-labelledby="serviceManagerTitle" aria-describedby="serviceManagerDescription">
        <div class="service-setup-shell">
          <header class="setup-dialog-head">
            <div><span class="setup-dialog-kicker">Add one service</span><h2 id="serviceManagerTitle" tabindex="-1">Add service</h2><p id="serviceManagerDescription">Choose one installed service, connect to its API, then add it to the managed fleet.</p></div>
            <button class="setup-dialog-close" id="closeServiceManager" type="button" aria-label="Close add service setup">×</button>
          </header>
          <nav class="setup-steps" aria-label="Add service progress">
            <span class="setup-step active" data-add-step="choose"><b>1</b>Choose</span>
            <span class="setup-step" data-add-step="connect"><b>2</b>Connect</span>
          </nav>
          <div class="setup-dialog-body">
            <section class="setup-dialog-section" id="serviceChooseStep" aria-labelledby="serviceCatalogTitle">
              <div class="catalog-head"><div><h3 id="serviceCatalogTitle">Available services</h3><p id="serviceTypeSummary">Loading services from the app catalog.</p></div></div>
              <div class="module-grid" id="moduleCatalog"><div class="empty">Loading available services.</div></div>
            </section>
            <section class="setup-dialog-section" id="serviceConnectStep" aria-labelledby="selectedServiceTitle" hidden>
              <button class="change-service" id="changeSelectedService" type="button">← Choose another service</button>
              <div class="selected-service" id="selectedServiceSummary"></div>
              <section class="direct-connections" id="directConnections" aria-labelledby="directConnectionsTitle" hidden>
                <h3 id="directConnectionsTitle">Connect directly</h3>
                <p id="directConnectionsHelp">Enter a service address this process can reach.</p>
                <div class="direct-connection-list" id="directConnectionFields"></div>
                <small class="direct-connection-note" id="directConnectionNote">Secrets are write-only in this screen: existing values are never returned to the browser or shown again.</small>
              </section>
              <section class="credential-bootstrap" id="jellyfinCredentialBootstrap" aria-labelledby="jellyfinCredentialBootstrapTitle" hidden>
                <h3 id="jellyfinCredentialBootstrapTitle">Create a dedicated Jellyfin API key</h3>
                <p>Authenticate once with a Jellyfin administrator account. Jellyfin will create and own a key named <strong>umbrelarr</strong>; the administrator password and temporary session are discarded immediately.</p>
                <form class="credential-bootstrap-form" id="jellyfinCredentialBootstrapForm">
                  <label><span>Jellyfin administrator</span><input id="jellyfinAdminUsername" name="username" autocomplete="username" required aria-describedby="jellyfinCredentialBootstrapHelp"></label>
                  <label><span>Administrator password</span><input id="jellyfinAdminPassword" name="password" type="password" autocomplete="current-password" required aria-describedby="jellyfinCredentialBootstrapHelp"></label>
                  <button class="primary" id="bootstrapJellyfinCredential" type="submit" data-busy-label="Creating API key…">Create and connect</button>
                </form>
                <small class="credential-bootstrap-note" id="jellyfinCredentialBootstrapHelp">These credentials are sent only to the selected Jellyfin API and are never saved by umbrelarr.</small>
              </section>
              <div class="credential-fields" id="qbittorrentCredentials" hidden><label><span>qBittorrent username</span><input id="qbittorrentUsername" value="admin" autocomplete="username"></label><label><span>One-time qBittorrent password</span><input id="qbittorrentTemporaryPassword" type="password" autocomplete="current-password" aria-describedby="qbittorrentPasswordHelp"><small id="qbittorrentPasswordHelp">Only needed when qBittorrent reports a temporary-password action. It stays in memory and is never saved.</small></label></div>
              <div class="attention-list setup-app-list" id="setupApps" aria-live="polite"><div class="empty">Check this service to verify its direct API connection.</div></div>
            </section>
          </div>
          <footer class="setup-dialog-foot">
            <span class="setup-dialog-feedback"><span class="setup-action-help" id="setupActionHelp" role="status" aria-live="polite"></span><span class="error" id="setupError" role="alert"></span></span>
            <button id="cancelServiceChanges" type="button">Cancel</button>
            <button class="primary" id="detectApps" type="button" data-busy-label="Checking service…" hidden>Check service</button>
            <button class="primary" id="confirmSetup" type="button" data-busy-label="Adding service…" data-completion-url="/services" hidden>Add service</button>
          </footer>
        </div>
      </dialog>
      <dialog class="service-setup-dialog service-remove-dialog" id="removeServiceDialog" aria-labelledby="removeServiceTitle" aria-describedby="removeServiceDescription">
        <div class="service-setup-shell">
          <header class="setup-dialog-head">
            <div><span class="setup-dialog-kicker">Remove managed service</span><h2 id="removeServiceTitle" tabindex="-1">Stop managing this service?</h2><p id="removeServiceDescription">Remove this service from the managed fleet.</p></div>
          </header>
          <div class="setup-dialog-body">
            <div class="remove-service-summary" id="removeServiceSummary"></div>
            <p class="remove-service-copy">umbrelarr will stop checking and reconciling this service.</p>
            <div class="safe-removal-note"><strong>The app stays installed.</strong> Its configuration, data, and settings remain in place.</div>
          </div>
          <footer class="setup-dialog-foot">
            <span class="setup-dialog-feedback"><span class="error" id="removeServiceError" role="alert"></span></span>
            <button id="cancelRemoveService" type="button">Cancel</button>
            <button class="danger" id="confirmRemoveService" type="button">Remove service</button>
          </footer>
        </div>
      </dialog>
      <p class="service-action-status" id="serviceActionStatus" role="status" aria-live="polite" hidden></p>
      <section class="service-grid" id="serviceGrid" aria-label="Detected and connected services" aria-live="polite"><div class="empty service-grid-empty">Loading service inventory.</div></section>
"""


LIBRARIES = r"""
      <section class="library-overview" aria-labelledby="libraryOverviewTitle">
        <div><h2 id="libraryOverviewTitle">Your media libraries</h2><p>Each library keeps its own root, download category, and connected services. Open one to review or change its complete managed configuration.</p></div>
        <span class="library-count" id="librarySummary">Loading libraries</span>
      </section>
      <section class="library-grid" id="libraryGrid" aria-label="Managed media libraries" aria-live="polite">
        <div class="empty service-grid-empty">Loading managed libraries.</div>
      </section>
"""


LIBRARY_DETAIL = r"""
      <div id="libraryDetail" data-library-id="%%LIBRARY_ID%%">
        <a class="back-link" href="/libraries">← All libraries</a>
        <section class="library-detail-hero" aria-labelledby="libraryDetailName">
          <div class="library-detail-main"><span id="libraryDetailIcon" aria-hidden="true"></span><div class="library-detail-title"><h2 id="libraryDetailName">Loading library</h2><p id="libraryDetailCopy">Reading the current API-managed configuration.</p></div></div>
          <div class="library-detail-root"><span>Current root</span><code id="libraryDetailRoot">Loading…</code></div>
        </section>
        <div class="library-detail-layout">
          <section class="panel" aria-labelledby="libraryLocationTitle">
            <div class="panel-head"><h2 id="libraryLocationTitle">Library location</h2></div>
            <form class="panel-body" id="libraryForm">
              <fieldset class="library-source-fieldset">
                <legend>Storage source</legend>
                <div class="library-source-options">
                  <label class="library-source-option"><input type="radio" name="librarySource" value="local"><strong>Umbrel storage</strong><small>Use the standard /downloads root.</small></label>
                  <label class="library-source-option"><input type="radio" name="librarySource" value="network"><strong>Network storage</strong><small>Use the matching /network root.</small></label>
                  <label class="library-source-option"><input type="radio" name="librarySource" value="custom"><strong>Browse system</strong><small>Choose any folder visible to this app.</small></label>
                </div>
              </fieldset>
              <div class="filesystem-browser" id="libraryBrowser">
                <div class="filesystem-browser-head">
                  <div class="filesystem-browser-title"><strong>System folders</strong><small id="libraryBrowserService">Loading the service filesystem.</small></div>
                  <div class="filesystem-browser-actions">
                    <button class="filesystem-browser-action" id="libraryBrowserUp" type="button" aria-label="Open parent folder" disabled><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 7-7 7 7M12 5v14"/></svg></button>
                    <button class="filesystem-browser-action" id="libraryBrowserRefresh" type="button" aria-label="Refresh folders"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5M4 18v-5h5"/><path d="M18.2 9A7 7 0 0 0 6.4 6.4L4 9m16 6-2.4 2.6A7 7 0 0 1 5.8 15"/></svg></button>
                  </div>
                </div>
                <nav class="filesystem-breadcrumbs" id="libraryBrowserCrumbs" aria-label="Folder path"><span class="filesystem-message">Loading path…</span></nav>
                <div class="filesystem-list" id="libraryBrowserList" aria-live="polite"><div class="filesystem-message">Loading folders…</div></div>
                <div class="filesystem-browser-foot"><span>Current folder</span><code id="libraryBrowserPath">Loading…</code></div>
                <div class="filesystem-mount-check" id="libraryMountCheck" aria-live="polite"><strong>Same path in every media service</strong><div class="filesystem-mount-summary">Checking service mounts…</div></div>
              </div>
              <input id="libraryPath" type="hidden" value="">
              <div class="panel-actions"><span class="library-feedback"><span class="error" id="libraryError" role="alert"></span><span class="success" id="libraryResult" role="status"></span></span><button class="primary" id="saveLibrary" type="submit">Save library</button></div>
            </form>
          </section>
          <section class="panel" aria-labelledby="libraryConfigTitle">
            <div class="panel-head"><div><h2 id="libraryConfigTitle">Managed configuration</h2><p>The complete configuration umbrelarr reconciles for this library.</p></div></div>
            <div class="panel-body">
              <dl class="library-config-list">
                <div><dt>Storage source</dt><dd id="librarySourceValue">Loading…</dd></div>
                <div><dt>Root folder</dt><dd><code id="libraryRootValue">Loading…</code></dd></div>
                <div><dt>Download category</dt><dd><code id="libraryCategory">Loading…</code></dd></div>
                <div><dt>Connected services</dt><dd><span id="libraryServiceCount">Loading…</span><div id="libraryDetailApps" data-library-apps="%%LIBRARY_KEY%%"></div></dd></div>
              </dl>
            </div>
          </section>
        </div>
      </div>
"""


ACTIVITY = r"""
      <section class="panel">
        <div class="panel-head"><div><h2>Reconciliation activity</h2><p>Credential-safe events from managed configuration runs.</p></div></div>
        <div class="activity-list full" id="events"><div class="empty">No reconciliation activity yet.</div></div>
      </section>
"""


PAGE_META = {
    "overview": ("System", "Current stack state and required setup actions", OVERVIEW),
    "services": ("Services", "API health and status for every managed app", SERVICES),
    "libraries": ("Libraries", "Media libraries and their managed locations", LIBRARIES),
    "activity": ("Activity", "Reconciliation history for this managed stack", ACTIVITY),
}


SERVICE_TITLES = {
    "privado-vpn": "Privado VPN", "flaresolverr": "FlareSolverr", "prowlarr": "Prowlarr",
    "qbittorrent": "qBittorrent", "sabnzbd": "SABnzbd", "sonarr": "Sonarr",
    "sonarr-4k": "Sonarr 4K", "radarr": "Radarr", "radarr-4k": "Radarr 4K",
    "bazarr": "Bazarr", "overseerr": "Overseerr", "profilarr": "Profilarr",
    "umbrelarr": "umbrelarr", "lidarr": "Lidarr", "jellyfin": "Jellyfin", "plex": "Plex",
}


def render_page(page="overview", service_id=None, library_id=None):
    if page == "library":
        if library_id not in LIBRARIES_BY_ID:
            raise ValueError(f"Unknown managed library: {library_id}")
        library = LIBRARIES_BY_ID[library_id]
        title = LIBRARY_TITLES[library_id]
        subtitle = "Library location and managed configuration"
        content = LIBRARY_DETAIL.replace("%%LIBRARY_ID%%", library_id).replace("%%LIBRARY_KEY%%", library["key"])
    elif page not in PAGE_META:
        raise ValueError(f"Unknown dashboard page: {page}")
    else:
        title, subtitle, content = PAGE_META[page]
    result = TEMPLATE.replace("%%PAGE_TITLE%%", title).replace("%%PAGE_SUBTITLE%%", subtitle).replace("%%CONTENT%%", content)
    for destination in ("overview", "services", "libraries", "activity"):
        active = destination == page or (destination == "libraries" and page == "library")
        result = result.replace(f"%%NAV_{destination.upper()}%%", "active" if active else "")
        result = result.replace(f"%%CURRENT_{destination.upper()}%%", 'aria-current="page"' if active else "")
    return result


PAGE = render_page()
