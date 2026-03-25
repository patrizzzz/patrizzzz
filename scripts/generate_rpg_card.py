"""
RPG Character Card Generator for GitHub Profile README
Fetches real GitHub stats and maps them to RPG-style stats.
"""

import os
import re
import math
import requests
from datetime import datetime, timezone

USERNAME = os.environ.get("GITHUB_USERNAME", "patrizzzz")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# ── GitHub data fetchers ───────────────────────────────────────────────────────

def get_user():
    r = requests.get(f"https://api.github.com/users/{USERNAME}", headers=HEADERS)
    return r.json()

def get_repos():
    repos, page = [], 1
    while True:
        r = requests.get(
            f"https://api.github.com/users/{USERNAME}/repos",
            headers=HEADERS,
            params={"per_page": 100, "page": page, "type": "owner"},
        )
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos

def get_commit_count():
    """Use the search API to count total commits by the user."""
    r = requests.get(
        "https://api.github.com/search/commits",
        headers={**HEADERS, "Accept": "application/vnd.github.cloak-preview+json"},
        params={"q": f"author:{USERNAME}", "per_page": 1},
    )
    return r.json().get("total_count", 0)

def get_contribution_streak():
    """Fetch contribution calendar via GraphQL to calculate streak."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        headers=HEADERS,
        json={"query": query, "variables": {"login": USERNAME}},
    )
    data = r.json()
    try:
        cal   = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        total = cal["totalContributions"]
        days  = [d for w in cal["weeks"] for d in w["contributionDays"]]

        # Calculate current streak (count from today backwards)
        today  = datetime.now(timezone.utc).date().isoformat()
        streak = 0
        active = False
        for day in reversed(days):
            if day["date"] > today:
                continue
            if day["contributionCount"] > 0:
                streak += 1
                active = True
            elif active:
                break
        return total, streak
    except Exception:
        return 0, 0

def get_merged_pr_count():
    """Count merged pull requests by the user."""
    r = requests.get(
        "https://api.github.com/search/issues",
        headers=HEADERS,
        params={"q": f"author:{USERNAME} type:pr is:merged", "per_page": 1},
    )
    return r.json().get("total_count", 0)

# ── Stat calculation ──────────────────────────────────────────────────────────

# Which languages map to which RPG stat
STAT_LANG_MAP = {
    "STR": ["Python", "Go", "Rust", "C", "C++"],          # backend / systems
    "INT": ["Jupyter Notebook", "R", "Julia"],             # data science / ML
    "DEX": ["Kotlin", "Swift", "Dart", "Java"],            # mobile
    "WIS": ["JavaScript", "TypeScript", "HTML", "CSS",    # frontend / web
             "Vue", "Svelte"],
    "AGI": ["Shell", "Dockerfile", "HCL", "YAML"],        # devops / infra
}

# ✅ FIX 1: Added merged_prs as a proper parameter instead of kwargs
def calc_stats(repos, commits, streak, merged_prs=0):
    # Total stars and forks
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0) for r in repos)

    # Language bytes across all repos
    lang_bytes: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        r = requests.get(repo["languages_url"], headers=HEADERS)
        for lang, count in r.json().items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + count

    total_bytes = sum(lang_bytes.values()) or 1

    def lang_score(stat_key):
        langs = STAT_LANG_MAP.get(stat_key, [])
        raw = sum(lang_bytes.get(l, 0) for l in langs) / total_bytes
        return min(int(raw * 300 + 30), 99)  # scale to 30-99

    str_val = lang_score("STR")
    int_val = lang_score("INT")
    dex_val = lang_score("DEX")
    wis_val = lang_score("WIS")
    agi_val = lang_score("AGI")

    # VIT = commit activity (capped 99)
    vit_val = min(int(commits / 50) + 40, 99)

    # XP = stars × 200 + forks × 100 + commits × 10 + merged_prs × 50
    xp = total_stars * 200 + total_forks * 100 + commits * 10 + merged_prs * 50

    # Level = sqrt(xp / 1000) capped at 99
    level = min(int(math.sqrt(xp / 1000)) + 1, 99)

    # XP progress to next level
    current_threshold = (level - 1) ** 2 * 1000
    next_threshold    = level ** 2 * 1000
    xp_pct = int((xp - current_threshold) / max(next_threshold - current_threshold, 1) * 100)
    xp_pct = max(1, min(xp_pct, 99))

    return {
        "STR": str_val, "INT": int_val, "DEX": dex_val,
        "WIS": wis_val, "AGI": agi_val, "VIT": vit_val,
        "level": level, "xp": xp, "xp_pct": xp_pct,
        "stars": total_stars, "streak": streak, "commits": commits,
        "merged_prs": merged_prs,
        "repos": len([r for r in repos if not r.get("fork")]),
    }

# ── SVG renderer ─────────────────────────────────────────────────────────────

def get_style():
    return """
    <style>
        .base { fill: #1a1a1a; stroke: #333; stroke-width: 1; }
        .text { font-family: 'JetBrains Mono', 'Segoe UI', monospace; fill: #c9d1d9; }
        .header { font-size: 24px; font-weight: 700; fill: #ffffff; }
        .subheader { font-size: 14px; fill: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
        .label { font-size: 14px; font-weight: 600; fill: #c9d1d9; }
        .value { font-size: 14px; font-weight: 700; fill: #ffffff; }
        .lvl-badge { fill: #0d1117; stroke: #0891b2; stroke-width: 1.5; }
        .lvl-text { font-size: 13px; font-weight: 800; fill: #0891b2; }
        .stat-bg { fill: #2d2d2d; rx: 4; }
        .bar-bg { fill: #121212; rx: 3; }
        .xp-bg { fill: #121212; rx: 5; }
        .tag-bg { fill: #0d1117; stroke: #30363d; stroke-width: 1; rx: 4; }
        .tag-text { font-size: 11px; font-weight: 600; }
        .footer-text { font-size: 11px; fill: #8b949e; }
        .status-dot { fill: #10b981; }
    </style>
    """

def generate_svg(s):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # SVG Dimensions
    W, H = 840, 650
    
    # Progress bar width calculations
    def get_bar_w(val, max_w=320):
        return (val / 100) * max_w

    # Skill tags
    all_skills = [
        ("Python", "#0891b2"), ("Django", "#0891b2"), ("Flask", "#0891b2"), ("PostgreSQL", "#0891b2"),
        ("TensorFlow", "#7c3aed"), ("PyTorch", "#7c3aed"), ("scikit-learn", "#7c3aed"),
        ("Kotlin", "#10b981"), ("Android", "#10b981"), ("Firebase", "#10b981"),
        ("JavaScript", "#f59e0b"), ("HTML/CSS", "#f59e0b")
    ]
    
    skill_tags = ""
    x_off, y_off = 0, 25
    for i, (name, color) in enumerate(all_skills):
        if i == 4 or i == 8:
            x_off = 0
            y_off += 35
        tag_w = len(name) * 8 + 20
        skill_tags += f"""
        <g transform="translate({x_off}, {y_off})">
            <rect width="{tag_w}" height="24" class="tag-bg" style="stroke: {color}; opacity: 0.6;"/>
            <text x="{tag_w/2}" y="16" class="text tag-text" text-anchor="middle" style="fill: {color};">{name}</text>
        </g>
        """
        x_off += tag_w + 10

    svg = f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg">
    {get_style()}
    <rect width="{W}" height="{H}" rx="15" class="base"/>
    
    <!-- Top Section -->
    <g transform="translate(40, 40)">
        <rect width="80" height="80" rx="12" class="tag-bg" style="stroke: #0891b2; stroke-width: 2;"/>
        <path d="M40 30C45.5228 30 50 34.4772 50 40C50 45.5228 45.5228 50 40 50C34.4772 50 30 45.5228 30 40C30 34.4772 34.4772 30 40 30Z" stroke="#0891b2" stroke-width="2.5"/>
        <path d="M25 58C25 54 30 51 40 51C50 51 55 54 55 58V62H25V58Z" stroke="#0891b2" stroke-width="2.5"/>
        
        <g transform="translate(110, 5)">
            <text x="0" y="8" class="text subheader">⚔ SOFTWARE DEVELOPER</text>
            <text x="0" y="42" class="text header">PATRIZZZZ</text>
            
            <g transform="translate(0, 55)">
                <rect width="60" height="24" rx="4" class="lvl-badge"/>
                <text x="30" y="17" class="text lvl-text" text-anchor="middle">LVL {s["level"]:02d}</text>
                <text x="75" y="17" class="text label" style="fill: #8b949e;">Class: <tspan style="fill: #ffffff;">Full-Stack Mage</tspan></text>
            </g>
        </g>
    </g>

    <line x1="40" y1="150" x2="{W-40}" y2="150" stroke="#333" stroke-dasharray="4 4"/>

    <!-- Core Stats Section -->
    <g transform="translate(40, 185)">
        <text x="0" y="0" class="text subheader">── CORE STATS ─────────────────────</text>
        
        <g transform="translate(0, 35)">
            <text x="0" y="0" class="text label">STR Backend</text>
            <text x="320" y="0" class="text value" text-anchor="end">{s["STR"]}</text>
            <rect y="10" width="320" height="8" class="bar-bg"/>
            <rect y="10" width="{get_bar_w(s["STR"])}" height="8" style="fill: #0891b2; rx: 3;"/>
            
            <g transform="translate(0, 45)">
                <text x="0" y="0" class="text label">DEX Mobile</text>
                <text x="320" y="0" class="text value" text-anchor="end">{s["DEX"]}</text>
                <rect y="10" width="320" height="8" class="bar-bg"/>
                <rect y="10" width="{get_bar_w(s["DEX"])}" height="8" style="fill: #10b981; rx: 3;"/>
            </g>
            
            <g transform="translate(0, 90)">
                <text x="0" y="0" class="text label">AGI DevOps</text>
                <text x="320" y="0" class="text value" text-anchor="end">{s["AGI"]}</text>
                <rect y="10" width="320" height="8" class="bar-bg"/>
                <rect y="10" width="{get_bar_w(s["AGI"])}" height="8" style="fill: #ef4444; rx: 3;"/>
            </g>
        </g>
        
        <g transform="translate(400, 35)">
            <text x="0" y="0" class="text label">INT AI / ML</text>
            <text x="320" y="0" class="text value" text-anchor="end">{s["INT"]}</text>
            <rect y="10" width="320" height="8" class="bar-bg"/>
            <rect y="10" width="{get_bar_w(s["INT"])}" height="8" style="fill: #7c3aed; rx: 3;"/>
            
            <g transform="translate(0, 45)">
                <text x="0" y="0" class="text label">WIS Frontend</text>
                <text x="320" y="0" class="text value" text-anchor="end">{s["WIS"]}</text>
                <rect y="10" width="320" height="8" class="bar-bg"/>
                <rect y="10" width="{get_bar_w(s["WIS"])}" height="8" style="fill: #f59e0b; rx: 3;"/>
            </g>
            
            <g transform="translate(0, 90)">
                <text x="0" y="0" class="text label">VIT Commits</text>
                <text x="320" y="0" class="text value" text-anchor="end">{s["VIT"]}</text>
                <rect y="10" width="320" height="8" class="bar-bg"/>
                <rect y="10" width="{get_bar_w(s["VIT"])}" height="8" style="fill: #06b6d4; rx: 3;"/>
            </g>
        </g>
    </g>

    <!-- Experience Section -->
    <g transform="translate(40, 355)">
        <text x="0" y="0" class="text subheader">── EXPERIENCE ─────────────────────</text>
        <text x="0" y="30" class="text label" style="font-weight: 700;">Overall Progress</text>
        <text x="{W-80}" y="30" class="text value" text-anchor="end" style="fill: #06b6d4;">{s["xp_pct"]}% → LVL {s["level"]+1}</text>
        
        <rect y="40" width="{W-80}" height="14" class="xp-bg"/>
        <rect y="40" width="{(s['xp_pct']/100) * (W-80)}" height="14" style="fill: url(#xp-grad); rx: 5;"/>
        <defs>
            <linearGradient id="xp-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#3b82f6" />
                <stop offset="100%" stop-color="#8b5cf6" />
            </linearGradient>
        </defs>
        
        <text x="0" y="72" class="footer-text">0 XP</text>
        <text x="{(W-80)/2}" y="72" class="footer-text" text-anchor="middle">Current: {s['xp']:,} XP</text>
        <text x="{W-80}" y="72" class="footer-text" text-anchor="end">100,000 XP</text>
    </g>

    <!-- Skills Section -->
    <g transform="translate(40, 480)">
        <text x="0" y="0" class="text subheader">── EQUIPPED SKILLS ─────────────────</text>
        {skill_tags}
    </g>

    <line x1="40" y1="615" x2="{W-40}" y2="615" stroke="#333" stroke-dasharray="4 4"/>

    <!-- Footer -->
    <g transform="translate(40, 635)">
        <circle cx="5" cy="-4" r="3" class="status-dot"/>
        <text x="15" y="0" class="footer-text">Active – Building in public</text>
        <text x="{W-80}" y="0" class="footer-text" text-anchor="end">github.com/patrizzzz</text>
        <text x="{W-180}" y="0" class="footer-text" text-anchor="end">Server: PH-01</text>
    </g>
</svg>"""
    return svg

# ── README patcher ────────────────────────────────────────────────────────────

def patch_readme(svg_content: str, path: str = "README.md"):
    # Save the SVG
    svg_path = "rpg-card.svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    # ✅ FIX 2: Handle missing README.md gracefully
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""  # Start fresh if README doesn't exist yet

    # Create the new block
    new_block = (
        "<!--RPG_CARD_START-->\n"
        '<div align="center">\n'
        f'  <img src="./{svg_path}" alt="RPG Character Card" width="100%" />\n'
        '</div>\n'
        "<!--RPG_CARD_END-->"
    )

    # Remove existing RPG_CARD block if any
    pattern = r"<!--RPG_CARD_START-->.*?<!--RPG_CARD_END-->"
    content = re.sub(pattern, "", content, flags=re.DOTALL).strip()

    # Prepend new block to top
    content = f"{new_block}\n\n{content}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ README.md updated and {svg_path} created successfully.")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🎮 Fetching stats for @{USERNAME}...")

    try:
        user    = get_user()
        repos   = get_repos()
        commits = get_commit_count()
        prs     = get_merged_pr_count()
        total_contributions, streak = get_contribution_streak()

        print(f"  • {len(repos)} repos | {commits} commits | {prs} PRs | {streak}d streak")

        # ✅ FIX 1: merged_prs passed correctly as keyword argument
        stats = calc_stats(repos, commits, streak, merged_prs=prs)
        print(f"  • LV.{stats['level']} | {stats['xp']:,} XP | {stats['xp_pct']}% to next")

        svg = generate_svg(stats)
        patch_readme(svg)
    except Exception as e:
        print(f"❌ Error generating RPG card: {e}")
        raise  # ✅ Re-raise so GitHub Actions shows the real error
