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
    }
    filename = f"mission-{str(i+1).zfill(2)}-{slug}.html"
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
    }
    out_dir = "weapons" if category == "Weapons" else "vehicles"
    filename = f"{slug}.html"
    write_page(f"{out_dir}/{filename}", replace_all(tpl, vars_dict))
    return {"name": name, "type_tag": row.get("type_tag", ""), "filename": filename}

def gen_collectible(row):
    """Generate a single collectible page using item template but with collectible-specific layout."""
    tpl = read_template("item.html")
    name = row.get("name", "Unknown Collectible")
    slug = make_slug(name)
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
    }
    filename = f"{slug}.html"
    write_page(f"collectibles/{filename}", replace_all(tpl, vars_dict))
    return {"name": name, "type_tag": type_tag, "filename": filename}

def gen_side_mission(row, i, prev_filename, next_filename):
    """Generate a single side mission page — reuses mission template with randomized structure."""
    tpl = read_template("mission.html")
    slug = make_slug(row.get("mission_name", f"side-{i+1}"))
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
    }
    filename = f"side-{str(i+1).zfill(2)}-{slug}.html"
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
        item_list = '<div class="disclaimer">GTA6 尚未发售，此分类的内容将在游戏发售后更新。请收藏本页，发售后第一时间回来查看。</div>'

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
    <p>预购 6 月 25 日开启。版本对比、价格预测、各平台预购渠道汇总。</p>
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
    <p>GTA5 作弊码参考 + GTA6 发售后更新</p>
  </a>
  <a href="money-guide.html" class="category-card">
    <h3>💰 Money Guide</h3>
    <p>赚钱方法通用思路，发售后更新具体数据</p>
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
    <p>GTA5 Online 参考 + GTA6 Online 前瞻</p>
  </a>
</div>"""),
        "PREORDER_ACTIVE": safe_html(""),
        "CHEATS_ACTIVE": safe_html(""),
        "MONEY_ACTIVE": safe_html(""),
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
<p>GTA6 尚未发售，无法确认任何作弊码。以下是基于 GTA 系列传统的推测——实际以发售后为准。</p>
<p>此页面将在游戏发售后 24-48 小时内更新，届时会有社区挖掘出的所有 GTA6 作弊码。</p>

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
  GTA6 尚未发售，此页面的具体赚钱方法、金额数据将在游戏发售后第一周内更新。以下内容基于 GTA 系列历代经验和已公开的 GTA6 信息整理。
</div>

<h2>GTA 系列赚钱通用思路</h2>
<p>以下为 GTA 系列历代的赚钱模式总结——GTA6 很可能延续这些系统，但具体数值和机制以发售后为准。每个方法都附了<strong>为什么有效</strong>和<strong>发售后怎么验证</strong>，方便游戏解锁后第一时间确认。</p>

<div class="card">
  <h3>💰 1. 主线任务 (Story Missions)</h3>
  <p>完成主线剧情是任何 GTA 游戏最主要的资金来源。以 GTA5 为例，通关全部 69 个主线任务可获得约 <strong>$30-40M</strong>（含抢劫分成）。后期抢劫任务单次报酬可达 <strong>$20M+</strong>（The Big Score，明显方案）。</p>
  <p><strong>核心策略：</strong>部分任务中通过选择不同方案（如 GTA5 的「明显」vs「隐秘」）影响最终报酬。在任务前手动存档，比较两种方案的实际收益——通常隐秘方案分钱的人少、你自己拿得多。</p>
  <p><strong>发售后验证点：</strong>哪几个任务报酬最高？哪些任务有方案选择？选哪个方案净收益最大（扣除 crew cut）？</p>
</div>

<div class="card">
  <h3>📈 2. 股市操纵 (Stock Market)</h3>
  <p>GTA5 首次引入受玩家行为影响的股票市场——LCN（单机）和 BAWSAQ（联网）。核心逻辑：<strong>在任务前买入受影响的股票，任务完成后股价暴涨时卖出</strong>。</p>
  <p>GTA5 典型案例：</p>
  <ul>
    <li><strong>LifeInvader 任务前</strong>做空 LifeInvader → 任务后股价暴跌 → 获利</li>
    <li><strong>Hotel Assassination 前</strong>买入 Betta Pharmaceuticals → 任务后涨 50%+</li>
    <li><strong>The Multi Target Assassination 前</strong>全仓 Debonaire → 涨 80%，再换 Redwood → 涨 300%</li>
  </ul>
  <p>如果 GTA6 延续此系统（大概率会——Rockstar 没理由砍掉这个广受好评的机制），股市操纵将是<strong>全游戏收益最高的赚钱方式</strong>，没有之一。</p>
  <p><strong>发售后验证点：</strong>LCN 股票池有哪些？哪些任务影响哪些股票？涨幅多少？最佳买入时机（任务前第几个 checkpoint）？</p>
</div>

<div class="card">
  <h3>🏢 3. 资产与产业 (Properties &amp; Businesses)</h3>
  <p>GTA 系列从 Vice City 开始就引入了资产系统——购买产业后解锁专属任务，完成后该产业开始定期产生收入。</p>
  <p>GTA Vice City 的经典例子：</p>
  <ul>
    <li><strong>Malibu Club</strong> — 12 万买入，完成后每周收入 $10K</li>
    <li><strong>Cherry Popper Ice Cream</strong> — 2 万买入，完成后每周 $3K</li>
    <li><strong>Print Works</strong> — 7 万买入，完成后每周 $8K（全游戏最后资产）</li>
  </ul>
  <p>GTA5 则把产业系统简化了——买下就赚钱，不需要做任务。GTA6 大概率回归 Vice City 的「买资产 → 做任务 → 开始收钱」模式，因为设在新 Vice City 致敬原版是情理之中。</p>
  <p><strong>发售后验证点：</strong>有多少可购买资产？哪些资产的投资回报率最高？需要多少任务才能「回本」？</p>
</div>

<div class="card">
  <h3>🚗 4. 载具出口 (Vehicle Export)</h3>
  <p>偷高端车辆出售是 GTA 最经典的赚钱玩法之一，从 GTA1 就开始有了。GTA5 Online 中的 Import/Export 更新把这个系统做成了最赚钱的 solo 活动之一。</p>
  <p>GTA6 设定在 Vice City（迈阿密），富人区（Starfish Island、Vice Beach 沿岸）的豪车密度预计非常高。如果单机模式也有类似 GTA Online I/E 的系统，那么：</p>
  <ul>
    <li>高端跑车（类似 Infernus、Cheetah）→ 预计 $80K-$150K/辆</li>
    <li>豪华轿车 → 预计 $40K-$80K/辆</li>
    <li>改装后出售 → 售价 +20%~50%（GTA5 的 Los Santos Customs 逻辑）</li>
  </ul>
  <p><strong>发售后验证点：</strong>有没有专门的出口任务线？最高价值的车在哪里刷新？改装增值比例是多少？</p>
</div>

<div class="card">
  <h3>🏪 5. 抢劫商店与随机事件 (Robberies &amp; Random Events)</h3>
  <p>GTA5 的便利店抢劫每次只能拿几百到一千多，性价比不高。但 GTA6 中这个系统可能被大幅扩展：</p>
  <ul>
    <li><strong>便利店</strong> — 快速现金 $200-$2K，低风险</li>
    <li><strong>运钞车</strong> — 随机刷新，$5K-$25K（GTA5 逻辑）</li>
    <li><strong>随机事件</strong> — 还钱包、送人、追小偷，$500-$10K，有些还会解锁特殊奖励</li>
    <li><strong>ATM 劫持</strong> — GTA6 如果加入（NPC 会在 ATM 取钱），跟在后面抢</li>
  </ul>
  <p><strong>发售后验证点：</strong>运钞车的刷新点和金额？哪些随机事件奖励最高？有没有隐藏的特殊随机事件？</p>
</div>

<div class="card">
  <h3>📦 6. 收集品 (Collectibles)</h3>
  <p>每代 GTA 都有隐藏收集品，找到一定数量后会给现金奖励和特殊载具：</p>
  <ul>
    <li>GTA Vice City — 100 隐藏包裹 → $100K + Hunter 直升机 + Rhino 坦克</li>
    <li>GTA SA — 100 涂鸦 + 50 照片 + 50 马蹄铁 + 50 牡蛎 → 总计 $300K+</li>
    <li>GTA5 — 50 信件碎片 + 50 太空船零件 + 30 核废料 + 50 信号干扰器 → 总计 $1.5M+</li>
  </ul>
  <p>收集品的好处是<strong>零风险</strong>——不开枪、不惹警察，纯跑图就能拿钱。GTA6 地图比 GTA5 更大，预计收集品数量也会创新高。</p>
  <p><strong>发售后验证点：</strong>有哪些类型的收集品？总数多少？找到多少给什么奖励？有没有像 GTA5 那样完成全收集给特殊任务？</p>
</div>

<div class="card">
  <h3>🏎️ 7. 可重复竞赛与活动 (Repeatable Events)</h3>
  <p>赛车、铁人三项、跳伞、高尔夫、网球——GTA5 的这些副活动虽然来钱慢，但可以无限重复：</p>
  <ul>
    <li>街头赛车 — 第一名 $1K-$5K，低风险</li>
    <li>铁人三项 — 第一名 $5K-$15K，但一次要跑 20-30 分钟</li>
    <li>跳伞 — 完成所有跳伞点 $1K-$3K/个</li>
  </ul>
  <p>GTA6 新增可能性：街头格斗/地下拳赛（Vice City 传统）、快艇竞速（水地图变大）、无人机竞速（现代迈阿密特色）。</p>
  <p><strong>发售后验证点：</strong>有哪些可重复活动？最高收益的活动是什么？有没有每日/每周奖励？</p>
</div>

<div class="card">
  <h3>🎯 8. 赏金与暗杀任务 (Bounty &amp; Assassination)</h3>
  <p>GTA5 的暗杀任务（Lester 的 5 个暗杀）除了本身给 $5K-$15K 报酬外，还有一个更重要的功能——<strong>配合股市操纵放大收益</strong>。GTA4 和 RDR2 也有赏金猎人机制。</p>
  <p>GTA6 如果结合了暗杀 + 股市 + 赏金系统，这将是一条完整的赚钱链条：接暗杀 → 投资目标竞争对手的股票 → 执行暗杀 → 股价涨 → 卖出。</p>
  <p><strong>发售后验证点：</strong>暗杀任务有多少个？每个暗杀影响哪些股票？赏金系统是否存在？</p>
</div>

<h2>赚钱方法优先级排名（基于 GTA 系列经验预估）</h2>
<p>以下是按预期收益排的优先级。游戏发售后会用实际数据替换。</p>

<table>
  <thead>
    <tr><th>等级</th><th>方法</th><th>单次/周期收益</th><th>可重复性</th><th>难度</th><th>前置条件</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>S</strong></td><td>股市操纵（配合暗杀任务）</td><td>几百万～上亿</td><td>一次性（每个暗杀一次机会）</td><td>低</td><td>主线推进到暗杀解锁</td></tr>
    <tr><td><strong>S</strong></td><td>主线抢劫任务（最终章）</td><td>$20M-$50M</td><td>一次性</td><td>中～高</td><td>主线推进到终章</td></tr>
    <tr><td><strong>A</strong></td><td>支线产业经营</td><td>$10K-$100K/周</td><td>持续被动收入</td><td>中</td><td>买下产业+完成产业任务</td></tr>
    <tr><td><strong>A</strong></td><td>收集品全清</td><td>$500K-$2M 总计</td><td>一次性</td><td>低</td><td>自由探索</td></tr>
    <tr><td><strong>B</strong></td><td>载具出口</td><td>$40K-$150K/辆</td><td>可重复（冷却时间未知）</td><td>低～中</td><td>解锁出口联系人</td></tr>
    <tr><td><strong>B</strong></td><td>暗杀任务（不含股市）</td><td>$5K-$20K/个</td><td>一次性（5-10个）</td><td>中</td><td>主线推进</td></tr>
    <tr><td><strong>C</strong></td><td>抢劫商店 / 运钞车</td><td>$200-$25K/次</td><td>可重复（随机刷新）</td><td>低</td><td>无</td></tr>
    <tr><td><strong>C</strong></td><td>可重复竞赛</td><td>$1K-$15K/次</td><td>无限可重复</td><td>低～中</td><td>无</td></tr>
    <tr><td><strong>D</strong></td><td>随机事件 / 还钱包</td><td>$500-$10K/次</td><td>随机触发</td><td>极低</td><td>无</td></tr>
  </tbody>
</table>

<h2>GTA6 经济系统预测</h2>
<p>基于 Rockstar 近年设计趋势（GTA Online 的经济模型 + RDR2 的沉浸感设计），对 GTA6 经济系统有几个关键预判：</p>

<div class="card">
  <h3>预判 1：资产系统回归 Vice City 模式</h3>
  <p>GTA6 设定在 Vice City，致敬原版是必然的。原版 VC 最受好评的设计之一就是<strong>买资产 → 做任务 → 开始收租</strong>的循环。GTA5 把这个砍成了纯买入就赚钱，玩家反馈不如 VC 有成就感。Rockstar 没理由不把 V C 最好的系统带回来。</p>
</div>

<div class="card">
  <h3>预判 2：经济更贴近现实</h3>
  <p>RDR2 的经济系统比 GTA5 严格得多——钱不好赚、物价合理、每笔消费都要掂量。GTA6 很可能介于两者之间：比 GTA5 更难赚大钱，但不像 RDR2 那么紧。这样可以<strong>延长单机游戏时长</strong>（GTA5 太容易赚到所有钱然后无事可做）。</p>
</div>

<div class="card">
  <h3>预判 3：洗钱机制</h3>
  <p>GTA Online 已经有基础的「洗钱」概念（不同生意有不同风险）。GTA6 单机可能引入更复杂的合法/非法收入平衡——非法活动来钱快但吸引警察注意，合法产业稳定但回报慢。这跟 Vice City 原版的「掩护公司」概念一脉相承。</p>
</div>

<div class="card">
  <h3>预判 4：鲨鱼卡生态延续</h3>
  <p>GTA Online 靠鲨鱼卡赚了几十亿美元，Take-Two 不可能放弃这个印钞机。GTA6 单机模式大概率没有氪金，但 GTA6 Online 肯定有。提前了解哪些东西在 Online 里最贵、最值得花游戏币买，可以帮助你决定单机把钱花在哪里。</p>
</div>

<h2>发售后第一时间赚钱路线图</h2>
<p>如果你是冲着「发售后尽快通关并财富自由」来的，这是推荐的行动顺序：</p>

<ol class="step-list">
  <li><strong>完成序章（估计 3-5 个任务）</strong>——解锁自由探索模式，这是做任何事情的前提。</li>
  <li><strong>不要乱花钱</strong>——初期资金紧张，武器捡敌人的就行，车偷来用。GTA 系列通用原则：前三分之一的游戏里，$10K 比后期 $100K 更值钱。</li>
  <li><strong>注意暗杀任务</strong>——如果你看到 Lester 或类似角色的暗杀任务出现，<strong>停下来</strong>。先查攻略确认每个暗杀对应哪只股票，再去做。这是全游戏收益最高的赚钱机会，一次错过损失几百万。</li>
  <li><strong>尽早买第一处资产</strong>——一旦可以买产业，优先买能解锁任务的那种（不是纯收租的）。做完产业任务后它会持续产生被动收入。</li>
  <li><strong>收集品随缘拿，别强迫症</strong>——通关过程中顺手拿，通关后用攻略补完。收集品是「锦上添花」不是「雪中送炭」。</li>
  <li><strong>通关后回来查更新</strong>——本页面会在游戏发售后一周内更新所有实际金额、最佳投资时机和完整策略。</li>
</ol>

<div class="warning">以上所有排名和金额均为基于 GTA 系列传统的预估值，并非 GTA6 确认数据。游戏发售后将更新具体金额排名、每只股票的最佳买卖时机、所有资产的投资回报率分析和完整赚钱策略指南。请收藏本页，发售后第一时间回来看最终版。</div>""",
        active_nav="money")

    # 8. Generate online guide page
    gen_generic("online/index.html",
        title="GTA6 Online Guide — Tips, Heists & Money Making",
        h1="GTA6 Online Guide",
        meta="Complete guide to GTA6 Online: heists, businesses, money making, crews, and PvP tips. Get ahead of other players from day one.",
        content="""<div class="disclaimer">
  GTA6 Online 尚未上线。此页面将在游戏发售后更新。以下为目前已确认的公开信息。
</div>

<h2>已确认信息</h2>
<ul>
  <li>GTA6 Online 将与单机游戏<strong>同日上线</strong>（Rockstar 官方确认）</li>
  <li>Rockstar 于 2023 年收购了 <strong>Cfx.re</strong>（FiveM 和 RedM 的开发商），暗示官方角色扮演功能</li>
  <li>Take-Two 在财报电话会中多次表示 GTA Online 是"独立的持续更新平台"</li>
</ul>

<h2>GTA5 Online 参考数据</h2>
<p>以下为 GTA5 Online 的赚钱排名（仅供参考，GTA6 Online 经济系统可能完全不同）：</p>

<table>
  <thead>
    <tr><th>方法</th><th>可单人?</th><th>时薪估算</th><th>难度</th></tr>
  </thead>
  <tbody>
    <tr><td>Cayo Perico 抢劫</td><td>是</td><td>$1.5M-$2M</td><td>中</td></tr>
    <tr><td>钻石赌场抢劫</td><td>否</td><td>$1M-$2.5M</td><td>高</td></tr>
    <tr><td>夜店仓库</td><td>是</td><td>$40K-$80K</td><td>低</td></tr>
    <tr><td>地堡销售</td><td>是</td><td>$135K-$210K</td><td>中</td></tr>
    <tr><td>载具出口 (I/E)</td><td>是</td><td>$240K-$320K</td><td>中</td></tr>
    <tr><td>事务所合约</td><td>是</td><td>$60K-$150K</td><td>低</td></tr>
    <tr><td>摩托帮生意</td><td>否</td><td>$60K-$100K</td><td>中</td></tr>
  </tbody>
</table>

<div class="tip">GTA5 Online 里 Cayo Perico 是最佳单人赚钱方式。GTA6 Online 极大概率会有类似的可重复单人抢劫——这是 GTA Online 历史上最受欢迎的一次更新。</div>

<div class="warning">不要原价买鲨鱼卡。等每 2-3 个月一次的半价促销。或者干脆别买——单刷 Cayo Perico 的时薪比一张 $20 鲨鱼卡值钱。</div>

<h2>GTA6 Online 前瞻</h2>
<p>GTA6 Online 将是<strong>全新起点</strong>——所有玩家从零开始。没有十年老号，没有满级玩家开着天煞炸鱼。<strong>GTA6 Online 头三个月会是 GTA 社区多年来最有趣的时期。</strong></p>

<p>Rockstar 已暗示的内容：</p>
<ul>
  <li><strong>动态地图</strong>——GTA6 世界会随时间变化，新建筑、活动、剧情线（类似 Fortnite 赛季制地图更新）</li>
  <li><strong>跨平台联机</strong>——至少 PlayStation 和 Xbox 互通，PC 也有可能</li>
  <li><strong>角色扮演功能</strong>——Rockstar 2023 年收购了最大 GTA RP 服务端团队 Cfx.re（FiveM 开发商），预计内建 RP 机制</li>
  <li><strong>专用服务器</strong>——告别 GTA5 Online 的 P2P 连接（延迟高、外挂多）</li>
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

<div class="tip">此页面将在 6 月 25 日预购开启后更新实际价格和链接。以下版本信息基于 Rockstar 历代发行模式和 Take-Two 财报数据推测。</div>

<h2>GTA6 版本对比</h2>
<p>Rockstar 通常为旗舰作品推出 3 个版本：「标准版」「特别/豪华版」「典藏版」。以下为基于 GTA5 和 RDR2 发行历史推测的版本差异：</p>

<div class="edition-grid">
  <div class="edition-card">
    <div class="edition-header standard">
      <h3>Standard Edition</h3>
      <div class="edition-price">$69.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>GTA6 基础游戏（PS5 / Xbox Series X|S）</li>
        <li>预购特典（如有）</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">数字版 / 实体版</span>
    </div>
  </div>

  <div class="edition-card featured">
    <div class="edition-badge">推荐</div>
    <div class="edition-header deluxe">
      <h3>Special Edition</h3>
      <div class="edition-price">$79.99 — $99.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>GTA6 基础游戏</li>
        <li>独家游戏内内容（载具、武器皮肤、服装）</li>
        <li>在线模式启动资金（预计 $1M-$2M 游戏币）</li>
        <li>数字原声带</li>
        <li>GTA6 艺术画册（数字版）</li>
        <li>GTA Online 专属道具</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">数字版 / 实体版</span>
    </div>
  </div>

  <div class="edition-card">
    <div class="edition-header collector">
      <h3>Collector's Edition</h3>
      <div class="edition-price">$149.99 — $199.99</div>
    </div>
    <div class="edition-body">
      <ul>
        <li>Special Edition 全部内容</li>
        <li>实体收藏铁盒 (Steelbook)</li>
        <li>GTA6 主题艺术画册（实体）</li>
        <li>主角手办或载具模型</li>
        <li>Vice City 风格地图（实体印刷）</li>
        <li>独占收藏外盒</li>
      </ul>
    </div>
    <div class="edition-footer">
      <span class="edition-tag">仅实体版</span>
    </div>
  </div>
</div>

<div class="warning">以上版本内容和价格均为基于 GTA5 / RDR2 发行历史的推测。实际版本划分、价格和内容以 Rockstar 6 月 25 日官方公布为准。</div>

<h2>各平台预购渠道</h2>

<table>
  <thead>
    <tr><th>平台</th><th>渠道</th><th>版本</th><th>备注</th></tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>PS5</strong></td>
      <td>PlayStation Store</td>
      <td>标准 / 豪华</td>
      <td>数字预购预载，发售日 0 点解锁</td>
    </tr>
    <tr>
      <td><strong>PS5</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>标准 / 豪华 / 典藏</td>
      <td>实体版，发售日发货</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Microsoft Store</td>
      <td>标准 / 豪华</td>
      <td>数字预购预载，Play Anywhere 可能支持</td>
    </tr>
    <tr>
      <td><strong>Xbox Series X|S</strong></td>
      <td>Amazon / GameStop / Best Buy</td>
      <td>标准 / 豪华 / 典藏</td>
      <td>实体版，发售日发货</td>
    </tr>
    <tr>
      <td><strong>PC</strong></td>
      <td>Rockstar Games Launcher</td>
      <td>待公布</td>
      <td>PC 发售日尚未公布（预计 2027）</td>
    </tr>
    <tr>
      <td><strong>PC</strong></td>
      <td>Steam / Epic Games</td>
      <td>待公布</td>
      <td>通常晚于主机版 6-18 个月</td>
    </tr>
    <tr>
      <td><strong>全平台</strong></td>
      <td>Rockstar Warehouse</td>
      <td>全版本</td>
      <td>Rockstar 官方商城，典藏版首发渠道</td>
    </tr>
  </tbody>
</table>

<h2>预购特典预测</h2>
<p>Rockstar 历年预购特典模式（GTA5 和 RDR2 均有以下形式的预购奖励）：</p>

<div class="card">
  <h3>预购奖励（99% 确认会有）</h3>
  <ul>
    <li><strong>游戏币奖励</strong> — GTA Online / GTA6 Online 启动资金，通常 $500K-$2M</li>
    <li><strong>独占载具</strong> — 预购专属载具（涂装或性能变体），不可通过游戏内途径获得</li>
    <li><strong>武器皮肤</strong> — 预购专属武器外观或早期解锁</li>
    <li><strong>服装套装</strong> — Vice City 主题复古服装</li>
  </ul>
</div>

<div class="card">
  <h3>豪华版额外奖励（推测）</h3>
  <ul>
    <li><strong>主线任务奖励加成</strong> — 类似 RDR2 的 Le Trésor des Morts 任务（PS4 独占内容后来全平台解锁）</li>
    <li><strong>资产折扣</strong> — 游戏内第一处资产购买打折</li>
    <li><strong>鲨鱼卡折扣</strong> — GTA Online 首次鲨鱼卡购买打折</li>
  </ul>
</div>

<h2>预购前要知道的事</h2>

<div class="card">
  <h3>实体版 vs 数字版</h3>
  <table>
    <thead><tr><th></th><th>实体版</th><th>数字版</th></tr></thead>
    <tbody>
      <tr><td>预载</td><td>❌ 需等快递</td><td>✅ 提前 2-3 天下载</td></tr>
      <tr><td>解锁时间</td><td>快递到货后</td><td>发售日 0 点（当地时间）</td></tr>
      <tr><td>转售</td><td>✅ 可二手出</td><td>❌ 绑账号</td></tr>
      <tr><td>典藏版</td><td>✅ 有实体周边</td><td>❌ 通常无典藏数字版</td></tr>
      <tr><td>光盘损坏风险</td><td>⚠ 有</td><td>✅ 无</td></tr>
      <tr><td>Game Sharing</td><td>✅ 借朋友玩</td><td>✅ 家庭共享（平台支持）</td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h3>PC 玩家：等还是不等？</h3>
  <p>Rockstar 历来 PC 版晚于主机版 6-18 个月：</p>
  <ul>
    <li><strong>GTA5</strong>: PS3/360 (2013.9) → PC (2015.4) — 间隔 <strong>19 个月</strong></li>
    <li><strong>RDR2</strong>: PS4/Xbox One (2018.10) → PC (2019.11) — 间隔 <strong>13 个月</strong></li>
  </ul>
  <p><strong>预估 GTA6 PC 版：2027 Q3-Q4</strong>。如果你只有 PC，建议等——Rockstar 的 PC 版向来比主机版画质更好、支持更高帧率。如果你有主机 + PC，建议先买主机版体验首发，PC 版出了再升级。</p>
</div>

<div class="card">
  <h3>典藏版值得冲吗？</h3>
  <p>GTA5 和 RDR2 的典藏版都在发售后<strong>快速售罄</strong>，二手市场溢价 50%-200%。如果你：</p>
  <ul>
    <li>是 GTA 死忠粉 / 收藏党 → 直接冲，别犹豫，犹豫就没了</li>
    <li>只想要游戏内容，对实体周边无感 → 买豪华数字版就够了</li>
    <li>预算有限 → 标准版 + 后期等折扣买 DLC 内容</li>
  </ul>
</div>

<h2>常见问题</h2>

<div class="card">
  <h3>预购什么时候扣款？</h3>
  <p><strong>数字版</strong>：PlayStation Store 和 Microsoft Store 通常在预购时立即扣款。部分零售商（Amazon、Best Buy）发货时才扣款。</p>
</div>

<div class="card">
  <h3>预购可以取消吗？</h3>
  <p><strong>PlayStation Store</strong>: 发售日前可取消（联系客服或使用取消预购功能）。<strong>Microsoft Store</strong>: 发售日前 10 天内不能取消，之前可取消。<strong>Amazon</strong>: 发货前随时取消。<strong>GameStop</strong>: 到店付定金的可以退。</p>
</div>

<div class="card">
  <h3>预购特典会过期吗？</h3>
  <p>一般来说，预购特典代码在游戏发售后的 1-2 年内都可以兑换。但部分零售商可能限制「必须发售前预购才能拿到」。建议 6 月 25 日-11 月 18 日之间预购。</p>
</div>

<div class="card">
  <h3>GTA6 需要多大存储空间？</h3>
  <p>尚未正式公布。参考：GTA5 首发约 65GB（后膨胀至 110GB+），RDR2 约 150GB。保守估计 GTA6 需要 <strong>150GB-200GB</strong>。建议 PS5 预留 200GB 可用空间，Xbox Series S 用户可能需要扩展卡。</p>
</div>

<div class="card">
  <h3>有没有 Early Access？</h3>
  <p>Rockstar 从来不搞提前游玩（EA 那种"豪华版提前 3 天玩"）。豪华版/典藏版和标准版是同一天解锁。别被第三方网站骗了。</p>
</div>

<div class="warning">本页面将在 6 月 25 日预购开启当天更新实际价格、购买链接和版本详情。建议收藏本页，预购日当天回来查看最终版。想要典藏版的建议设个 6 月 25 日零点（美东时间）的闹钟——GTA5 和 RDR2 的典藏版都在开启预购后几小时内售罄。</div>""",
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
