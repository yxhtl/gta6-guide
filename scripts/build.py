#!/usr/bin/env python3
"""
GTA6 Guide - Static Site Generator
Reads CSV data files, applies HTML templates, generates all pages + sitemap.
Usage: python scripts/build.py
"""

import csv
import hashlib
import html as _html
import os
import shutil
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data"

# ---- Helpers ----

class _SafeHTML(str):
    """Marker for pre-escaped HTML — replace_all() won't double-escape it."""
    pass

def safe_html(s):
    """Mark a string as pre-escaped HTML content."""
    return _SafeHTML(s)

def read_csv(name):
    """Read a CSV file and return list of dicts."""
    path = DATA / name
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def read_template(name):
    """Read a template file."""
    with open(TEMPLATES / name, "r", encoding="utf-8") as f:
        return f.read()

def write_page(rel_path, content):
    """Write a generated HTML page."""
    # Prevent path traversal
    if ".." in rel_path or rel_path.startswith(("/", "\\")):
        raise ValueError(f"Invalid path (traversal attempt): {rel_path}")
    out = ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {rel_path}")

def replace_all(text, vars_dict):
    """Replace all {{KEY}} placeholders. HTML-escapes by default; wrap values in safe_html() to skip."""
    for key, val in vars_dict.items():
        if not isinstance(val, _SafeHTML):
            val = _html.escape(str(val))
        text = text.replace("{{" + key + "}}", str(val))
    return text

def make_slug(name):
    """Convert a name to URL-safe slug."""
    slug = name.lower().replace(" ", "-")
    for ch in "'\"/.?&%#@(),;:+*=^~`<>[]{}|\\":
        slug = slug.replace(ch, "")
    return slug

def hash_seed(name):
    """Get a deterministic variant number (0-2) from a name string.
    Same name always gets same variant — pages don't change on rebuild."""
    h = hashlib.md5(name.encode()).hexdigest()
    return int(h[:8], 16) % 3

# Mission body variants — changes paragraph structure for HCU diversity
MISSION_VARIANT = {
    0: {"obj_heading": "Mission Objectives", "tips_heading": "Tips"},
    1: {"obj_heading": "Walkthrough Steps", "tips_heading": "Pro Tips"},
    2: {"obj_heading": "What You Need to Do", "tips_heading": "Strategy Guide"},
}

# Mission meta description variants
MISSION_DESC = [
    lambda r: f"Complete walkthrough for {r['mission_name']} in GTA6. Chapter: {r.get('chapter','?')}. {r.get('tips','')[:120]}",
    lambda r: f"GTA6 mission guide: {r['mission_name']} — full step-by-step walkthrough. Difficulty: {r.get('difficulty','Normal')} | Reward: {r.get('reward','TBD')}. All objectives covered.",
    lambda r: f"How to beat {r['mission_name']} in GTA6. {r.get('difficulty','Normal')} difficulty mission in {r.get('chapter','?')}. Complete objectives and strategy guide.",
]

# Item body variants — changes section order and heading phrasing
ITEM_VARIANT = {
    0: {"acq_heading": "How to Get It", "desc_pos": "after-stats"},
    1: {"acq_heading": "Where to Find It", "desc_pos": "before-stats"},
    2: {"acq_heading": "Acquisition Method", "desc_pos": "after-stats"},
}

# Item meta description variants
ITEM_DESC = [
    lambda r, cat: f"Stats, location, and how to get {r.get('name','')} in GTA6. {r.get('description','')[:120]}",
    lambda r, cat: f"GTA6 {cat} guide: {r.get('name','')} — complete stats, spawn location, and tips. {r.get('description','')[:100]}",
    lambda r, cat: f"Where to find the {r.get('name','')} in GTA6. Full {cat.lower()} stats, acquisition method, and pro strategies.",
]

# ---- Page generators ----

def gen_mission(row, i, prev_filename, next_filename):
    """Generate a single mission page with randomized paragraph structure."""
    tpl = read_template("mission.html")
    slug = make_slug(row.get("mission_name", f"mission-{i+1}"))
    filename = f"mission-{str(i+1).zfill(2)}-{slug}.html"
    seed = hash_seed(row.get("mission_name", ""))
    v = MISSION_VARIANT[seed]

    steps_html = ""
    for s in row.get("steps", "").split("|"):
        s = s.strip()
        if s:
            steps_html += f"<li>{_html.escape(s)}</li>\n"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>{v['tips_heading']}</h2>\n<div class=\"tip\">{_html.escape(tips)}</div>"

    trivia = row.get("trivia", "").strip()
    trivia_html = ""
    if trivia:
        trivia_html = f"<h2>Trivia</h2>\n<p>{_html.escape(trivia)}</p>"

    # Assemble body with different section order per variant
    steps_block = f"<h2>{v['obj_heading']}</h2>\n<ol class=\"step-list\">\n{steps_html}</ol>"
    if seed == 0:
        # Standard: objectives → tips → trivia
        mission_body = f"{steps_block}\n{tips_html}\n{trivia_html}"
    elif seed == 1:
        # Trivia-after-objectives: objectives → trivia → tips (tips last as "Pro Tips" punch)
        mission_body = f"{steps_block}\n{trivia_html}\n{tips_html}"
    else:
        # Story-first: summary paragraph → objectives → combined tips+trivia
        summary = f"<p>This mission takes place in <strong>{_html.escape(row.get('chapter','?'))}</strong> and is rated <strong>{_html.escape(row.get('difficulty','Normal'))}</strong>. Completing it rewards you with <strong>{_html.escape(row.get('reward','TBD'))}</strong>.</p>"
        combined = tips_html + "\n" + trivia_html if tips_html or trivia_html else ""
        mission_body = f"{summary}\n{steps_block}\n{combined}"

    prev_html = ""
    if prev_filename:
        prev_html = f'<a href="{prev_filename}">← Previous Mission</a>'
    next_html = ""
    if next_filename:
        next_html = f'<a href="{next_filename}">Next Mission →</a>'

    vars_dict = {
        "TITLE": row["mission_name"],
        "DESCRIPTION": MISSION_DESC[seed](row),
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "MISSION_NAME": row["mission_name"],
        "CHAPTER": row.get("chapter", "TBD"),
        "DIFFICULTY": row.get("difficulty", "Normal"),
        "REWARD": row.get("reward", "TBD"),
        "MISSION_BODY": safe_html(mission_body),
        "MISSIONS_ACTIVE": safe_html(' class="active"'),
        "PARENT_SLUG": "story-missions",
        "PARENT_LABEL": "Missions",
        "PREV_LINK": safe_html(prev_html),
        "NEXT_LINK": safe_html(next_html),
        "OG_URL": f"story-missions/{filename}",
        "OG_TYPE": "article",
    }
    write_page(f"story-missions/{filename}", replace_all(tpl, vars_dict))
    return {
        "name": row["mission_name"],
        "chapter": row.get("chapter", "TBD"),
        "filename": filename,
    }

def gen_item(row, category):
    """Generate a single weapon or vehicle page with randomized paragraph structure."""
    tpl = read_template("item.html")
    name = row.get("name", "Unknown Item")
    slug = make_slug(name)
    seed = hash_seed(name)
    v = ITEM_VARIANT[seed]
    cat_lower = category.lower()

    # Build stats grid
    stats_html = ""
    for key, val in row.items():
        if key in ("name", "type_tag", "description", "acquisition", "tips"):
            continue
        if val and val.strip():
            stats_html += f'<div class="stat-item"><div class="stat-label">{_html.escape(key.replace("_"," ").title())}</div><div class="stat-value">{_html.escape(val)}</div></div>\n'

    desc_text = row.get("description", f"Stats and details for {_html.escape(name)} in GTA6.")
    desc_html = f"<p>{_html.escape(desc_text)}</p>"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>Tips</h2>\n<div class=\"tip\">{_html.escape(tips)}</div>"

    acq_text = row.get("acquisition", "TBD — game not yet released.")
    acq_block = f"<h2>{v['acq_heading']}</h2>\n<p>{_html.escape(acq_text)}</p>"

    # Assemble body with different section order per variant
    stats_block = f"<div class=\"stats-grid\">\n{stats_html}</div>"
    if seed == 0:
        # Standard: stats → description → acquisition → tips
        item_body = f"{stats_block}\n{desc_html}\n{acq_block}\n{tips_html}"
    elif seed == 1:
        # Description-first: description → stats → acquisition → tips
        item_body = f"{desc_html}\n{stats_block}\n{acq_block}\n{tips_html}"
    else:
        # Acquisition-first: acquisition → stats → description → tips
        item_body = f"{acq_block}\n{stats_block}\n{desc_html}\n{tips_html}"

    weapons_active = ' class="active"' if category == "Weapons" else ""
    vehicles_active = ' class="active"' if category == "Vehicles" else ""
    out_dir = "weapons" if category == "Weapons" else "vehicles"
    filename = f"{slug}.html"

    vars_dict = {
        "TITLE": f"{name} - GTA6 {category}",
        "DESCRIPTION": ITEM_DESC[seed](row, category),
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "ITEM_NAME": name,
        "CATEGORY": category,
        "CATEGORY_LOWER": cat_lower,
        "TYPE_TAG": row.get("type_tag", category),
        "ITEM_BODY": safe_html(item_body),
        "WEAPONS_ACTIVE": safe_html(weapons_active),
        "VEHICLES_ACTIVE": safe_html(vehicles_active),
        "OG_URL": f"{out_dir}/{filename}",
        "OG_TYPE": "article",
    }
    write_page(f"{out_dir}/{filename}", replace_all(tpl, vars_dict))
    return {"name": name, "type_tag": row.get("type_tag", ""), "filename": filename}

def gen_collectible(row):
    """Generate a single collectible page using item template but with collectible-specific layout."""
    tpl = read_template("item.html")
    name = row.get("name", "Unknown Collectible")
    slug = make_slug(name)
    filename = f"{slug}.html"
    seed = hash_seed(name)
    v = ITEM_VARIANT[seed]

    area = row.get("area", "TBD")
    type_tag = row.get("type_tag", "Collectible")
    reward = row.get("reward", "TBD")
    desc_text = row.get("description", f"Where to find {_html.escape(name)} in GTA6.")
    acq_text = row.get("acquisition", "TBD — game not yet released.")
    tips = row.get("tips", "").strip()

    # Stats grid tailored for collectibles
    stats_html = f'<div class="stat-item"><div class="stat-label">Area</div><div class="stat-value">{_html.escape(area)}</div></div>\n'
    stats_html += f'<div class="stat-item"><div class="stat-label">Type</div><div class="stat-value">{_html.escape(type_tag)}</div></div>\n'
    stats_html += f'<div class="stat-item"><div class="stat-label">Reward</div><div class="stat-value">{_html.escape(reward)}</div></div>\n'

    desc_html = f"<p>{_html.escape(desc_text)}</p>"
    tips_html = ""
    if tips:
        tips_html = f"<h2>Tips</h2>\n<div class=\"tip\">{_html.escape(tips)}</div>"

    acq_block = f"<h2>{v['acq_heading']}</h2>\n<p>{_html.escape(acq_text)}</p>"
    stats_block = f"<div class=\"stats-grid\">\n{stats_html}</div>"

    if seed == 0:
        item_body = f"{stats_block}\n{desc_html}\n{acq_block}\n{tips_html}"
    elif seed == 1:
        item_body = f"{desc_html}\n{stats_block}\n{acq_block}\n{tips_html}"
    else:
        item_body = f"{acq_block}\n{stats_block}\n{desc_html}\n{tips_html}"

    vars_dict = {
        "TITLE": f"{name} Location - GTA6 Collectibles",
        "DESCRIPTION": ITEM_DESC[seed]({"name": name, "description": desc_text}, "Collectibles"),
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "ITEM_NAME": name,
        "CATEGORY": "Collectibles",
        "CATEGORY_LOWER": "collectibles",
        "TYPE_TAG": type_tag,
        "ITEM_BODY": safe_html(item_body),
        "WEAPONS_ACTIVE": safe_html(""),
        "VEHICLES_ACTIVE": safe_html(""),
        "OG_URL": f"collectibles/{filename}",
        "OG_TYPE": "article",
    }
    write_page(f"collectibles/{filename}", replace_all(tpl, vars_dict))
    return {"name": name, "type_tag": type_tag, "filename": filename}

def gen_side_mission(row, i, prev_filename, next_filename):
    """Generate a single side mission page — reuses mission template with randomized structure."""
    tpl = read_template("mission.html")
    slug = make_slug(row.get("mission_name", f"side-{i+1}"))
    filename = f"side-{str(i+1).zfill(2)}-{slug}.html"
    seed = hash_seed(row.get("mission_name", ""))
    v = MISSION_VARIANT[seed]

    steps_html = ""
    for s in row.get("steps", "").split("|"):
        s = s.strip()
        if s:
            steps_html += f"<li>{_html.escape(s)}</li>\n"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>{v['tips_heading']}</h2>\n<div class=\"tip\">{_html.escape(tips)}</div>"

    trivia = row.get("trivia", "").strip()
    trivia_html = ""
    if trivia:
        trivia_html = f"<h2>Trivia</h2>\n<p>{_html.escape(trivia)}</p>"

    steps_block = f"<h2>{v['obj_heading']}</h2>\n<ol class=\"step-list\">\n{steps_html}</ol>"
    if seed == 0:
        mission_body = f"{steps_block}\n{tips_html}\n{trivia_html}"
    elif seed == 1:
        mission_body = f"{steps_block}\n{trivia_html}\n{tips_html}"
    else:
        summary = f"<p>This side mission is available from <strong>{row.get('chapter','?')}</strong> and is rated <strong>{row.get('difficulty','Normal')}</strong>. Completing it rewards you with <strong>{row.get('reward','TBD')}</strong>.</p>"
        combined = tips_html + "\n" + trivia_html if tips_html or trivia_html else ""
        mission_body = f"{summary}\n{steps_block}\n{combined}"

    prev_html = ""
    if prev_filename:
        prev_html = f'<a href="{prev_filename}">← Previous Mission</a>'
    next_html = ""
    if next_filename:
        next_html = f'<a href="{next_filename}">Next Mission →</a>'

    vars_dict = {
        "TITLE": row["mission_name"],
        "DESCRIPTION": MISSION_DESC[seed](row),
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "MISSION_NAME": row["mission_name"],
        "CHAPTER": row.get("chapter", "TBD"),
        "DIFFICULTY": row.get("difficulty", "Normal"),
        "REWARD": row.get("reward", "TBD"),
        "MISSION_BODY": safe_html(mission_body),
        "MISSIONS_ACTIVE": safe_html(""),
        "PARENT_SLUG": "side-missions",
        "PARENT_LABEL": "Side Missions",
        "PREV_LINK": safe_html(prev_html),
        "NEXT_LINK": safe_html(next_html),
        "OG_URL": f"side-missions/{filename}",
        "OG_TYPE": "article",
    }
    write_page(f"side-missions/{filename}", replace_all(tpl, vars_dict))
    return {
        "name": row["mission_name"],
        "chapter": row.get("chapter", "TBD"),
        "filename": filename,
    }

def gen_index(category_name, items, css_path="", home_path=""):
    """Generate a category index page."""
    tpl = read_template("index-template.html")
    item_list = ""
    if items:
        for item in items:
            extra = f" — {_html.escape(item.get('chapter', item.get('type_tag', '')))}" if item.get("chapter") or item.get("type_tag") else ""
            item_list += f'<li><a href="{item["filename"]}"><span class="item-name">{_html.escape(item["name"])}</span><span class="item-meta">{extra}</span></a></li>\n'
    else:
        item_list = '<div class="disclaimer">GTA6 is not yet released. Content for this category will be added after the game launches. Bookmark this page and check back after release!</div>'

    missions_active = ' class="active"' if "Mission" in category_name else ""
    weapons_active = ' class="active"' if "Weapon" in category_name else ""
    vehicles_active = ' class="active"' if "Vehicle" in category_name else ""

    cat_slug = category_name.lower().replace(" ", "-")
    desc = f"Complete list of all {category_name.lower()} in GTA6."

    vars_dict = {
        "TITLE": f"All {category_name}",
        "DESCRIPTION": desc,
        "CSS_PATH": css_path,
        "HOME_PATH": home_path,
        "CATEGORY_NAME": category_name,
        "CATEGORY_DESC": desc,
        "ITEM_LIST": safe_html(item_list),
        "MISSIONS_ACTIVE": safe_html(missions_active),
        "WEAPONS_ACTIVE": safe_html(weapons_active),
        "VEHICLES_ACTIVE": safe_html(vehicles_active),
        "OG_URL": f"{cat_slug}/",
        "OG_TYPE": "website",
    }
    write_page(f"{cat_slug}/index.html", replace_all(tpl, vars_dict))

def gen_generic(filename, title, h1, meta, content, active_nav=""):
    """Generate a generic content page (cheats, money guide, etc.)."""
    tpl = read_template("generic.html")
    preorder_active = ' class="active"' if active_nav == "preorder" else ""
    cheats_active = ' class="active"' if active_nav == "cheats" else ""
    money_active = ' class="active"' if active_nav == "money" else ""

    # Compute relative path prefix based on directory depth
    depth = filename.count("/")
    rel = "../" * depth if depth > 0 else ""

    # Compute OG URL: strip trailing index.html for cleaner social share URLs
    og_url = filename
    if og_url.endswith("index.html"):
        og_url = og_url[:-10]  # strip "index.html", keep directory

    vars_dict = {
        "TITLE": title,
        "DESCRIPTION": f"{h1} — comprehensive GTA6 guide. {meta}",
        "CSS_PATH": rel,
        "HOME_PATH": rel,
        "PAGE_TITLE": h1,
        "H1": h1,
        "META": meta,
        "CONTENT": safe_html(content),
        "PREORDER_ACTIVE": safe_html(preorder_active),
        "CHEATS_ACTIVE": safe_html(cheats_active),
        "MONEY_ACTIVE": safe_html(money_active),
        "OG_URL": og_url,
        "OG_TYPE": "article",
    }
    write_page(filename, replace_all(tpl, vars_dict))

def gen_sitemap(pages):
    """Generate sitemap.xml."""
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    base = "https://gta6.yxhtl.com"
    for page in pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{base}/{page}</loc>")
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append(f"    <priority>{'1.0' if page == '' else '0.8'}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    write_page("sitemap.xml", "\n".join(lines))

def gen_robots():
    """Generate robots.txt."""
    content = "User-agent: *\nAllow: /\nSitemap: https://gta6.yxhtl.com/sitemap.xml\n"
    write_page("robots.txt", content)

def gen_homepage():
    """Generate the homepage."""
    tpl = read_template("generic.html")
    vars_dict = {
        "TITLE": "GTA6 Guide — Pre-Order, Cheats, Missions, Weapons & More",
        "DESCRIPTION": "GTA6 pre-order guide, cheats, money tips, all story missions, weapons, vehicles, and collectibles. Pre-orders open June 25, 2026. Updated regularly.",
        "CSS_PATH": "",
        "HOME_PATH": "",
        "PAGE_TITLE": "Home",
        "H1": "GTA6 Guide",
        "META": "Your ultimate resource for Grand Theft Auto VI",
        "CONTENT": safe_html(f"""<div class="preorder-hero">
  <div class="preorder-hero-badge">🔥 Pre-orders Open June 25, 2026</div>
  <h2 class="preorder-hero-title">Grand Theft Auto VI</h2>
  <p class="preorder-hero-platforms">PS5 · Xbox Series X|S · PC (date TBA)</p>
  <a href="pre-order.html" class="preorder-hero-cta">View Pre-Order Guide →</a>
</div>

<div class="home-sections">
  <div class="home-section">
    <h2>🛒 Pre-Order GTA6</h2>
    <p>Pre-orders open June 25. Edition comparison, price estimates, and where to buy across all platforms.</p>
    <a href="pre-order.html" class="home-section-link">Pre-Order Guide →</a>
  </div>
  <div class="home-section">
    <h2>📋 Game Guides</h2>
    <p>Story missions, cheats, money making, weapons, vehicles — everything you need when the game drops.</p>
  </div>
</div>

<div class="disclaimer">
  GTA6 is not yet released. We will update all pages with accurate data as soon as the game launches. Bookmark us and check back!
</div>

<div class="category-grid">
  <a href="story-missions/index.html" class="category-card">
    <h3>📋 Story Missions</h3>
    <p>Complete walkthrough for every main story mission</p>
    <span class="card-badge">Coming Soon</span>
  </a>
  <a href="weapons/index.html" class="category-card">
    <h3>🔫 Weapons</h3>
    <p>Stats, locations, and tips for every weapon</p>
    <span class="card-badge">Coming Soon</span>
  </a>
  <a href="vehicles/index.html" class="category-card">
    <h3>🚗 Vehicles</h3>
    <p>Complete vehicle catalog with stats and spawns</p>
    <span class="card-badge">Coming Soon</span>
  </a>
  <a href="cheats.html" class="category-card">
    <h3>🎮 Cheats</h3>
    <p>GTA5 cheat codes reference — GTA6 codes will be added after launch</p>
  </a>
  <a href="money-guide.html" class="category-card">
    <h3>💰 Money Guide</h3>
    <p>Proven money-making strategies — detailed data will be updated after launch</p>
  </a>
  <a href="collectibles/index.html" class="category-card">
    <h3>📍 Collectibles</h3>
    <p>Every hidden item location</p>
    <span class="card-badge">Coming Soon</span>
  </a>
  <a href="side-missions/index.html" class="category-card">
    <h3>📌 Side Missions</h3>
    <p>All side missions and strangers</p>
    <span class="card-badge">Coming Soon</span>
  </a>
  <a href="online/index.html" class="category-card">
    <h3>🌐 GTA Online</h3>
    <p>GTA5 Online reference + GTA6 Online preview</p>
  </a>
</div>"""),
        "PREORDER_ACTIVE": safe_html(""),
        "CHEATS_ACTIVE": safe_html(""),
        "MONEY_ACTIVE": safe_html(""),
        "OG_URL": "",
        "OG_TYPE": "website",
    }
    write_page("index.html", replace_all(tpl, vars_dict))


# ---- Main ----

def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("Building GTA6 Guide...\n")

    # 0. Clean old generated html files
    for d in ["story-missions", "weapons", "vehicles", "collectibles", "side-missions"]:
        dir_path = ROOT / d
        if dir_path.exists():
            for f in dir_path.glob("*.html"):
                f.unlink()
                print(f"  [CLEAN] {d}/{f.name}")

    # 1. Generate mission pages
    missions = read_csv("missions.csv")
    # First pass: compute all filenames
    mission_filenames = []
    for i, row in enumerate(missions):
        slug = make_slug(row["mission_name"])
        mission_filenames.append(f"mission-{str(i+1).zfill(2)}-{slug}.html")
    # Second pass: generate with correct prev/next links
    mission_items = []
    for i, row in enumerate(missions):
        prev_fn = mission_filenames[i-1] if i > 0 else ""
        next_fn = mission_filenames[i+1] if i < len(missions) - 1 else ""
        item = gen_mission(row, i, prev_fn, next_fn)
        mission_items.append(item)

    gen_index("Story Missions", mission_items, css_path="../", home_path="../")

    # 2. Generate weapon pages
    weapons = read_csv("weapons.csv")
    weapon_items = []
    for row in weapons:
        item = gen_item(row, "Weapons")
        weapon_items.append(item)

    gen_index("Weapons", weapon_items, css_path="../", home_path="../")

    # 3. Generate vehicle pages
    vehicles = read_csv("vehicles.csv")
    vehicle_items = []
    for row in vehicles:
        item = gen_item(row, "Vehicles")
        vehicle_items.append(item)

    gen_index("Vehicles", vehicle_items, css_path="../", home_path="../")

    # 4. Generate collectible pages
    collectibles = read_csv("collectibles.csv")
    collectible_items = []
    for row in collectibles:
        item = gen_collectible(row)
        collectible_items.append(item)

    gen_index("Collectibles", collectible_items, css_path="../", home_path="../")

    # 5. Generate side mission pages
    side_missions_raw = read_csv("side-missions.csv")
    side_filenames = []
    for i, row in enumerate(side_missions_raw):
        slug = make_slug(row["mission_name"])
        side_filenames.append(f"side-{str(i+1).zfill(2)}-{slug}.html")
    side_items = []
    for i, row in enumerate(side_missions_raw):
        prev_fn = side_filenames[i-1] if i > 0 else ""
        next_fn = side_filenames[i+1] if i < len(side_missions_raw) - 1 else ""
        item = gen_side_mission(row, i, prev_fn, next_fn)
        side_items.append(item)

    gen_index("Side Missions", side_items, css_path="../", home_path="../")

    # 6. Generate cheats page (GTA5 reference + expected GTA6 categories)
    gen_generic("cheats.html",
        title="GTA6 Cheats & Cheat Codes — Full List",
        h1="GTA6 Cheats & Cheat Codes",
        meta="Complete list of GTA6 cheat codes. Includes GTA5 reference cheats and confirmed GTA6 codes. God mode, weapons, vehicles, wanted level, money cheats.",
        content="""<div class="disclaimer">
  GTA6 cheat codes will be added here as soon as the game releases. For now, we include all GTA5 cheats as reference — Rockstar almost always keeps the same cheat input system across titles.
</div>

<h2>How GTA Cheats Work</h2>
<p>Since GTA4, Rockstar has used an in-game <strong>cell phone dial system</strong> for cheat codes. You bring up your phone, dial a number, and the cheat activates. Before that (GTA3/VC/SA era), cheats were entered via button combinations on the controller.</p>
<p>GTA6 is expected to continue the cell phone system. The exact numbers will change, but many cheat <em>categories</em> carry over from game to game.</p>

<h2>GTA5 Cheat Codes (Reference)</h2>
<p>These are the GTA5 cheat codes. GTA6 will likely have similar codes with different phone numbers. Bookmark this page — we'll update within hours of launch.</p>

<table>
  <thead>
    <tr><th>Cheat</th><th>GTA5 Phone Number</th><th>Effect</th></tr>
  </thead>
  <tbody>
    <tr><td>Invincibility (5 min)</td><td><code class="cheat-code">1-999-7246-545-537</code></td><td>God mode, lasts 5 minutes</td></tr>
	    <tr><td>Max Health & Armor</td><td><code class="cheat-code">1-999-887-853</code></td><td>Full health and armor refill</td></tr>
	    <tr><td>All Weapons & Ammo</td><td><code class="cheat-code">1-999-866-587</code></td><td>Spawns all weapons with full ammo</td></tr>
	    <tr><td>Recharge Special Ability</td><td><code class="cheat-code">1-999-769-3787</code></td><td>Instantly refill special ability bar</td></tr>
	    <tr><td>Raise Wanted Level</td><td><code class="cheat-code">1-999-3844-8483</code></td><td>Add one wanted star</td></tr>
	    <tr><td>Lower Wanted Level</td><td><code class="cheat-code">1-999-5299-3787</code></td><td>Remove one wanted star</td></tr>
	    <tr><td>Super Jump</td><td><code class="cheat-code">1-999-467-8648</code></td><td>Jump 10x higher</td></tr>
	    <tr><td>Fast Run</td><td><code class="cheat-code">1-999-228-8463</code></td><td>Sprint significantly faster</td></tr>
	    <tr><td>Fast Swim</td><td><code class="cheat-code">1-999-4684-4557</code></td><td>Swim at double speed</td></tr>
	    <tr><td>Skyfall</td><td><code class="cheat-code">1-999-759-3255</code></td><td>Spawn in the sky, freefall to ground</td></tr>
	    <tr><td>Explosive Bullets</td><td><code class="cheat-code">1-999-444-439</code></td><td>Bullets explode on impact</td></tr>
	    <tr><td>Flaming Bullets</td><td><code class="cheat-code">1-999-462-363-4279</code></td><td>Bullets set targets on fire</td></tr>
	    <tr><td>Explosive Melee</td><td><code class="cheat-code">1-999-4684-2637</code></td><td>Punches cause explosions</td></tr>
	    <tr><td>Slow Motion Aim</td><td><code class="cheat-code">1-999-332-3393</code></td><td>Slow-mo while aiming (enter again for lv2/3, 4th to disable)</td></tr>
	    <tr><td>Slow Motion (world)</td><td><code class="cheat-code">1-999-756-966</code></td><td>Entire world in slow motion (enter 3x for levels, 4th to disable)</td></tr>
	    <tr><td>Spawn Buzzard</td><td><code class="cheat-code">1-999-2899-633</code></td><td>Spawns armed attack helicopter</td></tr>
	    <tr><td>Spawn Comet</td><td><code class="cheat-code">1-999-266-38</code></td><td>Spawns Comet sports car</td></tr>
	    <tr><td>Spawn Sanchez</td><td><code class="cheat-code">1-999-633-7623</code></td><td>Spawns Sanchez off-road dirt bike</td></tr>
	    <tr><td>Spawn BMX</td><td><code class="cheat-code">1-999-226-348</code></td><td>Spawns BMX bicycle</td></tr>
	    <tr><td>Spawn Stunt Plane</td><td><code class="cheat-code">1-999-227-678-676</code></td><td>Spawns fixed-wing stunt plane</td></tr>
	    <tr><td>Parachute</td><td><code class="cheat-code">1-999-759-3483</code></td><td>Gives a parachute</td></tr>
	    <tr><td>Moon Gravity</td><td><code class="cheat-code">1-999-356-2837</code></td><td>Low gravity for all vehicles and characters</td></tr>
	    <tr><td>Slippery Cars</td><td><code class="cheat-code">1-999-7669-329</code></td><td>All cars drift like they're on ice</td></tr>
	    <tr><td>Change Weather</td><td><code class="cheat-code">1-999-625-348-7246</code></td><td>Cycle through weather types</td></tr>
	    <tr><td>Drunk Mode</td><td><code class="cheat-code">1-999-547-867</code></td><td>Character stumbles and sways as if drunk</td></tr>

	  </tbody>
	</table>
<div class="tip">GTA5 cheats disable achievements/trophies when active. GTA6 will likely have the same restriction — save before using cheats.</div>

<h2>What to Expect for GTA6 Cheats</h2>
<p>GTA6 is not yet released — no cheat codes can be confirmed. The information below is based on GTA series tradition and will be updated after launch.</p>
<p>This page will be updated with community-discovered GTA6 cheat codes within 24-48 hours of release.</p>

<h2>Why Cheats Get Discovered Fast</h2>
<p>Rockstar phone cheats follow a predictable pattern — the numbers spell words on a phone keypad. For example, GTA5'S invincibility number <code class="cheat-code">1-999-7246-545-537</code> spells <code class="cheat-code">1-999-PAIN-KILLER</code>. The community typically reverse-engineers all phone cheats within <strong>24-48 hours</strong> of release by brute-forcing common word combinations.</p>

<p>We monitor cheat discovery threads on Reddit, GTAForums, and Twitter/X in real time during launch week. <strong>This page will be updated within hours of the first confirmed GTA6 cheat codes.</strong></p>""",
        active_nav="cheats")

    # 7. Generate money guide (expanded strategies)
    gen_generic("money-guide.html",
        title="GTA6 Money Guide — How to Make Money Fast (Best Methods)",
        h1="GTA6 Money Guide — How to Make Money Fast",
        meta="Best ways to earn money fast in GTA6: heists, stock market manipulation, side businesses, vehicle exports, collectible hunting. Detailed strategies and payout estimates.",
        content="""<div class="disclaimer">
  GTA6 is not yet released. Specific money-making methods and payout figures will be updated within the first week after launch. The content below is based on GTA series history and confirmed GTA6 public information.
</div>

<h2>GTA Series Money-Making Fundamentals</h2>
<p>These are the core money-making patterns across every GTA title — GTA6 will likely continue these systems, but specific numbers and mechanics are subject to change after launch. Each method includes <strong>why it works</strong> and <strong>what to verify after launch</strong>, so you can hit the ground running on day one.</p>

<div class="card">
  <h3>💰 1. Story Missions</h3>
  <p>Main story missions are the primary income source in any GTA game. In GTA5, completing all 69 story missions yields roughly <strong>$30-40M</strong> (including heist cuts). Late-game heists can pay <strong>$20M+</strong> each (The Big Score, obvious approach).</p>
  <p><strong>Key strategy:</strong> Some missions let you choose between approaches (e.g. GTA5's "obvious" vs "subtle") that affect your final payout. Manual-save before the mission, compare both outcomes — the subtle approach usually means fewer people taking a cut, so you keep more.</p>
  <p><strong>Post-launch verification:</strong> Which missions pay the most? Which have approach choices? Which approach yields the highest net (after crew cuts)?</p>
</div>

<div class="card">
  <h3>📈 2. Stock Market Manipulation</h3>
  <p>GTA5 introduced a player-influenced stock market — LCN (single-player) and BAWSAQ (online). The core mechanic: <strong>buy affected stocks BEFORE a mission, sell AFTER the mission when prices spike</strong>.</p>
  <p>GTA5 classic examples:</p>
  <ul>
    <li><strong>Before LifeInvader mission:</strong> short LifeInvader → stock crashes after mission → profit</li>
    <li><strong>Before Hotel Assassination:</strong> buy Betta Pharmaceuticals → rises 50%+ after mission</li>
    <li><strong>Before The Multi Target Assassination:</strong> go all-in on Debonaire → rises 80%, switch to Redwood → rises 300%</li>
  </ul>
  <p>If GTA6 keeps this system (highly likely — Rockstar has no reason to cut a universally praised mechanic), stock manipulation will be <strong>the single most profitable money-making method in the entire game</strong>.</p>
  <p><strong>Post-launch verification:</strong> What's in the LCN stock pool? Which missions affect which stocks? How big are the price swings? When is the optimal buy-in point (which checkpoint before the mission)?</p>
</div>

<div class="card">
  <h3>🏢 3. Properties &amp; Businesses</h3>
  <p>The GTA series has had a property system since Vice City — buy a business, complete its unique missions, and it starts generating recurring income.</p>
  <p>Classic GTA Vice City examples:</p>
  <ul>
    <li><strong>Malibu Club</strong> — $120K purchase, $10K/week after missions</li>
    <li><strong>Cherry Popper Ice Cream</strong> — $20K purchase, $3K/week after missions</li>
    <li><strong>Print Works</strong> — $70K purchase, $8K/week after missions (final asset in the game)</li>
  </ul>
  <p>GTA5 simplified properties to "buy and earn" with no missions required. GTA6 will likely return to the Vice City model of "buy property → complete missions → collect income," since it's set in a new Vice City and paying homage to the original makes perfect sense.</p>
  <p><strong>Post-launch verification:</strong> How many purchasable properties? Which have the best ROI? How many missions until each one "pays for itself"?</p>
</div>

<div class="card">
  <h3>🚗 4. Vehicle Export</h3>
  <p>Stealing and selling high-end vehicles has been a staple GTA money-maker since GTA1. GTA Online's Import/Export update turned it into one of the most profitable solo activities.</p>
  <p>GTA6 is set in Vice City (Miami) — expect very high luxury car density in wealthy areas (Starfish Island, Vice Beach coastline). If single-player has an I/E-like system:</p>
  <ul>
    <li>High-end sports cars (Infernus, Cheetah tier) → est. $80K-$150K each</li>
    <li>Luxury sedans → est. $40K-$80K each</li>
    <li>Sell after modding → +20%-50% value (GTA5's Los Santos Customs logic)</li>
  </ul>
  <p><strong>Post-launch verification:</strong> Is there a dedicated export mission line? Where do the highest-value cars spawn? What's the modding value multiplier?</p>
</div>

<div class="card">
  <h3>🏪 5. Robberies &amp; Random Events</h3>
  <p>GTA5's convenience store robberies only paid a few hundred to a thousand dollars — not great ROI. But GTA6 may significantly expand this system:</p>
  <ul>
    <li><strong>Convenience stores</strong> — quick $200-$2K cash, low risk</li>
    <li><strong>Armored trucks</strong> — random spawns, $5K-$25K (GTA5 logic)</li>
    <li><strong>Random events</strong> — returning wallets, giving rides, chasing thieves, $500-$10K, some unlock special rewards</li>
    <li><strong>ATM muggings</strong> — if GTA6 NPCs use ATMs, follow and rob them after they withdraw</li>
  </ul>
  <p><strong>Post-launch verification:</strong> Armored truck spawn points and payout range? Which random events give the best rewards? Any hidden special random events?</p>
</div>

<div class="card">
  <h3>📦 6. Collectibles</h3>
  <p>Every GTA has hidden collectibles — find enough and you get cash rewards plus special vehicles:</p>
  <ul>
    <li>GTA Vice City — 100 hidden packages → $100K + Hunter helicopter + Rhino tank</li>
    <li>GTA SA — 100 tags + 50 photos + 50 horseshoes + 50 oysters → $300K+ total</li>
    <li>GTA5 — 50 letter scraps + 50 spaceship parts + 30 nuclear waste + 50 signal jammers → $1.5M+ total</li>
  </ul>
  <p>The best thing about collectibles: <strong>zero risk</strong> — no shooting, no wanted levels, just explore and collect. GTA6's map is larger than GTA5's, so expect a new record for collectible count.</p>
  <p><strong>Post-launch verification:</strong> What types of collectibles exist? Total count? Rewards at each milestone? Does 100% completion unlock a special mission like GTA5?</p>
</div>

<div class="card">
  <h3>🏎️ 7. Repeatable Races &amp; Activities</h3>
  <p>Street races, triathlons, parachuting, golf, tennis — GTA5's side activities may pay slowly, but they're infinitely repeatable:</p>
  <ul>
    <li>Street races — 1st place $1K-$5K, low risk</li>
    <li>Triathlons — 1st place $5K-$15K, but 20-30 minutes per run</li>
    <li>Parachuting — $1K-$3K per jump for completing all locations</li>
  </ul>
  <p>Possible GTA6 additions: street fighting/underground boxing (Vice City tradition), speedboat racing (larger water map), drone racing (modern Miami flavor).</p>
  <p><strong>Post-launch verification:</strong> What repeatable activities exist? Which pays the most per hour? Are there daily/weekly bonuses?</p>
</div>

<div class="card">
  <h3>🎯 8. Bounties &amp; Assassination Missions</h3>
  <p>GTA5's assassination missions (Lester's 5 missions) pay $5K-$15K each, but their real value is <strong>pairing them with stock market manipulation for enormous amplified returns</strong>. GTA4 and RDR2 also had bounty hunting mechanics.</p>
  <p>If GTA6 combines assassinations + stock market + bounty hunting, it creates a complete money-making chain: accept contract → invest in target's competitor → execute the hit → stock rises → cash out.</p>
  <p><strong>Post-launch verification:</strong> How many assassination missions? Which stock does each one affect? Does a bounty system exist?</p>
</div>

<h2>Money Method Priority Ranking (Estimated Based on GTA Series History)</h2>
<p>Ranked by expected payout. These will be replaced with actual data after launch.</p>

<table>
  <thead>
    <tr><th>Tier</th><th>Method</th><th>Payout (per run / period)</th><th>Repeatable?</th><th>Difficulty</th><th>Prerequisites</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>S</strong></td><td>Stock market (paired with assassinations)</td><td>Millions to hundreds of millions</td><td>One-shot (per assassination opportunity)</td><td>Low</td><td>Story progress to unlock assassinations</td></tr>
    <tr><td><strong>S</strong></td><td>Final story heists</td><td>$20M-$50M</td><td>One-shot</td><td>Med–High</td><td>Story progress to final chapter</td></tr>
    <tr><td><strong>A</strong></td><td>Side business income</td><td>$10K-$100K/week</td><td>Recurring passive income</td><td>Medium</td><td>Purchase property + complete business missions</td></tr>
    <tr><td><strong>A</strong></td><td>100% collectible completion</td><td>$500K-$2M total</td><td>One-shot</td><td>Low</td><td>Free roam access</td></tr>
    <tr><td><strong>B</strong></td><td>Vehicle export</td><td>$40K-$150K per vehicle</td><td>Repeatable (cooldown TBD)</td><td>Low–Med</td><td>Unlock export contact</td></tr>
    <tr><td><strong>B</strong></td><td>Assassination missions (no stock play)</td><td>$5K-$20K each</td><td>One-shot (5-10 missions)</td><td>Medium</td><td>Story progress</td></tr>
    <tr><td><strong>C</strong></td><td>Store robberies / armored trucks</td><td>$200-$25K per hit</td><td>Repeatable (random spawns)</td><td>Low</td><td>None</td></tr>
    <tr><td><strong>C</strong></td><td>Repeatable races &amp; activities</td><td>$1K-$15K per run</td><td>Infinitely repeatable</td><td>Low–Med</td><td>None</td></tr>
    <tr><td><strong>D</strong></td><td>Random events / wallet returns</td><td>$500-$10K per event</td><td>Random trigger</td><td>Very low</td><td>None</td></tr>
  </tbody>
</table>

<h2>GTA6 Economy System Predictions</h2>
<p>Based on Rockstar's recent design trends (GTA Online's economic model + RDR2's immersion-first design), here are key predictions for GTA6's economy:</p>

<div class="card">
  <h3>Prediction 1: Vice City-Style Property System Returns</h3>
  <p>GTA6 is set in Vice City — paying homage to the original is inevitable. One of the most beloved mechanics from the original VC was the <strong>buy property → complete missions → collect income</strong> loop. GTA5 removed the mission requirement and made properties pure passive income, which players found less rewarding than VC's approach. Rockstar has every reason to bring back VC's best system.</p>
</div>

<div class="card">
  <h3>Prediction 2: More Realistic Economy</h3>
  <p>RDR2's economy was much tighter than GTA5's — money was harder to earn, prices were grounded, and every purchase required consideration. GTA6 will likely land between the two: harder to get rich than GTA5, but not as restrictive as RDR2. This <strong>extends single-player playtime</strong> (GTA5 made it too easy to buy everything and run out of things to do).</p>
</div>

<div class="card">
  <h3>Prediction 3: Money Laundering Mechanics</h3>
  <p>GTA Online already has basic "money laundering" concepts (different businesses carry different risk levels). GTA6 single-player may introduce a more complex legal/illegal income balance — illegal activities pay fast but attract police attention, while legal businesses are stable but slow to grow. This directly echoes Vice City's original "front company" concept.</p>
</div>

<div class="card">
  <h3>Prediction 4: Shark Card Ecosystem Continues</h3>
  <p>GTA Online has made billions from Shark Cards — Take-Two isn't giving up that cash cow. GTA6 single-player will almost certainly have no microtransactions, but GTA6 Online definitely will. Understanding which items are most expensive and most worth buying with in-game currency in Online can help you decide where to spend your single-player money.</p>
</div>

<h2>Day-One Money Roadmap</h2>
<p>If you're aiming to "beat the game fast and reach financial freedom," here's the recommended action order:</p>

<ol class="step-list">
  <li><strong>Complete the prologue (est. 3-5 missions)</strong> — this unlocks free roam, the prerequisite for everything else.</li>
  <li><strong>Don't waste money early</strong> — funds are tight at the start. Pick up weapons from enemies, steal cars. Universal GTA rule: $10K in the first third of the game is worth more than $100K in the endgame.</li>
  <li><strong>Watch for assassination missions</strong> — if you see one from Lester or a similar character, <strong>stop</strong>. Check a guide first to confirm which stock it affects, THEN do the mission. These are the highest-ROI money opportunities in the entire game — miss one and you lose millions.</li>
  <li><strong>Buy your first property early</strong> — once properties become available, prioritize ones that unlock missions (not pure passive income). After completing the property missions, it generates recurring passive income.</li>
  <li><strong>Grab collectibles casually, don't obsess</strong> — pick them up as you play through the story, then use a guide to finish after beating the game. Collectibles are "nice to have," not "need to have."</li>
  <li><strong>Come back after beating the game</strong> — this page will be updated with all actual payout figures, optimal investment timing, and complete strategies within a week of launch.</li>
</ol>

<div class="warning">All rankings and dollar amounts above are estimates based on GTA series history, NOT confirmed GTA6 data. After launch, this page will be updated with actual payout rankings, optimal buy/sell timing for every stock, ROI analysis for all properties, and a complete money-making strategy guide. Bookmark this page and come back right after launch for the final version.</div>""",
        active_nav="money")

    # 8. Generate online guide page
    gen_generic("online/index.html",
        title="GTA6 Online Guide — Tips, Heists & Money Making",
        h1="GTA6 Online Guide",
        meta="Complete guide to GTA6 Online: heists, businesses, money making, crews, and PvP tips. Get ahead of other players from day one.",
        content="""<div class="disclaimer">
  GTA6 Online is not yet available. This page will be updated after launch. Below is currently confirmed public information.
</div>

<h2>Confirmed Information</h2>
<ul>
  <li>GTA6 Online will launch <strong>same day as single-player</strong> (confirmed by Rockstar)</li>
  <li>Rockstar acquired <strong>Cfx.re</strong> (developers of FiveM and RedM) in 2023, hinting at official roleplay features</li>
  <li>Take-Two has repeatedly called GTA Online "a standalone, continuously updated platform" in earnings calls</li>
</ul>

<h2>GTA5 Online Reference Data</h2>
<p>Below are GTA5 Online money-making rankings (for reference only — GTA6 Online's economy may be completely different):</p>

<table>
  <thead>
    <tr><th>Method</th><th>Soloable?</th><th>Est. Hourly</th><th>Difficulty</th></tr>
  </thead>
  <tbody>
    <tr><td>Cayo Perico Heist</td><td>Yes</td><td>$1.5M-$2M</td><td>Medium</td></tr>
    <tr><td>Diamond Casino Heist</td><td>No</td><td>$1M-$2.5M</td><td>High</td></tr>
    <tr><td>Nightclub Warehouse</td><td>Yes</td><td>$40K-$80K</td><td>Low</td></tr>
    <tr><td>Bunker Sales</td><td>Yes</td><td>$135K-$210K</td><td>Medium</td></tr>
    <tr><td>Vehicle Export (I/E)</td><td>Yes</td><td>$240K-$320K</td><td>Medium</td></tr>
    <tr><td>Agency Contracts</td><td>Yes</td><td>$60K-$150K</td><td>Low</td></tr>
    <tr><td>MC Businesses</td><td>No</td><td>$60K-$100K</td><td>Medium</td></tr>
  </tbody>
</table>

<div class="tip">Cayo Perico is the best solo money-maker in GTA5 Online. GTA6 Online will almost certainly have a similar repeatable solo heist — it was the most popular update in GTA Online history.</div>

<div class="warning">Never buy Shark Cards at full price. Wait for the 50% off sales every 2-3 months. Or just don't buy them — solo grinding Cayo Perico pays better per hour than a $20 Shark Card.</div>

<h2>GTA6 Online Preview</h2>
<p>GTA6 Online will be a <strong>completely fresh start</strong> — every player begins from zero. No decade-old accounts, no max-level players griefing newbies in jets. <strong>The first three months of GTA6 Online will be the most exciting period in the GTA community in years.</strong></p>

<p>What Rockstar has hinted at:</p>
<ul>
  <li><strong>Dynamic map</strong> — GTA6's world will evolve over time, with new buildings, events, and storylines (similar to Fortnite's seasonal map updates)</li>
  <li><strong>Cross-play</strong> — at minimum between PlayStation and Xbox, with PC possibly included</li>
  <li><strong>Roleplay features</strong> — Rockstar acquired Cfx.re (the largest GTA RP server team and FiveM developers) in 2023, suggesting built-in RP mechanics</li>
  <li><strong>Dedicated servers</strong> — goodbye to GTA5 Online's P2P connections (high latency, rampant cheating)</li>
</ul>""",
        active_nav="")

    # 9. Generate pre-order guide page
    gen_generic("pre-order.html",
        title="GTA6 Pre-Order Guide — Editions, Prices, Platforms & Bonuses",
        h1="GTA6 Pre-Order Guide",
        meta="Complete GTA6 pre-order guide: Standard/Deluxe/Collector's Edition comparison, prices, platforms, pre-order bonuses, and where to buy. Pre-orders open June 25, 2026.",
        content="""<div class="preorder-hero">
  <div class="preorder-hero-badge">🔥 Pre-orders Open June 25, 2026</div>
  <h2 class="preorder-hero-title">Secure Your Copy</h2>
  <p class="preorder-hero-date">Launching <strong>November 19, 2026</strong></p>
</div>

<div class="tip">This page will be updated with actual prices and links when pre-orders open on June 25. Edition info below is based on Rockstar's historical release patterns and Take-Two earnings data.</div>

<h2>GTA6 Edition Comparison</h2>
<p>Rockstar typically offers 3 editions for flagship titles: Standard, Special/Deluxe, and Collector's. Below are the estimated differences based on GTA5 and RDR2 release history:</p>

<div class="edition-grid">
  <div class="edition-card">
    <div class="edition-header standard">
      <h3>Standard Edition</h3>
      <div class="edition-price">$69.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>GTA6 base game (PS5 / Xbox Series X|S)</li>
        <li>Pre-order bonus (if any)</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">Digital / Physical</span>
    </div>
  </div>

  <div class="edition-card featured">
    <div class="edition-badge">Recommended</div>
    <div class="edition-header deluxe">
      <h3>Special Edition</h3>
      <div class="edition-price">$79.99 — $99.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>GTA6 base game</li>
        <li>Exclusive in-game content (vehicles, weapon skins, outfits)</li>
        <li>Online mode starting cash (est. $1M-$2M in-game currency)</li>
        <li>Digital soundtrack</li>
        <li>GTA6 art book (digital)</li>
        <li>GTA Online exclusive items</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">Digital / Physical</span>
    </div>
  </div>

  <div class="edition-card">
    <div class="edition-header collector">
      <h3>Collector's Edition</h3>
      <div class="edition-price">$149.99 — $199.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>All Special Edition content</li>
        <li>Physical Steelbook case</li>
        <li>GTA6 themed art book (physical)</li>
        <li>Protagonist figurine or vehicle model</li>
        <li>Vice City style map (physical print)</li>
        <li>Exclusive collector's outer box</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">Physical Only</span>
    </div>
  </div>
</div>

<div class="warning">All edition details and prices above are estimates based on GTA5 / RDR2 release history. Actual editions, pricing, and contents will be confirmed when Rockstar officially announces them on June 25.</div>

<h2>Where to Pre-Order by Platform</h2>

<table>
  <thead>
    <tr><th>Platform</th><th>Store</th><th>Editions</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>PS5</strong></td>
      <td>PlayStation Store</td>
      <td>Standard / Deluxe</td>
      <td>Digital pre-order with pre-load, unlocks midnight launch day</td>
    </tr>
    <tr>
      <td><strong>PS5</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>Standard / Deluxe / Collector's</td>
      <td>Physical, ships on launch day</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Microsoft Store</td>
      <td>Standard / Deluxe</td>
      <td>Digital pre-order with pre-load, Play Anywhere likely supported</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>Standard / Deluxe / Collector's</td>
      <td>Physical, ships on launch day</td>
    </tr>
    <tr>
      <td><strong>PC</strong></td>
      <td>Rockstar Games Launcher</td>
      <td>TBA</td>
      <td>PC release date not yet announced (est. 2027)</td>
    </tr>
    <tr>
      <td><strong>PC</strong></td>
      <td>Steam / Epic Games</td>
      <td>TBA</td>
      <td>Typically 6-18 months after console launch</td>
    </tr>
    <tr>
      <td><strong>All Platforms</strong></td>
      <td>Rockstar Warehouse</td>
      <td>All Editions</td>
      <td>Rockstar's official store — primary channel for Collector's Edition</td>
    </tr>
  </tbody>
</table>

<h2>Pre-Order Bonus Predictions</h2>
<p>Rockstar's historical pre-order bonus patterns (GTA5 and RDR2 both had the following types of pre-order rewards):</p>

<div class="card">
  <h3>Pre-Order Bonuses (99% Confirmed)</h3>
  <ul>
    <li><strong>In-game cash bonus</strong> — GTA Online / GTA6 Online starting funds, typically $500K-$2M</li>
    <li><strong>Exclusive vehicle</strong> — pre-order exclusive vehicle (livery or performance variant), not obtainable through in-game means</li>
    <li><strong>Weapon skins</strong> — pre-order exclusive weapon appearance or early unlock</li>
    <li><strong>Outfit pack</strong> — Vice City themed retro outfits</li>
  </ul>
</div>

<div class="card">
  <h3>Deluxe Edition Extra Bonuses (Speculative)</h3>
  <ul>
    <li><strong>Story mission reward boost</strong> — similar to RDR2's Le Trésor des Morts mission (originally PS4 exclusive, later unlocked for all platforms)</li>
    <li><strong>Property discount</strong> — discount on your first in-game property purchase</li>
    <li><strong>Shark Card discount</strong> — discount on first GTA Online Shark Card purchase</li>
  </ul>
</div>

<h2>What to Know Before Pre-Ordering</h2>

<div class="card">
  <h3>Physical vs Digital</h3>
  <table>
    <thead><tr><th></th><th>Physical</th><th>Digital</th></tr></thead>
    <tbody>
      <tr><td>Pre-load</td><td>❌ Must wait for delivery</td><td>✅ Downloads 2-3 days early</td></tr>
      <tr><td>Unlock time</td><td>When delivery arrives</td><td>Midnight launch day (local time)</td></tr>
      <tr><td>Resell</td><td>✅ Can resell used</td><td>❌ Locked to account</td></tr>
      <tr><td>Collector's Edition</td><td>✅ Physical collectibles included</td><td>❌ Usually no digital Collector's</td></tr>
      <tr><td>Disc damage risk</td><td>⚠ Yes</td><td>✅ None</td></tr>
      <tr><td>Game Sharing</td><td>✅ Lend to friends</td><td>✅ Family sharing (platform dependent)</td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h3>PC Players: Wait or Jump In?</h3>
  <p>Rockstar historically releases PC versions 6-18 months after consoles:</p>
  <ul>
    <li><strong>GTA5</strong>: PS3/360 (Sep 2013) → PC (Apr 2015) — <strong>19 months</strong> gap</li>
    <li><strong>RDR2</strong>: PS4/Xbox One (Oct 2018) → PC (Nov 2019) — <strong>13 months</strong> gap</li>
  </ul>
  <p><strong>Estimated GTA6 PC release: Q3-Q4 2027</strong>. If you only have a PC, it's worth the wait — Rockstar's PC ports consistently deliver better graphics and higher framerates than console versions. If you have both a console and a PC, buy the console version first to experience launch day, then upgrade when the PC version drops.</p>
</div>

<div class="card">
  <h3>Is the Collector's Edition Worth It?</h3>
  <p>Both GTA5 and RDR2 Collector's Editions <strong>sold out fast</strong> after launch, with secondary market markups of 50%-200%. If you:</p>
  <ul>
    <li>Are a die-hard GTA fan / collector → go for it immediately, don't hesitate or it's gone</li>
    <li>Only want the in-game content, don't care about physical items → the Digital Deluxe is enough</li>
    <li>Have a tight budget → get the Standard Edition + wait for DLC discounts later</li>
  </ul>
</div>

<h2>FAQ</h2>

<div class="card">
  <h3>When am I charged for a pre-order?</h3>
  <p><strong>Digital</strong>: PlayStation Store and Microsoft Store typically charge immediately at pre-order. Some retailers (Amazon, Best Buy) charge when the item ships.</p>
</div>

<div class="card">
  <h3>Can I cancel a pre-order?</h3>
  <p><strong>PlayStation Store</strong>: Cancel before release date (contact support or use the cancel pre-order feature). <strong>Microsoft Store</strong>: Cancel up to 10 days before release, not within the final 10 days. <strong>Amazon</strong>: Cancel anytime before shipment. <strong>GameStop</strong>: In-store deposits are refundable.</p>
</div>

<div class="card">
  <h3>Do pre-order bonus codes expire?</h3>
  <p>Generally, pre-order bonus codes are redeemable for 1-2 years after launch. However, some retailers may require pre-ordering before release to qualify. It's recommended to pre-order between June 25 and November 18.</p>
</div>

<div class="card">
  <h3>How much storage space will GTA6 need?</h3>
  <p>Not yet officially confirmed. For reference: GTA5 launched at ~65GB (later bloated to 110GB+), RDR2 was ~150GB. A conservative estimate for GTA6 is <strong>150GB-200GB</strong>. PS5 users should reserve at least 200GB of free space. Xbox Series S users may need an expansion card.</p>
</div>

<div class="card">
  <h3>Is there Early Access?</h3>
  <p>Rockstar never does early access (the kind where Deluxe Edition gets to play 3 days early). Deluxe/Collector's and Standard editions all unlock on the same day. Don't fall for third-party sites claiming otherwise.</p>
</div>

<div class="warning">This page will be updated with actual prices, purchase links, and confirmed edition details on June 25 when pre-orders open. Bookmark this page and come back on pre-order day for the final version. If you're aiming for the Collector's Edition, set an alarm for midnight ET on June 25 — both GTA5 and RDR2 Collector's Editions sold out within hours of pre-orders opening.</div>""",
        active_nav="preorder")

    # 10. Generate privacy page
    gen_generic("privacy.html",
        title="Privacy Policy - GTA6 Guide",
        h1="Privacy Policy",
        meta="Privacy policy for GTA6 Guide.",
        content="""<p>GTA6 Guide uses Google AdSense to serve ads. Google may use cookies to serve ads based on your prior visits to this or other websites.</p>
<p>We do not collect, store, or share any personal information.</p>
<p>This site is a fan project and is not affiliated with Rockstar Games or Take-Two Interactive.</p>""",
        active_nav="")

    # 10. Generate homepage
    gen_homepage()

    # 11. Generate sitemap & robots
    pages = ["", "privacy.html", "cheats.html", "money-guide.html", "pre-order.html",
             "story-missions/", "weapons/", "vehicles/",
             "collectibles/", "side-missions/", "online/"]
    for m in mission_items:
        pages.append(f"story-missions/{m['filename']}")
    for w in weapon_items:
        pages.append(f"weapons/{w['filename']}")
    for v in vehicle_items:
        pages.append(f"vehicles/{v['filename']}")
    for c in collectible_items:
        pages.append(f"collectibles/{c['filename']}")
    for s in side_items:
        pages.append(f"side-missions/{s['filename']}")

    gen_sitemap(pages)
    gen_robots()

    print(f"\nDone! Generated {len(pages)} URLs.")
    print(f"   Missions: {len(mission_items)} | Weapons: {len(weapon_items)} | Vehicles: {len(vehicle_items)}")
    print(f"   Collectibles: {len(collectible_items)} | Side Missions: {len(side_items)} | Online: 1")

if __name__ == "__main__":
    main()
