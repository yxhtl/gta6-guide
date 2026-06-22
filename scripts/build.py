#!/usr/bin/env python3
"""
GTA6 Guide - Static Site Generator
Reads CSV data files, applies HTML templates, generates all pages + sitemap.
Usage: python scripts/build.py
"""

import csv
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

# ---- Page generators ----

def gen_mission(row, i, prev_filename, next_filename):
    """Generate a single mission page."""
    tpl = read_template("mission.html")
    slug = make_slug(row.get("mission_name", f"mission-{i+1}"))
    steps_html = ""
    for s in row.get("steps", "").split("|"):
        s = s.strip()
        if s:
            steps_html += f"<li>{s}</li>\n"

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = '<div class="tip">' + tips + "</div>"

    trivia = row.get("trivia", "").strip()
    trivia_html = ""
    if trivia:
        trivia_html = f"<h2>Trivia</h2><p>{trivia}</p>"

    prev_html = ""
    if prev_filename:
        prev_html = f'<a href="{prev_filename}">← Previous Mission</a>'
    next_html = ""
    if next_filename:
        next_html = f'<a href="{next_filename}">Next Mission →</a>'

    vars_dict = {
        "TITLE": row["mission_name"],
        "DESCRIPTION": f"Complete walkthrough for {row['mission_name']} in GTA6. Chapter: {row.get('chapter','?')}. {row.get('tips','')[:120]}",
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "MISSION_NAME": row["mission_name"],
        "CHAPTER": row.get("chapter", "TBD"),
        "DIFFICULTY": row.get("difficulty", "Normal"),
        "REWARD": row.get("reward", "TBD"),
        "STEPS": steps_html,
        "TIPS_SECTION": tips_html,
        "TRIVIA_SECTION": trivia_html,
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
    """Generate a single weapon or vehicle page."""
    tpl = read_template("item.html")
    name = row.get("name", "Unknown Item")
    slug = make_slug(name)
    cat_lower = category.lower()

    # Build stats grid
    stats_html = ""
    for key, val in row.items():
        if key in ("name", "type_tag", "description", "acquisition", "tips"):
            continue
        if val and val.strip():
            stats_html += f'<div class="stat-item"><div class="stat-label">{key.replace("_"," ").title()}</div><div class="stat-value">{val}</div></div>\n'

    tips = row.get("tips", "").strip()
    tips_html = ""
    if tips:
        tips_html = f'<h2>Tips</h2><div class="tip">{tips}</div>'

    weapons_active = ' class="active"' if category == "Weapons" else ""
    vehicles_active = ' class="active"' if category == "Vehicles" else ""

    vars_dict = {
        "TITLE": f"{name} - GTA6 {category}",
        "DESCRIPTION": f"Stats, location, and how to get {name} in GTA6. {row.get('description','')[:120]}",
        "CSS_PATH": "../",
        "HOME_PATH": "../",
        "ITEM_NAME": name,
        "CATEGORY": category,
        "CATEGORY_LOWER": cat_lower,
        "TYPE_TAG": row.get("type_tag", category),
        "STATS": stats_html,
        "DESCRIPTION_TEXT": f"<p>{row.get('description','Stats and details for ' + name + ' in GTA6.')}</p>",
        "ACQUISITION": row.get("acquisition", "TBD — game not yet released."),
        "TIPS_SECTION": tips_html,
        "WEAPONS_ACTIVE": weapons_active,
        "VEHICLES_ACTIVE": vehicles_active,
    }
    out_dir = "weapons" if category == "Weapons" else "vehicles"
    filename = f"{slug}.html"
    write_page(f"{out_dir}/{filename}", replace_all(tpl, vars_dict))
    return {"name": name, "type_tag": row.get("type_tag", ""), "filename": filename}

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

def gen_homepage(mission_count, weapon_count, vehicle_count):
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
    <h3>📍 Collectibles</h3>
    <p>Every hidden item location</p>
  </a>
  <a href="side-missions/index.html" class="category-card">
    <h3>📌 Side Missions</h3>
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

    # 4. Generate cheats page (placeholder)
    gen_generic("cheats.html",
        title="GTA6 Cheats & Cheat Codes",
        h1="GTA6 Cheats & Cheat Codes",
        meta="All working GTA6 cheat codes. Updated after game release.",
        content="""<div class="disclaimer">
  Cheat codes will be added here as soon as GTA6 releases and codes are discovered.
  Bookmark this page and check back after launch!
</div>
<p>GTA6 cheat codes are not yet available. Rockstar typically releases cheats alongside or shortly after the game launch. This page will be updated immediately when codes are confirmed.</p>
<h2>What to Expect</h2>
<p>Based on previous GTA titles, GTA6 cheats will likely include:</p>
<ul style="list-style:disc;margin-left:20px;margin-bottom:16px;">
  <li>Invincibility / God Mode</li>
  <li>Weapon and ammo spawns</li>
  <li>Vehicle spawns</li>
  <li>Wanted level manipulation</li>
  <li>Weather and time control</li>
  <li>Money cheats (if available)</li>
</ul>
<p>Stay tuned — we'll have the full list the moment codes are confirmed.</p>""",
        active_nav="cheats")

    # 5. Generate money guide (placeholder)
    gen_generic("money-guide.html",
        title="GTA6 Money Guide — How to Make Money Fast",
        h1="GTA6 Money Guide",
        meta="Best ways to earn money fast in GTA6. Heists, businesses, stock market, side activities, and more.",
        content="""<div class="disclaimer">
  Money-making strategies will be detailed here after GTA6 releases. Bookmark and come back!
</div>
<h2>Expected Money-Making Methods</h2>
<p>Based on GTA series history, here are the likely ways to earn money in GTA6:</p>

<div class="card"><h3>1. Story Missions & Heists</h3><p>Main story missions are always the primary source of big payouts in GTA games. Expect major heists to be the biggest earners.</p></div>
<div class="card"><h3>2. Stock Market</h3><p>GTA5 introduced the stock market mechanic — invest before missions that affect specific companies. GTA6 is expected to expand this system.</p></div>
<div class="card"><h3>3. Side Businesses</h3><p>Properties, nightclubs, and businesses that generate passive income — a staple since GTA Online.</p></div>
<div class="card"><h3>4. Side Activities</h3><p>Races, taxi missions, bounty hunting, and other repeatable activities for steady cash.</p></div>
<div class="card"><h3>5. Collectibles & Hidden Rewards</h3><p>Hidden packages, stunt jumps, and collectibles often come with cash rewards.</p></div>

<p>Full detailed strategies will be published within the first week of launch.</p>""",
        active_nav="money")

    # 6. Generate placeholder index pages for empty categories
    for cat_name, cat_dir in [("Collectibles", "collectibles"), ("Side Missions", "side-missions"), ("Online", "online")]:
        tpl = read_template("index-template.html")
        vars_dict = {
            "TITLE": f"GTA6 {cat_name}",
            "DESCRIPTION": f"Complete guide to {cat_name.lower()} in GTA6.",
            "CSS_PATH": "../",
            "HOME_PATH": "../",
            "CATEGORY_NAME": cat_name,
            "CATEGORY_DESC": f"Content coming after GTA6 release.",
            "ITEM_LIST": '<li style="color:var(--text-dim);padding:16px;">Content will be added after game release. Stay tuned!</li>',
            "MISSIONS_ACTIVE": "",
            "WEAPONS_ACTIVE": "",
            "VEHICLES_ACTIVE": "",
        }
        write_page(f"{cat_dir}/index.html", replace_all(tpl, vars_dict))

    # 7. Generate privacy page
    gen_generic("privacy.html",
        title="Privacy Policy - GTA6 Guide",
        h1="Privacy Policy",
        meta="Privacy policy for GTA6 Guide.",
        content="""<p>GTA6 Guide uses Google AdSense to serve ads. Google may use cookies to serve ads based on your prior visits to this or other websites.</p>
<p>We do not collect, store, or share any personal information.</p>
<p>This site is a fan project and is not affiliated with Rockstar Games or Take-Two Interactive.</p>""",
        active_nav="")

    # 8. Generate homepage
    gen_homepage(len(mission_items), len(weapon_items), len(vehicle_items))

    # 9. Generate sitemap & robots
    pages = ["", "privacy.html", "cheats.html", "money-guide.html",
             "story-missions/", "weapons/", "vehicles/",
             "collectibles/", "side-missions/", "online/"]
    for m in mission_items:
        pages.append(f"story-missions/{m['filename']}")
    for w in weapon_items:
        pages.append(f"weapons/{w['filename']}")
    for v in vehicle_items:
        pages.append(f"vehicles/{v['filename']}")

    gen_sitemap(pages)
    gen_robots()

    print(f"\nDone! Generated {len(pages)} URLs.")
    print(f"   Missions: {len(mission_items)} | Weapons: {len(weapon_items)} | Vehicles: {len(vehicle_items)}")

if __name__ == "__main__":
    main()
