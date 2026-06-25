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

    # 7. Generate money guide (placeholder — game not yet released)
    gen_generic("money-guide.html",
        title="GTA6 Money Guide — How to Make Money Fast",
        h1="GTA6 Money Guide — How to Make Money Fast",
        meta="GTA6 money-making guide: story missions, heists, stock market, properties, businesses, vehicle export, and more. Full strategies and payout data coming after launch.",
        content="""<div class="disclaimer">
  GTA6 is not yet released. Money-making methods, payout figures, and strategies will be added within the first week after launch (November 19, 2026). Bookmark this page and check back.
</div>

<p>Once GTA6 launches, this page will cover:</p>

<ul>
  <li><strong>Story mission payouts</strong> — which missions pay the most, approach choices that affect your cut, crew cost optimization</li>
  <li><strong>Stock market manipulation</strong> — which missions affect which stocks, optimal buy/sell timing, LCN vs BAWSAQ strategies</li>
  <li><strong>Properties &amp; businesses</strong> — purchase costs, mission requirements, recurring income, ROI analysis</li>
  <li><strong>Vehicle export</strong> — high-value car spawns, modding value multipliers, cooldown mechanics</li>
  <li><strong>Side activities</strong> — street races, collectibles, random events, armored trucks, and other repeatable income sources</li>
  <li><strong>Complete money-making priority ranking</strong> — actual tested payouts, not estimates</li>
</ul>

<div class="warning">All strategies and numbers will be based on tested, confirmed GTA6 gameplay data — not speculation. Check back after November 19, 2026.</div>""",
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

<div class="tip">Pre-orders are now live (opened June 25, 2026). All information on this page is based on official Rockstar announcements. Game launches <strong>November 19, 2026</strong>. Pre-load begins November 12.</div>

<h2>GTA6 Edition Comparison — Officially Confirmed</h2>
<p>Rockstar confirmed two editions at launch. There is <strong>no Collector's Edition</strong> with physical collectibles. Physical copies come with a download code inside the box — <strong>no disc</strong> at launch.</p>

<div class="edition-grid">
  <div class="edition-card">
    <div class="edition-header standard">
      <h3>Standard Edition</h3>
      <div class="edition-price">$79.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>GTA6 base game (PS5 / Xbox Series X|S)</li>
        <li>Vintage Vice City Pack (all pre-orders and purchases before Nov 20, 2026)</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">Digital / Physical (download code)</span>
    </div>
  </div>

  <div class="edition-card featured">
    <div class="edition-badge">Recommended</div>
    <div class="edition-header ultimate">
      <h3>Ultimate Edition</h3>
      <div class="edition-price">$99.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>All Standard Edition content</li>
        <li>5 exclusive vehicles: '95 Grotti Cheetah, '67 Vapid Dominator Boogie, Dinka Enduro, Shitzu Squalo, Crest Kayak</li>
        <li>4 exclusive weapons: Hawk &amp; Little Morgan Revolvers, Girardi ES9, Klose K17 Custom Pistols</li>
        <li>Exclusive apparel tied to Jason &amp; Lucia's story</li>
        <li>Access to Rideout Customs &amp; One-Eyed Willie's mod shops (unique inventories)</li>
        <li>Classic Car Collection restoration missions</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">Digital Only</span>
    </div>
  </div>
</div>

<div class="tip">All edition details above are <strong>officially confirmed</strong> by Rockstar Games as of June 25, 2026. No Collector's Edition with physical collectibles exists. Physical copies do NOT include a disc — a proper disc release may come in 2027 or later.</div>

<h2>Where to Pre-Order by Platform</h2>

<table>
  <thead>
    <tr><th>Platform</th><th>Store</th><th>Editions</th><th>Notes</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>PS5</strong></td>
      <td>PlayStation Store</td>
      <td>Standard / Ultimate</td>
      <td>Digital pre-order. Pre-load starts Nov 12, unlocks midnight Nov 19.</td>
    </tr>
    <tr>
      <td><strong>PS5</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>Standard</td>
      <td>Physical box with download code (no disc). Ships Nov 12 for pre-load.</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Microsoft Store</td>
      <td>Standard / Ultimate</td>
      <td>Digital pre-order. Pre-load starts Nov 12, unlocks midnight Nov 19.</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>Standard</td>
      <td>Physical box with download code (no disc). Ships Nov 12 for pre-load.</td>
    </tr>
    <tr>
      <td><strong>All Platforms</strong></td>
      <td>Rockstar Warehouse</td>
      <td>Standard / Ultimate</td>
      <td>Rockstar's official store. Ultimate Edition is <strong>digital only</strong>.</td>
    </tr>
    <tr>
      <td><strong>PC</strong></td>
      <td>Rockstar Games Launcher / Steam / Epic</td>
      <td>TBA</td>
      <td>PC version not yet announced by Rockstar. No release window confirmed.</td>
    </tr>
  </tbody>
</table>

<h2>Pre-Order Bonuses — Confirmed</h2>
<p>Rockstar has officially confirmed the following pre-order bonuses. All pre-orders and purchases made before November 20, 2026 qualify.</p>

<div class="card">
  <h3>Vintage Vice City Pack (All Pre-Orders)</h3>
  <ul>
    <li><strong>'55 Vapid Stanier</strong> — classic sedan with vintage styling, plus a garage near Ocean Beach (includes weapon locker and stolen goods storage)</li>
    <li><strong>Jason's outfit</strong> — pastel linen suit with vintage hairstyle</li>
    <li><strong>Lucia's outfit</strong> — red sequin mini dress with curls</li>
    <li><strong>Weapon pattern</strong> — Tommy Vercetti-inspired palm tree tropical pattern</li>
  </ul>
</div>

<div class="card">
  <h3>Digital Pre-Order Extra Bonus</h3>
  <ul>
    <li><strong>1 free month of GTA+</strong> — redeemable immediately for GTA Online / GTA V</li>
    <li>Includes monthly GTA$500,000 deposit, Shark Card bonuses, free/discounted vehicles, and access to the GTA+ Games Library</li>
  </ul>
</div>

<div class="card">
  <h3>Ultimate Edition Exclusive Content ($99.99)</h3>
  <ul>
    <li><strong>Vehicles</strong>: '95 Grotti Cheetah, '67 Vapid Dominator Boogie, Dinka Enduro, Shitzu Squalo, Crest Kayak</li>
    <li><strong>Weapons</strong>: Hawk &amp; Little Morgan Revolvers (his-and-hers, palm-tree grips, engraved, scoped), Girardi ES9 Custom Pistol (Jason's), Klose K17 Custom Pistol (Lucia's)</li>
    <li><strong>Apparel</strong>: Exclusive clothing and hairstyles for Jason &amp; Lucia</li>
    <li><strong>Mod Shops</strong>: Rideout Customs &amp; One-Eyed Willie's — unique car/tattoo/clothing/salon inventories</li>
    <li><strong>Classic Car Collection</strong>: Find and restore abandoned vehicles (commissioned by Wyman)</li>
  </ul>
</div>

<div class="warning">GTA6 Online is <strong>not available at launch</strong> — the base game is single-player only. Pre-order bonuses are for the single-player campaign. GTA6 Online will be added post-launch.</div>

<h2>What to Know Before Pre-Ordering</h2>

<div class="card">
  <h3>Physical vs Digital — The New Reality</h3>
  <p><strong>Important:</strong> Physical GTA6 copies do <strong>NOT</strong> contain a disc. The box includes a download code. This applies to all retailers.</p>
  <table>
    <thead><tr><th></th><th>Physical (Download Code)</th><th>Digital</th></tr></thead>
    <tbody>
      <tr><td>Pre-load</td><td>✅ Code ships Nov 12, download before launch</td><td>✅ Pre-load starts Nov 12</td></tr>
      <tr><td>Unlock time</td><td>Midnight Nov 19 (local time)</td><td>Midnight Nov 19 (local time)</td></tr>
      <tr><td>Resell</td><td>✅ Can resell unused code</td><td>❌ Locked to account</td></tr>
      <tr><td>Ultimate Edition</td><td>❌ Not available physically</td><td>✅ Ultimate Edition is digital only</td></tr>
      <tr><td>Box / Collectible</td><td>✅ Has a box on your shelf</td><td>❌ Nothing physical</td></tr>
      <tr><td>Game Sharing</td><td>✅ Give code to anyone</td><td>✅ Family sharing (platform dependent)</td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h3>PC Players: No Announcement Yet</h3>
  <p>Rockstar has <strong>not announced a PC version</strong> of GTA6. Historical patterns provide a rough guide but are not confirmation:</p>
  <ul>
    <li><strong>GTA5</strong>: PS3/360 (Sep 2013) → PC (Apr 2015) — <strong>19 months</strong> gap</li>
    <li><strong>RDR2</strong>: PS4/Xbox One (Oct 2018) → PC (Nov 2019) — <strong>13 months</strong> gap</li>
  </ul>
  <p>If the pattern holds, expect a PC release sometime in <strong>2027-2028</strong>. If you only have a PC, you'll be waiting. If you have a console, buy it there — there's no confirmed date to wait for on PC.</p>
</div>

<div class="card">
  <h3>No Collector's Edition — What to Do?</h3>
  <p>Rockstar did <strong>not</strong> announce a Collector's Edition with physical items (no Steelbook, no figurine, no art book). This breaks the tradition from GTA5 and RDR2. Here's what it means:</p>
  <ul>
    <li>If you want maximum in-game content → <strong>Ultimate Edition ($99.99)</strong> is your only upgrade path</li>
    <li>If you want physical items → there are none from Rockstar directly. Third-party merchandise may appear closer to launch</li>
    <li>If you're on a budget → <strong>Standard Edition ($79.99)</strong> still includes the Vintage Vice City Pack if you pre-order or buy before Nov 20</li>
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
  <p>Not yet officially confirmed by Rockstar. Industry estimates based on trailer footage and development scope: <strong>150GB-200GB</strong>. PS5 users should reserve at least 200GB. Xbox Series S (512GB model) users will likely need an expansion card.</p>
</div>

<div class="card">
  <h3>Is there Early Access?</h3>
  <p>Rockstar never does early access (the kind where Deluxe Edition gets to play 3 days early). Deluxe/Collector's and Standard editions all unlock on the same day. Don't fall for third-party sites claiming otherwise.</p>
</div>

<div class="warning">All information on this page updated June 25, 2026 based on official Rockstar announcements. Pre-orders are live now. If you're aiming for the Ultimate Edition, note that it is <strong>digital only</strong> — there is no physical Ultimate Edition. The Standard Edition physical box contains a download code, not a disc.</div>""",
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
