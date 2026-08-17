#!/usr/bin/env python3
"""
Living Devotional blog generator.

Reads the post sources in tools/posts/*.json and writes static HTML:

    blog/index.html                 blog hub
    blog/<slug>/index.html          one page per post
    blog/how-i-make-these/index.html
    sitemap.xml, robots.txt, llms.txt
    index.html                      the <!-- BLOG:START/END --> section, in place

Everything it emits is plain static HTML that opens fine over file:// — the
generator is an authoring convenience, not a deploy requirement.

Standard library only. No pip, no npm.

Usage
-----
    python3 tools/build_blog.py
        Rebuild everything. Idempotent: run it twice, git diff stays clean.

    python3 tools/build_blog.py --new <slug> --youtube <id> [--roteiro <path>]
        Scaffold tools/posts/<slug>.json. If a video-factory roteiro is given,
        title / passage / scene narration are pulled in as DRAFT material.
        The draft is a starting point — rewrite it in your own voice before
        publishing. This script never writes prose for you.
"""

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# Site constants — change DOMAIN here and every canonical/OG/sitemap URL follows
# --------------------------------------------------------------------------
DOMAIN = "https://portfolio.agcreationmkt.cloud"
SITE_NAME = "Alex Rodrigues Gomes"
BLOG_NAME = "Living Devotional"
AUTHOR_NAME = "Alex Rodrigues Gomes"
AUTHOR_URL = DOMAIN + "/#alex"
AUTHOR_SAME_AS = [
    "https://www.agcreationmkt.com",
    "https://www.linkedin.com/in/alexrodriguesgomes",
    "https://www.youtube.com/@living-devotional",
]
CHANNEL_URL = "https://www.youtube.com/@living-devotional"
CHANNEL_NAME = "Living Devotional"
BLOG_DESC = (
    "Cinematic Bible stories from the Living Devotional YouTube channel, with a "
    "written companion for every episode by producer Alex Rodrigues Gomes."
)
HOMEPAGE_CARDS = 3          # how many posts show on index.html
WORDS_PER_MINUTE = 220

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR = os.path.join(ROOT, "tools", "posts")
TPL_DIR = os.path.join(ROOT, "tools", "templates")

BLOG_MARK_START = "<!-- BLOG:START -->"
BLOG_MARK_END = "<!-- BLOG:END -->"


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, content):
    """Write only when the content actually changed, so reruns stay quiet."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and read(path) == content:
        print("  unchanged  %s" % os.path.relpath(path, ROOT))
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  wrote      %s" % os.path.relpath(path, ROOT))
    return True


def fill(template, values):
    """Replace {{KEY}} tokens. Plain replacement — no brace escaping needed."""
    out = template
    for key, val in values.items():
        out = out.replace("{{%s}}" % key, str(val))
    leftover = re.findall(r"\{\{([A-Z_]+)\}\}", out)
    if leftover:
        raise SystemExit("Unfilled template tokens: %s" % ", ".join(sorted(set(leftover))))
    return out


def esc(text):
    """Escape for use inside an HTML attribute."""
    return html.escape(str(text), quote=True)


def strip_tags(markup):
    return re.sub(r"<[^>]+>", " ", markup)


def human_date(iso_date):
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%B %-d, %Y")


def iso_to_clock(iso_duration):
    """PT6M38S -> 6:38"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso_duration or "")
    if not m:
        return iso_duration or ""
    hours, mins, secs = (int(g) if g else 0 for g in m.groups())
    if hours:
        return "%d:%02d:%02d" % (hours, mins, secs)
    return "%d:%02d" % (mins, secs)


def post_url(post):
    return "%s/blog/%s/" % (DOMAIN, post["slug"])


def thumb_url(post, quality="maxresdefault"):
    return "https://i.ytimg.com/vi/%s/%s.jpg" % (post["youtube_id"], quality)


def read_minutes(post):
    words = len(strip_tags(" ".join(s["html"] for s in post["sections"])).split())
    words += len(post.get("quick_answer", "").split())
    words += sum(len(f["a"].split()) for f in post.get("faq", []))
    return max(1, round(words / WORDS_PER_MINUTE))


# --------------------------------------------------------------------------
# Shared chrome
# --------------------------------------------------------------------------
FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;'
    '9..144,500;9..144,600&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500'
    '&display=swap" rel="stylesheet">'
)

FAVICON = (
    '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 '
    'viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 rx=%2214%22 '
    'fill=%22%2333463B%22/><text x=%2250%22 y=%2268%22 font-size=%2258%22 '
    'font-family=%22Georgia,serif%22 fill=%22%23EFEAE1%22 text-anchor=%22middle%22>A</text></svg>">'
)


def head(title, description, canonical, og_image, og_type="article", jsonld=None,
         keywords=None, published=None):
    # Google truncates around these lengths; warn rather than fail so a long
    # description never blocks a build.
    if len(description) > 160:
        print("  WARNING    %s: description is %d chars (aim for <=155)"
              % (canonical, len(description)))
    if len(title) > 62:
        print("  WARNING    %s: title is %d chars (aim for <=60)" % (canonical, len(title)))
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>%s</title>" % esc(title),
        '<meta name="description" content="%s">' % esc(description),
        '<link rel="canonical" href="%s">' % esc(canonical),
        '<meta name="author" content="%s">' % esc(AUTHOR_NAME),
        '<meta name="robots" content="index, follow, max-image-preview:large, '
        'max-snippet:-1, max-video-preview:-1">',
    ]
    if keywords:
        parts.append('<meta name="keywords" content="%s">' % esc(", ".join(keywords)))
    parts += [
        '<meta property="og:type" content="%s">' % og_type,
        '<meta property="og:site_name" content="%s">' % esc(SITE_NAME),
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(description),
        '<meta property="og:url" content="%s">' % esc(canonical),
        '<meta property="og:image" content="%s">' % esc(og_image),
        '<meta property="og:image:width" content="1280">',
        '<meta property="og:image:height" content="720">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(description),
        '<meta name="twitter:image" content="%s">' % esc(og_image),
    ]
    if published:
        parts.append('<meta property="article:published_time" content="%s">' % esc(published))
        parts.append('<meta property="article:author" content="%s">' % esc(AUTHOR_NAME))
    parts += [FAVICON, FONTS, '<link rel="stylesheet" href="/blog/assets/blog.css">']
    if jsonld:
        parts.append(
            '<script type="application/ld+json">\n%s\n</script>'
            % json.dumps(jsonld, indent=2, ensure_ascii=False)
        )
    parts += ["</head>", "<body>"]
    return "\n".join(parts)


def nav(current=""):
    def cls(name):
        return ' class="current"' if name == current else ""

    return """
<nav>
  <div class="wrap">
    <a class="nav-name" href="/">Alex Gomes</a>
    <div class="nav-links">
      <a href="/#work" class="hide-sm">Work</a>
      <a href="/#about" class="hide-sm">About</a>
      <a href="/blog/"%s>Devotional</a>
      <a href="/#contact">Contact</a>
    </div>
  </div>
</nav>
""" % cls("blog")


FOOTER = """
<footer>
  <div class="wrap">
    &copy; %s Alex Rodrigues Gomes &mdash; Vista, CA &middot;
    <a href="/">Portfolio</a> &middot;
    <a href="/blog/">Living Devotional</a> &middot;
    <a href="%s" target="_blank" rel="noopener">YouTube</a>
  </div>
</footer>

<script>
/* Video facade: swap the treated thumbnail for the real iframe on click.
   Keeps ~700KB of YouTube player off the initial load. */
document.querySelectorAll('.facade').forEach(function(el){
  el.addEventListener('click', function(){
    var id = el.dataset.yt;
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + id +
            '?autoplay=1&rel=0&modestbranding=1';
    f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; ' +
              'gyroscope; picture-in-picture; web-share';
    f.allowFullscreen = true;
    f.title = el.getAttribute('aria-label') || 'Video player';
    el.innerHTML = '';
    el.appendChild(f);
  }, { once: true });
});
</script>

</body>
</html>
""" % (datetime.now().year, CHANNEL_URL)


# --------------------------------------------------------------------------
# Structured data
# --------------------------------------------------------------------------
def person_node():
    return {
        "@type": "Person",
        "@id": AUTHOR_URL,
        "name": AUTHOR_NAME,
        "url": DOMAIN + "/",
        "jobTitle": "Creative Director & Media Producer",
        "sameAs": AUTHOR_SAME_AS,
    }


def post_jsonld(post):
    """One @graph carrying BlogPosting + VideoObject + FAQPage + BreadcrumbList.

    VideoObject is the highest-value node here: it makes the page eligible for
    Google's video rich result, which points searchers at the channel.
    """
    url = post_url(post)
    graph = [
        person_node(),
        {
            "@type": "BlogPosting",
            "@id": url + "#article",
            "isPartOf": {"@id": DOMAIN + "/blog/#blog"},
            "headline": post["title"],
            "description": post["meta_description"],
            "image": [thumb_url(post)],
            "datePublished": post["published"],
            "dateModified": post.get("modified", post["published"]),
            "author": {"@id": AUTHOR_URL},
            "publisher": {"@id": AUTHOR_URL},
            "mainEntityOfPage": url,
            "inLanguage": "en-US",
            "keywords": ", ".join(post.get("keywords", [])),
            "articleSection": "Bible study",
            "about": [{"@type": "Thing", "name": k} for k in post.get("about", [])],
            "citation": post.get("scripture", []),
            "wordCount": len(strip_tags(" ".join(s["html"] for s in post["sections"])).split()),
        },
        {
            "@type": "VideoObject",
            "@id": url + "#video",
            "name": post.get("video_title", post["title"]),
            "description": post["meta_description"],
            "thumbnailUrl": [thumb_url(post), thumb_url(post, "hqdefault")],
            "uploadDate": post.get("video_upload_date", post["published"]),
            "duration": post["duration_iso"],
            "embedUrl": "https://www.youtube.com/embed/" + post["youtube_id"],
            "contentUrl": "https://www.youtube.com/watch?v=" + post["youtube_id"],
            "creator": {"@id": AUTHOR_URL},
            "publisher": {
                "@type": "Organization",
                "name": CHANNEL_NAME,
                "url": CHANNEL_URL,
            },
            "inLanguage": "en-US",
        },
        {
            "@type": "BreadcrumbList",
            "@id": url + "#breadcrumb",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": DOMAIN + "/blog/"},
                {"@type": "ListItem", "position": 3, "name": post["title"], "item": url},
            ],
        },
    ]
    if post.get("faq"):
        graph.append({
            "@type": "FAQPage",
            "@id": url + "#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": f["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(f["a"]).strip()},
                }
                for f in post["faq"]
            ],
        })
    return {"@context": "https://schema.org", "@graph": graph}


# --------------------------------------------------------------------------
# Block builders
# --------------------------------------------------------------------------
def sections_html(post):
    out = []
    for sec in post["sections"]:
        if sec.get("h2"):
            out.append("  <h2>%s</h2>" % sec["h2"])
        out.append("  " + sec["html"].strip())
    return "\n".join(out)


def scripture_html(post):
    refs = post.get("scripture", [])
    if not refs:
        return ""
    items = "\n".join("      <li><cite>%s</cite></li>" % r for r in refs)
    return (
        '  <div class="scripture">\n'
        '    <span class="eyebrow">Scripture in this episode</span>\n'
        "    <ul>\n%s\n    </ul>\n"
        "  </div>" % items
    )


def faq_html(post):
    faq = post.get("faq", [])
    if not faq:
        return ""
    rows = "\n".join(
        "    <details>\n      <summary>%s</summary>\n      <p>%s</p>\n    </details>"
        % (f["q"], f["a"])
        for f in faq
    )
    return (
        '  <h2 id="faq">%s</h2>\n  <div class="faq">\n%s\n  </div>'
        % (post.get("faq_heading", "Questions people ask"), rows)
    )


def next_teaser_html(post):
    teaser = post.get("next_teaser")
    if not teaser:
        return ""
    return (
        '    <div class="next-up">\n'
        '      <span class="eyebrow">Next episode</span>\n'
        "      <strong>%s</strong> &mdash; %s\n"
        "    </div>" % (teaser["title"], teaser["note"])
    )


def post_nav_html(newer, older):
    if not newer and not older:
        return ""      # a single post has no neighbours — omit the block entirely

    def cell(post, label):
        if not post:
            return '  <span class="empty"></span>'
        return (
            '  <a href="/blog/%s/">\n'
            '    <span class="dir">%s</span>\n'
            "    <h3>%s</h3>\n"
            "  </a>" % (post["slug"], label, post["title"])
        )

    return (
        '<div class="post-nav">\n%s\n%s\n</div>'
        % (cell(older, "Previous episode"), cell(newer, "Next episode"))
    )


def grid_open(count, indent=""):
    """data-count lets the CSS collapse to 1 or 2 columns so a short list never
    leaves empty cells showing the grid's hairline background."""
    return '%s<div class="post-grid" data-count="%d">' % (indent, min(count, 3))


def card_html(post, indent="    "):
    return (
        '{i}<a class="post-card" href="/blog/{slug}/">\n'
        '{i}  <span class="thumb">\n'
        '{i}    <img src="{thumb}" loading="lazy" width="1280" height="720" alt="{alt}"\n'
        "{i}         onerror=\"this.onerror=null;this.src='{fallback}';\">\n"
        "{i}  </span>\n"
        '{i}  <span class="post-body">\n'
        "{i}    <h3>{title}</h3>\n"
        "{i}    <p>{teaser}</p>\n"
        '{i}    <span class="post-meta"><time datetime="{published}">{human}</time>'
        '<span class="tag">{clock}</span></span>\n'
        "{i}  </span>\n"
        "{i}</a>"
    ).format(
        i=indent,
        slug=post["slug"],
        thumb=thumb_url(post),
        fallback=thumb_url(post, "hqdefault"),
        alt=esc(post.get("thumb_alt", post["title"])),
        title=post["title"],
        teaser=post.get("card_teaser", post["meta_description"]),
        published=post["published"],
        human=human_date(post["published"]),
        clock=iso_to_clock(post["duration_iso"]),
    )


# --------------------------------------------------------------------------
# Page renderers
# --------------------------------------------------------------------------
def render_post(post, newer, older):
    tpl = read(os.path.join(TPL_DIR, "post.html"))
    return fill(tpl, {
        "HEAD": head(
            title=post.get("seo_title", post["title"]),
            description=post["meta_description"],
            canonical=post_url(post),
            og_image=thumb_url(post),
            jsonld=post_jsonld(post),
            keywords=post.get("keywords"),
            published=post["published"],
        ),
        "NAV": nav("blog"),
        "FOOTER": FOOTER,
        "TITLE": post["title"],
        "THUMB_ALT": esc(post.get("thumb_alt", post["title"])),
        "SCRIPTURE_REF": post.get("scripture_ref", ""),
        "PUBLISHED": post["published"],
        "PUBLISHED_HUMAN": human_date(post["published"]),
        "READ_MINUTES": read_minutes(post),
        "DURATION_HUMAN": iso_to_clock(post["duration_iso"]),
        "YOUTUBE_ID": post["youtube_id"],
        "QUICK_ANSWER": post["quick_answer"],
        "SECTIONS": sections_html(post),
        "SCRIPTURE_BLOCK": scripture_html(post),
        "FAQ_BLOCK": faq_html(post),
        "SCENE_COUNT": post.get("scene_count", "every"),
        "CHANNEL_URL": CHANNEL_URL,
        "NEXT_TEASER": next_teaser_html(post),
        "POST_NAV": post_nav_html(newer, older),
    })


def render_hub(posts):
    tpl = read(os.path.join(TPL_DIR, "hub.html"))
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            person_node(),
            {
                "@type": "Blog",
                "@id": DOMAIN + "/blog/#blog",
                "name": BLOG_NAME,
                "description": BLOG_DESC,
                "url": DOMAIN + "/blog/",
                "author": {"@id": AUTHOR_URL},
                "inLanguage": "en-US",
                "blogPost": [
                    {
                        "@type": "BlogPosting",
                        "headline": p["title"],
                        "url": post_url(p),
                        "datePublished": p["published"],
                        "image": thumb_url(p),
                    }
                    for p in posts
                ],
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Blog",
                     "item": DOMAIN + "/blog/"},
                ],
            },
        ],
    }
    return fill(tpl, {
        "HEAD": head(
            title="Living Devotional — Cinematic Bible Stories | Alex Gomes",
            description=BLOG_DESC,
            canonical=DOMAIN + "/blog/",
            og_image=thumb_url(posts[0]) if posts else DOMAIN + "/",
            og_type="website",
            jsonld=jsonld,
        ),
        "NAV": nav("blog"),
        "FOOTER": FOOTER,
        "CHANNEL_URL": CHANNEL_URL,
        "GRID_OPEN": grid_open(len(posts), indent="  "),
        "POST_CARDS": "\n".join(card_html(p) for p in posts),
    })


def render_method(posts):
    tpl = read(os.path.join(TPL_DIR, "method.html"))
    url = DOMAIN + "/blog/how-i-make-these/"
    desc = (
        "How the Living Devotional films are made: AI-generated imagery, with the "
        "script, shot design, curation, edit and cost handled entirely by me."
    )
    published = min((p["published"] for p in posts), default="2026-08-17")
    jsonld = {
        "@context": "https://schema.org",
        "@graph": [
            person_node(),
            {
                "@type": "Article",
                "@id": url + "#article",
                "headline": "How I actually make these films",
                "description": desc,
                "author": {"@id": AUTHOR_URL},
                "publisher": {"@id": AUTHOR_URL},
                "datePublished": published,
                "dateModified": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "mainEntityOfPage": url,
                "inLanguage": "en-US",
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": DOMAIN + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Blog",
                     "item": DOMAIN + "/blog/"},
                    {"@type": "ListItem", "position": 3, "name": "How I make these",
                     "item": url},
                ],
            },
        ],
    }
    return fill(tpl, {
        "HEAD": head(
            title="How I Make These Films — AI Imagery, Human Direction",
            description=desc,
            canonical=url,
            og_image=thumb_url(posts[0]) if posts else DOMAIN + "/",
            jsonld=jsonld,
            published=published,
        ),
        "NAV": nav("blog"),
        "FOOTER": FOOTER,
        "PUBLISHED": published,
        "PUBLISHED_HUMAN": human_date(published),
    })


# --------------------------------------------------------------------------
# Site-level files
# --------------------------------------------------------------------------
def render_sitemap(posts):
    def entry(loc, lastmod, priority, extra=""):
        return (
            "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
            "    <priority>%s</priority>\n%s  </url>"
            % (loc, lastmod, priority, extra)
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    newest = posts[0]["published"] if posts else today
    rows = [
        entry(DOMAIN + "/", today, "1.0"),
        entry(DOMAIN + "/blog/", newest, "0.9"),
        entry(DOMAIN + "/blog/how-i-make-these/", today, "0.6"),
    ]
    for p in posts:
        video = (
            "    <video:video>\n"
            "      <video:thumbnail_loc>%s</video:thumbnail_loc>\n"
            "      <video:title>%s</video:title>\n"
            "      <video:description>%s</video:description>\n"
            "      <video:player_loc>https://www.youtube.com/embed/%s</video:player_loc>\n"
            "      <video:publication_date>%s</video:publication_date>\n"
            "    </video:video>\n"
            % (
                thumb_url(p),
                html.escape(p.get("video_title", p["title"])),
                html.escape(p["meta_description"]),
                p["youtube_id"],
                p["published"],
            )
        )
        rows.append(entry(post_url(p), p.get("modified", p["published"]), "0.8", video))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">\n'
        "%s\n</urlset>\n" % "\n".join(rows)
    )


def render_robots():
    return """# %s

User-agent: *
Allow: /

# AI answer engines are explicitly welcome — the goal is to be cited.
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-Web
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /
User-agent: CCBot
Allow: /

Sitemap: %s/sitemap.xml
""" % (DOMAIN, DOMAIN)


def render_llms(posts):
    """llms.txt — the emerging convention for describing a site to LLM crawlers."""
    lines = [
        "# %s" % SITE_NAME,
        "",
        "> Creative director and media producer in Vista, California. Ten years of "
        "branding, photography, video production and UX, plus a B.A. in Theology "
        "(Rochester University, 2026). Makes cinematic Bible-story short films for "
        "the YouTube channel Living Devotional.",
        "",
        "## About",
        "",
        "- [Portfolio](%s/): work, background and contact for Alex Rodrigues Gomes." % DOMAIN,
        "- [How the films are made](%s/blog/how-i-make-these/): full disclosure of the "
        "AI-assisted production pipeline — imagery is AI-generated; script, shot design, "
        "character continuity, curation, edit and cost are entirely human." % DOMAIN,
        "",
        "## Living Devotional blog",
        "",
        "Written companions to the [Living Devotional](%s) YouTube channel. Each post "
        "retells one Bible narrative in full and applies it to a specific modern "
        "experience." % CHANNEL_URL,
        "",
    ]
    for p in posts:
        lines.append(
            "- [%s](%s): %s" % (p["title"], post_url(p), p.get("llms_summary", p["meta_description"]))
        )
    lines.append("")
    return "\n".join(lines)


def homepage_section(posts):
    cards = "\n".join(card_html(p, indent="      ") for p in posts[:HOMEPAGE_CARDS])
    return """%s
<section id="devotional">
  <div class="wrap">
    <div class="section-head">
      <span class="eyebrow">Living Devotional &middot; YouTube</span>
      <h2>Cinematic Bible stories, made weekly.</h2>
      <p style="max-width:58ch; opacity:0.82; margin-top:14px;">A personal project where I
      direct short films out of the parts of Scripture people actually live inside &mdash;
      waiting, being forgotten, doing the right thing and losing anyway. Every episode gets a
      written companion, and I document exactly how each one is made.</p>
      <div style="display:flex; gap:12px; margin-top:22px; flex-wrap:wrap;">
        <a class="btn" href="/blog/">Read the episodes</a>
        <a class="btn btn-outline" href="%s" target="_blank" rel="noopener">Watch on YouTube</a>
      </div>
    </div>
  </div>
%s
%s
  </div>
</section>
%s""" % (BLOG_MARK_START, CHANNEL_URL,
         grid_open(min(len(posts), HOMEPAGE_CARDS), indent="  "), cards, BLOG_MARK_END)


def update_index(posts):
    """Rewrite the marker-delimited devotional section inside index.html."""
    path = os.path.join(ROOT, "index.html")
    source = read(path)
    if BLOG_MARK_START not in source or BLOG_MARK_END not in source:
        print("  SKIPPED    index.html — %s / %s markers not found"
              % (BLOG_MARK_START, BLOG_MARK_END))
        return False
    start = source.index(BLOG_MARK_START)
    end = source.index(BLOG_MARK_END) + len(BLOG_MARK_END)
    return write(path, source[:start] + homepage_section(posts) + source[end:])


# --------------------------------------------------------------------------
# Loading & validation
# --------------------------------------------------------------------------
REQUIRED = ["slug", "youtube_id", "title", "meta_description", "published",
            "duration_iso", "quick_answer", "sections"]


def load_posts():
    if not os.path.isdir(POSTS_DIR):
        return []
    posts = []
    for name in sorted(os.listdir(POSTS_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(POSTS_DIR, name)
        with open(path, encoding="utf-8") as fh:
            post = json.load(fh)
        if post.get("draft"):
            print("  skipping draft: %s" % name)
            continue
        missing = [k for k in REQUIRED if not post.get(k)]
        if missing:
            raise SystemExit("%s is missing required field(s): %s" % (name, ", ".join(missing)))
        if len(post["meta_description"]) > 160:
            print("  WARNING    %s: meta_description is %d chars (aim for <=155)"
                  % (name, len(post["meta_description"])))
        posts.append(post)
    # newest first
    posts.sort(key=lambda p: p["published"], reverse=True)
    return posts


# --------------------------------------------------------------------------
# Scaffolding
# --------------------------------------------------------------------------
def scaffold(slug, youtube_id, roteiro_path):
    os.makedirs(POSTS_DIR, exist_ok=True)
    dest = os.path.join(POSTS_DIR, "%s.json" % slug)
    if os.path.exists(dest):
        raise SystemExit("%s already exists — refusing to overwrite." % dest)

    draft = {
        "draft": True,
        "_note": "Rewrite every DRAFT field in Alex's first-person voice, then remove "
                 "\"draft\": true to publish.",
        "slug": slug,
        "youtube_id": youtube_id,
        "title": "DRAFT — title",
        "seo_title": "DRAFT — <=60 chars including | Alex Gomes",
        "meta_description": "DRAFT — <=155 chars",
        "card_teaser": "DRAFT — one sentence for the grid card",
        "llms_summary": "DRAFT — one line for llms.txt",
        "thumb_alt": "DRAFT — describe the thumbnail image",
        "published": datetime.now().strftime("%Y-%m-%d"),
        "duration_iso": "PT0M0S",
        "scripture_ref": "",
        "scene_count": "",
        "keywords": [],
        "about": [],
        "quick_answer": "DRAFT — ~60 words answering the title question directly.",
        "sections": [],
        "scripture": [],
        "faq_heading": "Questions people ask",
        "faq": [],
        "next_teaser": {"title": "DRAFT", "note": "DRAFT"},
    }

    if roteiro_path:
        with open(roteiro_path, encoding="utf-8") as fh:
            roteiro = json.load(fh)
        draft["title"] = "DRAFT — " + roteiro.get("titulo_en", "")
        draft["scripture_ref"] = roteiro.get("passagem", "")
        draft["scene_count"] = str(len(roteiro.get("cenas", [])))
        draft["about"] = list(roteiro.get("personagens", {}).keys())
        # Group scene narration by narrative block: one draft section per block.
        blocks = []
        for cena in roteiro.get("cenas", []):
            block = cena.get("bloco", "misc")
            if not blocks or blocks[-1][0] != block:
                blocks.append((block, []))
            blocks[-1][1].append(cena.get("en", "").strip())
        for block, lines in blocks:
            draft["sections"].append({
                "h2": "DRAFT — question-shaped H2 for '%s'" % block,
                "html": "\n".join("<p>%s</p>" % ln for ln in lines if ln),
            })
        print("  pulled %d scenes in %d narrative blocks from %s"
              % (len(roteiro.get("cenas", [])), len(blocks), os.path.basename(roteiro_path)))

    write(dest, json.dumps(draft, indent=2, ensure_ascii=False) + "\n")
    print("\nNext: rewrite the DRAFT fields in your own voice, drop \"draft\": true,")
    print("then run  python3 tools/build_blog.py")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def build():
    posts = load_posts()
    if not posts:
        raise SystemExit("No publishable posts found in %s" % POSTS_DIR)

    print("Building %d post(s)…" % len(posts))
    for i, post in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None          # list is newest-first
        older = posts[i + 1] if i + 1 < len(posts) else None
        write(os.path.join(ROOT, "blog", post["slug"], "index.html"),
              render_post(post, newer, older))

    write(os.path.join(ROOT, "blog", "index.html"), render_hub(posts))
    write(os.path.join(ROOT, "blog", "how-i-make-these", "index.html"), render_method(posts))
    write(os.path.join(ROOT, "sitemap.xml"), render_sitemap(posts))
    write(os.path.join(ROOT, "robots.txt"), render_robots())
    write(os.path.join(ROOT, "llms.txt"), render_llms(posts))
    update_index(posts)
    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Living Devotional blog generator")
    parser.add_argument("--new", metavar="SLUG", help="scaffold a new post JSON")
    parser.add_argument("--youtube", metavar="ID", help="YouTube video id for --new")
    parser.add_argument("--roteiro", metavar="PATH", help="video-factory roteiro to draft from")
    args = parser.parse_args()

    if args.new:
        if not args.youtube:
            parser.error("--new requires --youtube <id>")
        scaffold(args.new, args.youtube, args.roteiro)
        return
    build()


if __name__ == "__main__":
    sys.exit(main())
