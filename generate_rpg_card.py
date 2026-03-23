"""
RPG Character Card Generator for GitHub Profile README
Fetches real GitHub stats and maps them to RPG-style stats.
"""

import os
import re
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
        today     = datetime.now(timezone.utc).date().isoformat()
        streak    = 0
        active    = False
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

def calc_stats(repos, commits, streak):
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

    # XP = stars × 200 + forks × 100 + commits × 10
    xp = total_stars * 200 + total_forks * 100 + commits * 10

    # Level = sqrt(xp / 1000) capped at 99
    import math
    level = min(int(math.sqrt(xp / 1000)) + 1, 99)

    # XP progress to next level: what % of the way to the next level threshold
    current_threshold = (level - 1) ** 2 * 1000
    next_threshold    = level ** 2 * 1000
    xp_pct = int((xp - current_threshold) / max(next_threshold - current_threshold, 1) * 100)
    xp_pct = max(1, min(xp_pct, 99))

    return {
        "STR": str_val, "INT": int_val, "DEX": dex_val,
        "WIS": wis_val, "AGI": agi_val, "VIT": vit_val,
        "level": level, "xp": xp, "xp_pct": xp_pct,
        "stars": total_stars, "streak": streak, "commits": commits,
        "repos": len([r for r in repos if not r.get("fork")]),
    }

# ── Bar renderer ─────────────────────────────────────────────────────────────

def bar(value, length=20):
    filled = round(value / 100 * length)
    return "█" * filled + "░" * (length - filled)

def stat_line(label, abbr, val, color_hint=""):
    return f"| `{abbr}` | **{label}** | `{bar(val)}` | **{val}**/99 |"

# ── Markdown card builder ─────────────────────────────────────────────────────

def build_card(s):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    xp_bar_len   = 30
    xp_filled    = round(s["xp_pct"] / 100 * xp_bar_len)
    xp_bar       = "█" * xp_filled + "░" * (xp_bar_len - xp_filled)

    return f"""## `> character --stats`

<!--RPG_CARD_START-->
<div align="center">

```
╔══════════════════════════════════════════════════════╗
║            ⚔  DEVELOPER CHARACTER CARD  ⚔            ║
╚══════════════════════════════════════════════════════╝
```

</div>

<div align="center">

| | | |
|:---:|:---:|:---:|
| **NAME** | **CLASS** | **SERVER** |
| `PATRICK` | `Full-Stack Mage` | `PH-01` |
| **LEVEL** | **TOTAL XP** | **STREAK** |
| `LV. {s["level"]:02d}` | `{s["xp"]:,} XP` | `{s["streak"]} days 🔥` |

</div>

<div align="center">

```
── CORE STATS ──────────────────────────────────────────
```

| Stat | Attribute | Progress | Value |
|:----:|:----------|:---------|------:|
{stat_line("Backend Power", "STR", s["STR"])}
{stat_line("AI / ML Intel", "INT", s["INT"])}
{stat_line("Mobile Agility", "DEX", s["DEX"])}
{stat_line("Frontend Wisdom", "WIS", s["WIS"])}
{stat_line("DevOps Finesse", "AGI", s["AGI"])}
{stat_line("Commit Vitality", "VIT", s["VIT"])}

</div>

<div align="center">

```
── EXPERIENCE ──────────────────────────────────────────
  LV.{s["level"]:02d}  [{xp_bar}]  LV.{s["level"]+1:02d}
        Progress to next level: {s["xp_pct"]}%
── ACHIEVEMENTS ────────────────────────────────────────
  ★ {s["stars"]:>5} stars earned        ⚔ {s["commits"]:>5} total commits
  ⚡ {s["repos"]:>5} original repos      🔥 {s["streak"]:>5} day streak
── EQUIPPED SKILLS ─────────────────────────────────────
  [Python] [Django] [Flask] [PostgreSQL] [Firebase]
  [TensorFlow] [PyTorch] [scikit-learn]
  [Kotlin] [Android] [JavaScript] [HTML] [CSS]
```

</div>

<div align="center">
  <sub><code>// last synced: {now} · auto-updated daily via GitHub Actions</code></sub>
</div>

<!--RPG_CARD_END-->"""

# ── README patcher ────────────────────────────────────────────────────────────

def patch_readme(card: str, path: str = "README.md"):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!--RPG_CARD_START-->.*?<!--RPG_CARD_END-->"
    inner    = re.search(r"(<!--RPG_CARD_START-->.*?<!--RPG_CARD_END-->)", card, re.DOTALL)
    new_block = inner.group(1) if inner else card

    if re.search(pattern, content, re.DOTALL):
        content = re.sub(pattern, new_block, content, flags=re.DOTALL)
    else:
        # If markers don't exist yet, replace the old stats section header
        old_header = "## `> git log --stat`"
        if old_header in content:
            content = content.replace(old_header, card)
        else:
            content += "\n\n" + card

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ README.md updated successfully.")

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🎮 Fetching stats for @{USERNAME}...")

    user    = get_user()
    repos   = get_repos()
    commits = get_commit_count()
    total_contributions, streak = get_contribution_streak()

    print(f"  • {len(repos)} repos | {commits} commits | {streak}d streak")

    stats = calc_stats(repos, commits, streak)
    print(f"  • LV.{stats['level']} | {stats['xp']:,} XP | {stats['xp_pct']}% to next")

    card = build_card(stats)
    patch_readme(card)
