#!/usr/bin/env python3
"""The project blog: dated milestone posts on the website (web/blog/). The user reads it as the main view
of progress, so every medium-or-larger milestone gets a post: what was reached, the numbers before and
after, the mechanism found, and links to the gallery GIFs.

  python3 tools/blog.py new "<title>" < post.md      writes web/blog/posts/<date>-<slug>.md (markdown, a
                                                    subset: #/## headings, paragraphs, - lists, **bold**,
                                                    `code`, [text](url), ![alt](src)) and rebuilds
  python3 tools/blog.py build                        rebuilds web/blog/index.html from the posts, newest first
bash tools/publish_site.sh then puts it on the site (web/ is rsynced to gh-pages).
"""
import datetime, html, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
POSTS = os.path.join(ROOT, "web", "blog", "posts")
INDEX = os.path.join(ROOT, "web", "blog", "index.html")


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render(md):
    out, para, lst = [], [], False
    def flush():
        nonlocal para
        if para: out.append("<p>%s</p>" % inline(" ".join(para))); para = []
    for line in md.splitlines():
        if line.startswith("- "):
            flush()
            if not lst: out.append("<ul>"); lst = True
            out.append("<li>%s</li>" % inline(line[2:].strip())); continue
        if lst and not line.startswith("- "): out.append("</ul>"); lst = False
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m: flush(); out.append("<h%d>%s</h%d>" % (len(m.group(1)) + 1, inline(m.group(2)), len(m.group(1)) + 1)); continue
        if not line.strip(): flush(); continue
        para.append(line.strip())
    flush()
    if lst: out.append("</ul>")
    return "\n".join(out)


def build():
    posts = []
    for f in sorted(os.listdir(POSTS), reverse=True):
        if not f.endswith(".md"): continue
        text = open(os.path.join(POSTS, f)).read()
        title = text.split("\n", 1)[0].lstrip("# ").strip()
        body = text.split("\n", 1)[1] if "\n" in text else ""
        date = f[:10]
        posts.append((date, title, f[:-3], render(body)))
    items = "\n".join('<article id="%s"><h2>%s</h2><div class="date">%s</div>%s</article>' % (slug, html.escape(title), date, body)
                      for date, title, slug, body in posts)
    toc = "\n".join('<li><a href="#%s">%s</a> <span class="date">%s</span></li>' % (slug, html.escape(title), date) for date, title, slug, _ in posts)
    page = """<!doctype html><html><head><meta charset="utf-8"><title>BN6 in Rust: project blog</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font:16px/1.55 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#222;background:#fafafa}
h1{font-size:1.6rem}article{border-top:1px solid #ddd;padding:1.2rem 0}article h2{font-size:1.25rem;margin:.2rem 0}.date{color:#777;font-size:.9rem}
code{background:#eee;padding:0 .25em;border-radius:3px}img{max-width:100%%}a{color:#0a58a8}nav a{margin-right:1rem}ul{padding-left:1.2rem}</style></head><body>
<nav><a href="../index.html">site</a><a href="../gifs.html">gallery</a><a href="../log.html">log</a><a href="https://github.com/alex-berliner/bn6-rust">repo</a></nav>
<h1>Project blog: rebuilding Battle Network 6's battle system to the pixel</h1>
<p>Milestones, medium and up: what was reached, the numbers before and after, the mechanism found, and the gallery GIFs that show it. Newest first.</p>
<ul class="toc">%s</ul>
%s
</body></html>""" % (toc, items)
    open(INDEX, "w").write(page)
    print("built %s (%d posts)" % (os.path.relpath(INDEX, ROOT), len(posts)))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build(); return
    if len(sys.argv) >= 3 and sys.argv[1] == "new":
        title = sys.argv[2]; date = datetime.date.today().isoformat()
        for i, a in enumerate(sys.argv):
            if a == "--date": date = sys.argv[i + 1]
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
        path = os.path.join(POSTS, "%s-%s.md" % (date, slug))
        body = sys.stdin.read()
        open(path, "w").write("# %s\n\n%s" % (title, body.strip() + "\n"))
        print("wrote", os.path.relpath(path, ROOT)); build(); return
    print(__doc__)


if __name__ == "__main__":
    main()
