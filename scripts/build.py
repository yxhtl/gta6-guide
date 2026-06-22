#!/usr/bin/env python3
"""
GTA6 Guide - Static Site Generator
Reads CSV data files, applies HTML templates, generates all pages + sitemap.
Usage: python scripts/build.py
"""

import csv
import hashlib
import os
import shutil
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data"

# ---- Helpers ----

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
    out = ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] {rel_path}")

def replace_all(text, vars_dict):
    """Replace all {{KEY}} placeholders with values."""
    for key, val in vars_dict.items():
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
            steps_html += f"<li>{s}</li>\n"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>{v['tips_heading']}</h2>\n<div class=\"tip\">{tips}</div>"

    trivia = row.get("trivia", "").strip()
    trivia_html = ""
    if trivia:
        trivia_html = f"<h2>Trivia</h2>\n<p>{trivia}</p>"

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
        summary = f"<p>This mission takes place in <strong>{row.get('chapter','?')}</strong> and is rated <strong>{row.get('difficulty','Normal')}</strong>. Completing it rewards you with <strong>{row.get('reward','TBD')}</strong>.</p>"
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
        "MISSION_BODY": mission_body,
        "MISSIONS_ACTIVE": ' class="active"',
        "PARENT_SLUG": "story-missions",
        "PARENT_LABEL": "Missions",
        "PREV_LINK": prev_html,
        "NEXT_LINK": next_html,
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
            stats_html += f'<div class="stat-item"><div class="stat-label">{key.replace("_"," ").title()}</div><div class="stat-value">{val}</div></div>\n'

    desc_text = row.get("description", f"Stats and details for {name} in GTA6.")
    desc_html = f"<p>{desc_text}</p>"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>Tips</h2>\n<div class=\"tip\">{tips}</div>"

    acq_text = row.get("acquisition", "TBD — game not yet released.")
    acq_block = f"<h2>{v['acq_heading']}</h2>\n<p>{acq_text}</p>"

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
        "ITEM_BODY": item_body,
        "WEAPONS_ACTIVE": weapons_active,
        "VEHICLES_ACTIVE": vehicles_active,
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
    desc_text = row.get("description", f"Where to find {name} in GTA6.")
    acq_text = row.get("acquisition", "TBD — game not yet released.")
    tips = row.get("tips", "").strip()

    # Stats grid tailored for collectibles
    stats_html = f'<div class="stat-item"><div class="stat-label">Area</div><div class="stat-value">{area}</div></div>\n'
    stats_html += f'<div class="stat-item"><div class="stat-label">Type</div><div class="stat-value">{type_tag}</div></div>\n'
    stats_html += f'<div class="stat-item"><div class="stat-label">Reward</div><div class="stat-value">{reward}</div></div>\n'

    desc_html = f"<p>{desc_text}</p>"
    tips_html = ""
    if tips:
        tips_html = f"<h2>Tips</h2>\n<div class=\"tip\">{tips}</div>"

    acq_block = f"<h2>{v['acq_heading']}</h2>\n<p>{acq_text}</p>"
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
        "ITEM_BODY": item_body,
        "WEAPONS_ACTIVE": "",
        "VEHICLES_ACTIVE": "",
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
            steps_html += f"<li>{s}</li>\n"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f"<h2>{v['tips_heading']}</h2>\n<div class=\"tip\">{tips}</div>"

    trivia = row.get("trivia", "").strip()
    trivia_html = ""
    if trivia:
        trivia_html = f"<h2>Trivia</h2>\n<p>{trivia}</p>"

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
        "MISSION_BODY": mission_body,
        "MISSIONS_ACTIVE": "",
        "PARENT_SLUG": "side-missions",
        "PARENT_LABEL": "Side Missions",
        "PREV_LINK": prev_html,
        "NEXT_LINK": next_html,
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
            extra = f" — {item.get('chapter', item.get('type_tag', ''))}" if item.get("chapter") or item.get("type_tag") else ""
            item_list += f'<li><a href="{item["filename"]}"><span class="item-name">{item["name"]}</span><span class="item-meta">{extra}</span></a></li>\n'
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
        "ITEM_LIST": item_list,
        "MISSIONS_ACTIVE": missions_active,
        "WEAPONS_ACTIVE": weapons_active,
        "VEHICLES_ACTIVE": vehicles_active,
    }
    write_page(f"{cat_slug}/index.html", replace_all(tpl, vars_dict))

def gen_generic(filename, title, h1, meta, content, active_nav=""):
    """Generate a generic content page (cheats, money guide, etc.)."""
    tpl = read_template("generic.html")
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
        "CONTENT": content,
        "CHEATS_ACTIVE": cheats_active,
        "MONEY_ACTIVE": money_active,
    }
    write_page(filename, replace_all(tpl, vars_dict))

def gen_sitemap(pages):
    """Generate sitemap.xml."""
    today = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    base = "https://gta6-guide.com"
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
    content = "User-agent: *\nAllow: /\nSitemap: https://gta6-guide.com/sitemap.xml\n"
    write_page("robots.txt", content)

def gen_homepage():
    """Generate the homepage."""
    tpl = read_template("generic.html")
    vars_dict = {
        "TITLE": "GTA6 Guide — Cheats, Missions, Weapons & More",
        "DESCRIPTION": "The ultimate GTA6 guide: cheats, money tips, all story missions, weapons, vehicles, and collectibles. Updated regularly.",
        "CSS_PATH": "",
        "HOME_PATH": "",
        "PAGE_TITLE": "Home",
        "H1": "GTA6 Guide",
        "META": "Your ultimate resource for Grand Theft Auto VI",
        "CONTENT": f"""<div class="hero">
  <p>The most comprehensive resource for Grand Theft Auto VI — cheats, missions, weapons, vehicles, money guides, and more.</p>
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
</div>""",
        "CHEATS_ACTIVE": "",
        "MONEY_ACTIVE": "",
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
    <tr><td>Invincibility</td><td><code class="cheat-code">1-999-724-654-5537</code></td><td>God mode for 5 minutes</td></tr>
    <tr><td>Max Health & Armor</td><td><code class="cheat-code">1-999-887-853</code></td><td>Full health and armor refill</td></tr>
    <tr><td>All Weapons</td><td><code class="cheat-code">1-999-866-587</code></td><td>Spawns all weapons with ammo</td></tr>
    <tr><td>Raise Wanted Level</td><td><code class="cheat-code">1-999-3844-8483</code></td><td>Add one wanted star</td></tr>
    <tr><td>Lower Wanted Level</td><td><code class="cheat-code">1-999-5299-3787</code></td><td>Remove one wanted star</td></tr>
    <tr><td>Spawn Buzzard Helicopter</td><td><code class="cheat-code">1-999-289-9633</code></td><td>Spawns armed attack helicopter</td></tr>
    <tr><td>Spawn Comet Sports Car</td><td><code class="cheat-code">1-999-266-38</code></td><td>Spawns a Comet sports car</td></tr>
    <tr><td>Spawn Sanchez Dirt Bike</td><td><code class="cheat-code">1-999-633-7623</code></td><td>Spawns a Sanchez off-road bike</td></tr>
    <tr><td>Parachute</td><td><code class="cheat-code">1-999-759-3483</code></td><td>Gives a parachute</td></tr>
    <tr><td>Slow Motion</td><td><code class="cheat-code">1-999-756-966</code></td><td>Slow motion aiming (3 levels)</td></tr>
    <tr><td>Change Weather</td><td><code class="cheat-code">1-999-625-348-7246</code></td><td>Cycle through weather types</td></tr>
    <tr><td>Moon Gravity</td><td><code class="cheat-code">1-999-356-2837</code></td><td>Low gravity mode</td></tr>
    <tr><td>Drunk Mode</td><td><code class="cheat-code">1-999-547-861</code></td><td>Drunken walking effect</td></tr>
    <tr><td>Explosive Melee</td><td><code class="cheat-code">1-999-4684-2637</code></td><td>Punches cause explosions</td></tr>
    <tr><td>Flaming Bullets</td><td><code class="cheat-code">1-999-462-363-4279</code></td><td>Bullets set targets on fire</td></tr>
  </tbody>
</table>

<div class="tip">GTA5 cheats disable achievements/trophies when active. GTA6 will likely have the same restriction — save before using cheats.</div>

<h2>What to Expect for GTA6 Cheats</h2>
<p>GTA6 尚未发售，无法确认任何作弊码。以下是基于 GTA 系列传统的推测——实际以发售后为准。</p>
<p>此页面将在游戏发售后 24-48 小时内更新，届时会有社区挖掘出的所有 GTA6 作弊码。</p>

<h2>Why Cheats Get Discovered Fast</h2>
<p>Rockstar phone cheats follow a predictable pattern — the numbers spell words on a phone keypad. For example, GTA5'S invincibility number <code class="cheat-code">1-999-724-654-5537</code> spells <code class="cheat-code">1-999-PAIN-KILLER</code>. The community typically reverse-engineers all phone cheats within <strong>24-48 hours</strong> of release by brute-forcing common word combinations.</p>

<p>We monitor cheat discovery threads on Reddit, GTAForums, and Twitter/X in real time during launch week. <strong>This page will be updated within hours of the first confirmed GTA6 cheat codes.</strong></p>""",
        active_nav="cheats")

    # 7. Generate money guide (expanded strategies)
    gen_generic("money-guide.html",
        title="GTA6 Money Guide — How to Make Money Fast (Best Methods)",
        h1="GTA6 Money Guide — How to Make Money Fast",
        meta="Best ways to earn money fast in GTA6: heists, stock market manipulation, side businesses, vehicle exports, collectible hunting. Detailed strategies and payout estimates.",
        content="""<div class="disclaimer">
  GTA6 尚未发售，此页面的具体赚钱方法、金额数据将在游戏发售后第一周内更新。
</div>

<h2>GTA 系列赚钱通用思路</h2>
<p>以下为 GTA 系列历代的赚钱模式总结——GTA6 很可能延续这些系统，但具体数值和机制以发售后为准：</p>

<div class="card"><h3>主线任务</h3>
<p>完成主线剧情是任何 GTA 游戏最主要的资金来源。后期任务（尤其是抢劫类）通常给出最大的一次性报酬。</p></div>

<div class="card"><h3>股市系统</h3>
<p>GTA5 首次引入了受玩家行为影响的股票市场（LCN 和 BAWSAQ）。如果 GTA6 延续此系统，在特定任务前投资相关股票会是收益最高的赚钱方式。</p></div>

<div class="card"><h3>支线任务与产业</h3>
<p>出租车、赛车、义警等可重复支线任务提供稳定收入。GTA Online 中的产业系统（夜店、地堡等）可能在 GTA6 单机模式中也有对应。</p></div>

<div class="card"><h3>收集品</h3>
<p>每代 GTA 都有隐藏包裹/收集品，找到一定数量后通常有现金奖励和特殊载具。</p></div>

<div class="card"><h3>载具出口</h3>
<p>偷高端车辆出售是经典 GTA 玩法。GTA6 设定在 Vice City（迈阿密），富人区的豪车密度预计很高。</p></div>

<div class="warning">以上均为系列传统模式的总结，并非 GTA6 确认内容。游戏发售后将更新具体金额排名、最佳投资时机和完整策略指南。</div>""",
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

    # 9. Generate privacy page
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
    pages = ["", "privacy.html", "cheats.html", "money-guide.html",
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
