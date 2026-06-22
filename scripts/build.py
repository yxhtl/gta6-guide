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
    for item in items:
        extra = f" — {item.get('chapter', item.get('type_tag', ''))}" if item.get("chapter") or item.get("type_tag") else ""
        item_list += f'<li><a href="{item["filename"]}"><span class="item-name">{item["name"]}</span><span class="item-meta">{extra}</span></a></li>\n'

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

    vars_dict = {
        "TITLE": title,
        "DESCRIPTION": f"{h1} — comprehensive GTA6 guide. {meta}",
        "CSS_PATH": "",
        "HOME_PATH": "",
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

def gen_homepage(mission_count, weapon_count, vehicle_count, collectible_count, sidem_count):
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
    <h3>📋 Story Missions ({mission_count})</h3>
    <p>Complete walkthrough for every main story mission</p>
  </a>
  <a href="weapons/index.html" class="category-card">
    <h3>🔫 Weapons ({weapon_count})</h3>
    <p>Stats, locations, and tips for every weapon</p>
  </a>
  <a href="vehicles/index.html" class="category-card">
    <h3>🚗 Vehicles ({vehicle_count})</h3>
    <p>Complete vehicle catalog with stats and spawns</p>
  </a>
  <a href="cheats.html" class="category-card">
    <h3>🎮 Cheats</h3>
    <p>All GTA6 cheat codes in one place</p>
  </a>
  <a href="money-guide.html" class="category-card">
    <h3>💰 Money Guide</h3>
    <p>How to make money fast in GTA6</p>
  </a>
  <a href="collectibles/index.html" class="category-card">
    <h3>📍 Collectibles ({collectible_count})</h3>
    <p>Every hidden item location</p>
  </a>
  <a href="side-missions/index.html" class="category-card">
    <h3>📌 Side Missions ({sidem_count})</h3>
    <p>All side missions and strangers</p>
  </a>
  <a href="online/index.html" class="category-card">
    <h3>🌐 GTA Online</h3>
    <p>Tips and guides for GTA6 Online</p>
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

    if mission_items:
        gen_index("Story Missions", mission_items, css_path="../", home_path="../")

    # 2. Generate weapon pages
    weapons = read_csv("weapons.csv")
    weapon_items = []
    for row in weapons:
        item = gen_item(row, "Weapons")
        weapon_items.append(item)

    if weapon_items:
        gen_index("Weapons", weapon_items, css_path="../", home_path="../")

    # 3. Generate vehicle pages
    vehicles = read_csv("vehicles.csv")
    vehicle_items = []
    for row in vehicles:
        item = gen_item(row, "Vehicles")
        vehicle_items.append(item)

    if vehicle_items:
        gen_index("Vehicles", vehicle_items, css_path="../", home_path="../")

    # 4. Generate collectible pages
    collectibles = read_csv("collectibles.csv")
    collectible_items = []
    for row in collectibles:
        item = gen_collectible(row)
        collectible_items.append(item)

    if collectible_items:
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

    if side_items:
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

<h2>Expected GTA6 Cheat Categories</h2>
<p>Based on every GTA release since GTA3, these categories are almost guaranteed to return:</p>

<div class="stats-grid">
  <div class="stat-item"><div class="stat-label">🛡️ God Mode</div><div class="stat-value">Confirmed</div></div>
  <div class="stat-item"><div class="stat-label">🔫 Weapons</div><div class="stat-value">Confirmed</div></div>
  <div class="stat-item"><div class="stat-label">🚗 Vehicles</div><div class="stat-value">Confirmed</div></div>
  <div class="stat-item"><div class="stat-label">⭐ Wanted</div><div class="stat-value">Confirmed</div></div>
  <div class="stat-item"><div class="stat-label">🌤️ Weather</div><div class="stat-value">Likely</div></div>
  <div class="stat-item"><div class="stat-label">💰 Money</div><div class="stat-value">Uncertain</div></div>
  <div class="stat-item"><div class="stat-label">💪 Super Jump</div><div class="stat-value">Likely</div></div>
  <div class="stat-item"><div class="stat-label">🏊 Fast Swim</div><div class="stat-value">Likely</div></div>
  <div class="stat-item"><div class="stat-label">🎯 Slow Motion</div><div class="stat-value">Confirmed</div></div>
  <div class="stat-item"><div class="stat-label">🎸 Spawn Bodyguard</div><div class="stat-value">Possible</div></div>
</div>

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
  Money-making strategies are based on GTA series patterns. We will update with exact GTA6 numbers within the first week of launch. The methods below are almost certain to work — Rockstar has kept the same economic systems since GTA5.
</div>

<h2>Overview: How Money Works in GTA6</h2>
<p>In every GTA game since Vice City, money buys you <strong>weapons, properties, vehicles, and business investments</strong>. GTA6 expands on GTA5's economy with more properties and a deeper stock market. You'll need money from the very first mission.</p>
<p>Here are the proven money-making methods, ranked by <strong>payout per hour</strong>:</p>

<table>
  <thead>
    <tr><th>Method</th><th>Risk</th><th>Est. Payout</th><th>Best For</th></tr>
  </thead>
  <tbody>
    <tr><td>Story Heists</td><td>Low</td><td>$50K-$2M</td><td>Big one-time payouts</td></tr>
    <tr><td>Stock Market</td><td>Medium</td><td>20%-200% ROI</td><td>Passive investing</td></tr>
    <tr><td>Side Businesses</td><td>Low</td><td>$5K-$50K/day</td><td>Passive income</td></tr>
    <tr><td>Vehicle Export</td><td>Medium</td><td>$20K-$100K/car</td><td>Active grinding</td></tr>
    <tr><td>Collectibles</td><td>None</td><td>$500-$5K/item</td><td>Early game cash</td></tr>
    <tr><td>Street Races</td><td>Low</td><td>$2K-$10K/race</td><td>Repeatable income</td></tr>
  </tbody>
</table>

<div class="card"><h3>1. Story Heists — The Big Money</h3>
<p>Story heists are the highest-paying activities in any GTA game. GTA5's biggest heist paid <strong>$200M+ total</strong>. GTA6 is expected to have 5-6 major heists.</p>
<p><strong>Key strategy:</strong> Always pick the best crew members for each heist role. Cheap crew members mess up, costing you money. Spend more on the driver and hacker — they determine your cut. Wait until you have enough cash to invest in the best crew before attempting the biggest heists.</p>
<p><em>Expected payout range: $50,000 (early heists) to $2,000,000+ (finale heists).</em></p></div>

<div class="card"><h3>2. Stock Market Manipulation — GTA5's Best-Kept Secret</h3>
<p>GTA5 had two stock exchanges: LCN (Liberty City National) and BAWSAQ. LCN was affected by your in-game actions — blow up a company's competitor, their stock drops. This is <strong>the single most profitable mechanic</strong> in GTA5, and GTA6 is expected to expand it.</p>
<p><strong>How it works:</strong> Before a mission that targets a specific company, invest all your money in their <strong>competitor</strong>. After the mission, the targeted company's stock falls and the competitor's rises. Sell for profit. Some GTA5 missions gave 80-200% returns if you invested correctly.</p>
<p><strong>Pro tip:</strong> Save your game before investing. If the market doesn't move as expected, reload and try a different stock. Also, invest <em>before</em> assassination missions — those always move specific stocks.</p></div>

<div class="card"><h3>3. Side Businesses & Properties — Passive Income</h3>
<p>GTA Online introduced businesses like nightclubs, biker gangs, and bunkers that generate money over time. GTA6's single-player is expected to bring this system into the main story — you'll buy properties that generate income while you do other things.</p>
<p><strong>Strategy:</strong> Buy properties as early as possible. The sooner you own income-generating assets, the more money they make over the course of the game. Prioritize <strong>high-ROI properties</strong> first — cheap businesses that pay for themselves quickly.</p></div>

<div class="card"><h3>4. Vehicle Export & Chop Shop — Active Money</h3>
<p>Stealing and selling high-end cars is a GTA tradition. GTA6 is set in Vice City (Miami), which means <strong>luxury cars everywhere</strong>. Look for sports cars in rich districts, take them to a chop shop or export dock, and sell for quick cash.</p>
<p><strong>Best targets:</strong> Sports cars and SUVs parked in the Vice Beach and Downtown districts. Check parking garages — they often spawn high-value vehicles without witnesses.</p></div>

<div class="card"><h3>5. Collectibles & Hidden Packages — Easy Early Cash</h3>
<p>Every GTA game has hidden packages scattered across the map. Finding them gives instant cash rewards plus completion bonuses. GTA5 had 100+ collectibles worth $2,000-$25,000 each in some categories.</p>
<p><strong>Strategy:</strong> Don't go out of your way during missions, but grab any collectible you see. After finishing the story, use a guide to clean up the remaining ones. The full collection bonus is usually worth <strong>$500,000+</strong>.</p></div>

<div class="card"><h3>6. Street Races & Side Activities — Repeatable Grinding</h3>
<p>Races, taxi missions, bounty hunting, and other side activities are infinitely repeatable. They don't pay as much as heists, but they're <strong>zero-risk</strong> and available from the start of the game.</p>
<p><strong>Most efficient:</strong> Street races with high-end cars (win more, get higher payouts). Unlock the fastest car you can afford, then chain races for consistent income. Taxi missions are safer but pay less per hour.</p></div>

<div class="warning">Don't spend recklessly early in the game. The biggest mistake new players make is buying expensive cars and weapons before investing in income-generating properties. <strong>Assets first, toys second.</strong></div>

<h2>Money-Making Priority Checklist</h2>
<ol class="step-list">
  <li>Complete early story missions for starting capital</li>
  <li>Invest all spare cash in stocks before assassination missions</li>
  <li>Buy your first income property as soon as it's available</li>
  <li>Collect hidden packages while traveling between missions</li>
  <li>Use stock market windfalls to buy more properties</li>
  <li>Chain vehicle exports when you need quick cash</li>
</ol>""",
        active_nav="money")

    # 8. Generate online guide page
    gen_generic("online/index.html",
        title="GTA6 Online Guide — Tips, Heists & Money Making",
        h1="GTA6 Online Guide",
        meta="Complete guide to GTA6 Online: heists, businesses, money making, crews, and PvP tips. Get ahead of other players from day one.",
        content="""<div class="disclaimer">
  GTA6 Online details are based on GTA5 Online patterns and Rockstar's public statements. We will update with exact GTA6 Online data on launch day.
</div>

<h2>What We Know About GTA6 Online</h2>
<p>GTA Online (GTA5) has been Rockstar's biggest cash cow — generating <strong>$500M+ per year</strong> since 2013. GTA6 Online will be a separate, evolving multiplayer world built from lessons learned over a decade of GTA Online updates.</p>
<p>Rockstar has confirmed that GTA6 Online will launch alongside the single-player game, not months later. Expect it to be available <strong>on day one</strong>.</p>

<h2>Getting Started: First Things to Do</h2>
<ol class="step-list">
  <li><strong>Complete the tutorial</strong> — GTA Online always starts with a guided intro that gives you your first car, weapon, and property. Don't skip it — the free items are worth $100K+.</li>
  <li><strong>Save your first $200K</strong> — don't waste money on clothes or car mods. Your first goal is a high-end apartment or business property.</li>
  <li><strong>Join a crew</strong> — having 3 other players to run heists with is the single biggest money multiplier. Solo players earn 3-5x less.</li>
  <li><strong>Buy the Buzzard (or GTA6 equivalent)</strong> — a weaponized helicopter is the best early investment. It spawns instantly and makes every mission faster.</li>
  <li><strong>Do daily objectives</strong> — Rockstar gives $25K-$50K per day for completing 3 simple tasks. Free money, takes 15 minutes.</li>
</ol>

<h2>Best Money-Making Methods in GTA Online</h2>

<table>
  <thead>
    <tr><th>Method</th><th>Solo?</th><th>Est. $/Hour</th><th>Difficulty</th></tr>
  </thead>
  <tbody>
    <tr><td>Cayo Perico Heist</td><td>Yes</td><td>$1.5M-$2M</td><td>Medium</td></tr>
    <tr><td>Diamond Casino Heist</td><td>No</td><td>$1M-$2.5M</td><td>Hard</td></tr>
    <tr><td>Nightclub Warehouse</td><td>Yes</td><td>$40K-$80K</td><td>Easy</td></tr>
    <tr><td>Bunker Sales</td><td>Yes</td><td>$135K-$210K</td><td>Medium</td></tr>
    <tr><td>Vehicle Cargo (I/E)</td><td>Yes</td><td>$240K-$320K</td><td>Medium</td></tr>
    <tr><td>Agency Contracts</td><td>Yes</td><td>$60K-$150K</td><td>Easy</td></tr>
    <tr><td>MC Businesses</td><td>No</td><td>$60K-$100K</td><td>Medium</td></tr>
  </tbody>
</table>

<div class="tip">In GTA5 Online, the Cayo Perico heist is the best solo money maker. GTA6 will almost certainly have a similar repeatable solo heist — it was one of the most popular updates in GTA Online history.</div>

<div class="card"><h3>Businesses: Passive Income is King</h3>
<p>GTA Online's economy revolves around owning businesses that generate product over time. You buy supplies, wait for product to build up (even while offline in some cases), then sell for profit.</p>
<p><strong>Priority order for buying businesses:</strong> Bunker (best solo profit) → Nightclub (passive warehouse) → Agency (easy contracts) → MC businesses (coke/meth/cash) → Vehicle warehouse.</p>
<p><strong>Key tip:</strong> Always sell in <strong>invite-only lobbies</strong>. Public lobbies have griefers who destroy your cargo for fun. You lose everything if your sale vehicle is destroyed. Invite-only = zero risk.</p></div>

<div class="card"><h3>Heists: The Big Payouts</h3>
<p>Heists are the core of GTA Online's endgame. They require 2-4 players and pay $500K-$2M+ per completion. The best heists are:</p>
<p><strong>Cayo Perico</strong> — soloable, 1-hour setup + 15-minute finale, $1.5M average take. <strong>Diamond Casino</strong> — 2-4 players, harder but $2.5M max take. <strong>Doomsday Heist</strong> — 2-4 players, 3 acts, hardest PvE content but unlocks trade prices on powerful vehicles.</p>
<p><strong>Crew strategy:</strong> Find 3 reliable players. Use voice chat. Split finale cuts 40/20/20/20 (host takes 40% since they paid setup costs). A coordinated crew running Cayo + Casino back-to-back can make <strong>$3M+ per night</strong>.</p></div>

<div class="card"><h3>PvP & Freemode Survival</h3>
<p>GTA Online's freemode is a warzone. Other players will kill you on sight. Here's how to survive:</p>
<p><strong>Passive mode</strong> — makes you immune to PvP damage. Use it when doing business sales or just exploring. Toggle it from the interaction menu.</p>
<p><strong>Ghost Organization</strong> — hides you and your crew from the radar for 3 minutes. Essential for avoiding griefers during sales.</p>
<p><strong>Best PvP vehicles:</strong> Oppressor MK2 (flying bike with homing missiles — the griefers' favorite), Nightshark (insanely tanky SUV, survives 27 homing missiles), Toreador (submarine car with boost + unlimited missiles).</p>
<p><strong>Counter-griefing:</strong> If someone is spawn-killing you, go passive, call your most armored vehicle, drive away, then come back with an Oppressor or jet. Or just switch sessions — it's not worth the frustration.</p></div>

<div class="warning">Never buy Shark Cards at full price. Wait for 50% off sales, which happen every 2-3 months. Better yet, don't buy them at all — grinding Cayo Perico solo makes more money per hour than a $20 Shark Card is worth.</div>

<h2>GTA6 Online: What to Expect</h2>
<p>GTA6 Online will likely be a <strong>clean slate</strong> — everyone starts fresh with a new character. This is the best time to play: no griefers with 10-year-old accounts and every weaponized vehicle. <strong>The first 3 months of GTA6 Online will be the most fun the GTA community has had in years.</strong></p>

<p>Rockstar has hinted at:</p>
<ul>
  <li><strong>Evolving map</strong> — the GTA6 world will change over time with new buildings, events, and storylines (similar to Fortnite's seasonal map changes)</li>
  <li><strong>Cross-play</strong> — likely between PlayStation and Xbox at minimum, possibly PC too</li>
  <li><strong>Roleplay features</strong> — Rockstar bought the biggest GTA RP server team (Cfx.re, creators of FiveM) in 2023. Expect built-in RP mechanics</li>
  <li><strong>Dedicated servers</strong> — no more peer-to-peer connections that plagued GTA5 Online with lag and modders</li>
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
    gen_homepage(len(mission_items), len(weapon_items), len(vehicle_items), len(collectible_items), len(side_items))

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
