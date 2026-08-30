#!/usr/bin/env python3
"""
Rebuild all-channels.m3u by merging:
  - english-countries.m3u  (static, in this repo — the English base list)
  - iptv-org CCTV           (US-CDN, Canada-accessible)
  - fanmingming Chinese     (domain-based only, IPv6 dropped)
  - jn950/live holive       (央视 + 体育 轮播)
  - ottiptv 虎牙 + 斗鱼      (game-streaming 轮播 — live streamers, refreshed each run)

Run: python3 refresh.py
Output: all-channels.m3u (overwritten)

Note: 虎牙/斗鱼 point to live streamers, so they go stale as people go offline.
This script re-pulls the upstream lists each run to keep them current.
"""
import re, os, sys, urllib.request

UA = "okhttp/3.15"
HERE = os.path.dirname(os.path.abspath(__file__))

SOURCES = {
    "english":  {"file": os.path.join(HERE, "english-countries.m3u")},  # local, static
    "cctv":     {"url": "https://iptv-org.github.io/iptv/countries/cn.m3u", "filter": "cctv"},
    "chinese":  {"url": "https://live.fanmingming.com/tv/m3u/ipv6.m3u", "filter": "drop_ipv6"},
    "lunbo":    {"url": "https://raw.githubusercontent.com/jn950/live/main/tv/holive.m3u", "retag": "轮播", "drop_groups": ["MO测试"]},
    "huya":     {"url": "https://sub.ottiptv.cc/huyayqk.m3u", "retag": "虎牙", "drop_groups": ["列表更新时间", "4K频道"]},
    "douyu":    {"url": "https://sub.ottiptv.cc/douyuyqk.m3u", "retag": "斗鱼", "drop_groups": ["列表更新时间", "4K频道"]},
}

EPG = 'https://raw.githubusercontent.com/StrangeDrVN/epg/public/guide.xml.gz,https://live.fanmingming.cn/e.xml'


def fetch(url, tries=3):
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  retry {url}: {e}", file=sys.stderr)
    return ""


def parse(text):
    lines = [l.rstrip("\r\n") for l in text.split("\n")]
    out = []
    i = 1 if lines and lines[0].startswith("#EXTM3U") else 0
    while i < len(lines):
        if lines[i].strip().startswith("#EXTINF"):
            ext = lines[i]; url = None; j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt and not nxt.startswith("#"):
                    url = nxt; break
                j += 1
            if url:
                out.append((ext, url))
            i = j + 1
        else:
            i += 1
    return out


def group_of(ext):
    m = re.search(r'group-title="([^"]*)"', ext)
    return m.group(1) if m else ""


def set_group(ext, grp):
    if "group-title=" in ext:
        return re.sub(r'group-title="[^"]*"', f'group-title="{grp}"', ext)
    return ext.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{grp}"', 1)


def process(name, cfg):
    if "file" in cfg:
        with open(cfg["file"], encoding="utf-8", errors="replace") as f:
            entries = parse(f.read())
    else:
        entries = parse(fetch(cfg["url"]))

    flt = cfg.get("filter")
    if flt == "cctv":
        entries = [(e, u) for e, u in entries if "CCTV" in e and not u.startswith("http://[")]
    elif flt == "drop_ipv6":
        entries = [(e, u) for e, u in entries if not u.startswith("http://[")]

    drop = set(cfg.get("drop_groups", []))
    retag = cfg.get("retag")
    result = []
    for e, u in entries:
        g = group_of(e)
        if g in drop or "testvideo" in u:
            continue
        if flt in ("cctv", "drop_ipv6"):
            e = set_group(e, "央视频道")
        elif retag:
            e = set_group(e, f"{retag}-{g}" if g else retag)
        result.append((e, u))
    print(f"  {name}: {len(result)} channels")
    return result


def main():
    all_entries = []
    for name, cfg in SOURCES.items():
        all_entries.extend(process(name, cfg))

    seen = set(); merged = []; dupes = 0
    for e, u in all_entries:
        if u in seen:
            dupes += 1; continue
        seen.add(u); merged.append((e, u))

    out_path = os.path.join(HERE, "all-channels.m3u")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG}"\n')
        for e, u in merged:
            f.write(e + "\n" + u + "\n")

    print(f"Total: {len(merged)} channels ({dupes} dupes removed) -> {out_path}")


if __name__ == "__main__":
    main()
