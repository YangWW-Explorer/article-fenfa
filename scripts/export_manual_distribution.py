#!/usr/bin/env python3
"""Export an Obsidian Markdown article to MDNice Markdown and X rich HTML."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|$)", re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
OBSIDIAN_IMAGE_RE = re.compile(r"!\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
MARKDOWN_IMAGE_RE = re.compile(
    r"!\[([^\]]*)\]\(\s*([^\s)]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
PLACEHOLDER_RE = re.compile(
    r"(?:\[截图位[^\]]*\]|【(?:配图|截图)[^】]*(?:待补|占位)[^】]*】)"
)
HORIZONTAL_RULE_RE = re.compile(r"^\s*(?:---|\*\*\*|___)\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export one project Markdown article to MDNice Markdown and X HTML."
    )
    parser.add_argument("input", type=Path, help="Source Markdown file")
    parser.add_argument("--topic", help="Output topic; inferred from input name by default")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the unversioned output pair",
    )
    return parser.parse_args()


def infer_topic(path: Path) -> str:
    topic = path.stem
    topic = re.sub(r"^\d+_", "", topic)
    topic = re.sub(
        r"^(?:母板|母版|公众号(?:mdnice)?|长文|XArticle|X推文)[_-]*",
        "",
        topic,
        flags=re.IGNORECASE,
    )
    topic = topic.strip("_- ")
    return topic or path.stem


def sanitize_topic(topic: str) -> str:
    topic = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", topic)
    topic = topic.strip(" ._-")
    if not topic:
        raise ValueError("topic is empty after filename sanitization")
    return topic


def clean_source(source: str) -> str:
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    source = FRONTMATTER_RE.sub("", source)
    source = COMMENT_RE.sub("", source)
    lines = [line for line in source.splitlines() if not HORIZONTAL_RULE_RE.match(line)]
    source = "\n".join(lines)
    source = re.sub(r"\n{3,}", "\n\n", source).strip()
    return source + "\n"


def validate_images(source: str) -> tuple[list[tuple[str, str]], list[str]]:
    remote_images: list[tuple[str, str]] = []
    errors: list[str] = []

    for match in OBSIDIAN_IMAGE_RE.finditer(source):
        errors.append(match.group(0))

    for match in MARKDOWN_IMAGE_RE.finditer(source):
        alt, url = match.group(1).strip(), match.group(2).strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(match.group(0))
        else:
            remote_images.append((alt, url))

    return remote_images, errors


def reserve_outputs(
    output_dir: Path, topic: str, overwrite: bool
) -> tuple[Path, Path]:
    md_base = output_dir / f"36_公众号mdnice_{topic}.md"
    html_base = output_dir / f"37_XArticle_{topic}_富文本粘贴版.html"
    if overwrite or (not md_base.exists() and not html_base.exists()):
        return md_base, html_base

    version = 2
    while True:
        md_path = md_base.with_name(f"{md_base.stem}_v{version}{md_base.suffix}")
        html_path = html_base.with_name(
            f"{html_base.stem}_v{version}{html_base.suffix}"
        )
        if not md_path.exists() and not html_path.exists():
            return md_path, html_path
        version += 1


def render_inline(text: str) -> str:
    tokens: dict[str, str] = {}

    def stash(value: str) -> str:
        key = f"@@FENFA_TOKEN_{len(tokens)}@@"
        tokens[key] = value
        return key

    def image_repl(match: re.Match[str]) -> str:
        alt = html.escape(match.group(1).strip(), quote=True)
        url = html.escape(match.group(2).strip(), quote=True)
        return stash(f'<img src="{url}" alt="{alt}" loading="lazy">')

    def link_repl(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        url = html.escape(match.group(2), quote=True)
        return stash(f'<a href="{url}">{label}</a>')

    def code_repl(match: re.Match[str]) -> str:
        return stash(f"<code>{html.escape(match.group(1))}</code>")

    text = MARKDOWN_IMAGE_RE.sub(image_repl, text)
    text = re.sub(r"`([^`]+)`", code_repl, text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", link_repl, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    for key, value in tokens.items():
        text = text.replace(key, value)
    return text


def markdown_to_html(source: str) -> tuple[str, str]:
    lines = source.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_type: str | None = None
    in_code = False
    code_lines: list[str] = []
    title = ""

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_type
        if list_items and list_type:
            items = "".join(f"<li>{render_inline(item)}</li>" for item in list_items)
            blocks.append(f"<{list_type}>{items}</{list_type}>")
            list_items.clear()
            list_type = None

    for line in lines:
        if line.startswith("```"):
            flush_paragraph()
            flush_list()
            if in_code:
                blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines.clear()
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            flush_paragraph()
            flush_list()
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            heading_text = heading.group(2).strip()
            if level == 1 and not title:
                title = re.sub(r"[*_`]", "", heading_text)
            blocks.append(f"<h{level}>{render_inline(heading_text)}</h{level}>")
            continue

        unordered = re.match(r"^\s*[-+]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            current_type = "ul" if unordered else "ol"
            if list_type and list_type != current_type:
                flush_list()
            list_type = current_type
            list_items.append((unordered or ordered).group(1))
            continue

        quote = re.match(r"^>\s?(.*)$", line)
        if quote:
            flush_paragraph()
            flush_list()
            blocks.append(f"<blockquote>{render_inline(quote.group(1))}</blockquote>")
            continue

        image_only = MARKDOWN_IMAGE_RE.fullmatch(line.strip())
        if image_only:
            flush_paragraph()
            flush_list()
            alt = html.escape(image_only.group(1).strip(), quote=True)
            url = html.escape(image_only.group(2).strip(), quote=True)
            caption = f"<figcaption>{alt}</figcaption>" if alt else ""
            blocks.append(
                f'<figure><img src="{url}" alt="{alt}" loading="lazy">{caption}</figure>'
            )
            continue

        paragraph.append(line.strip())

    flush_paragraph()
    flush_list()
    if in_code:
        blocks.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return title, "\n".join(blocks)


def build_html(title: str, article_html: str) -> str:
    page_title = html.escape(title or "X Article", quote=True)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{page_title}</title>
  <style>
    body {{ margin: 0; background: #f4f6f8; color: #111; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .toolbar {{ position: sticky; top: 0; z-index: 2; display: flex; gap: 12px; align-items: center; padding: 12px 20px; background: #fff; border-bottom: 1px solid #ddd; }}
    button {{ padding: 9px 16px; border: 0; border-radius: 999px; background: #0f1419; color: #fff; cursor: pointer; }}
    #status {{ color: #536471; font-size: 14px; }}
    article {{ max-width: 720px; margin: 32px auto; padding: 40px; background: #fff; }}
    h1 {{ font-size: 36px; line-height: 1.25; }}
    h2 {{ margin-top: 36px; font-size: 26px; }}
    h3 {{ margin-top: 28px; font-size: 21px; }}
    p, li, blockquote {{ font-size: 18px; line-height: 1.75; }}
    img {{ display: block; max-width: 100%; height: auto; margin: 24px auto 8px; }}
    figure {{ margin: 28px 0; }}
    figcaption {{ color: #536471; text-align: center; font-size: 14px; }}
    blockquote {{ margin-left: 0; padding-left: 18px; border-left: 4px solid #cfd9de; color: #536471; }}
    pre {{ overflow: auto; padding: 16px; background: #f7f9f9; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <button type="button" onclick="copyArticle()">复制富文本</button>
    <span id="status">复制后粘贴到 X Articles 草稿编辑器；远程图片能否导入取决于平台。</span>
  </div>
  <article id="article">
{article_html}
  </article>
  <script>
    async function copyArticle() {{
      const article = document.getElementById("article");
      const rich = article.innerHTML;
      const plain = article.innerText;
      const status = document.getElementById("status");
      try {{
        await navigator.clipboard.write([
          new ClipboardItem({{
            "text/html": new Blob([rich], {{ type: "text/html" }}),
            "text/plain": new Blob([plain], {{ type: "text/plain" }})
          }})
        ]);
        status.textContent = "已复制富文本。";
      }} catch (error) {{
        const range = document.createRange();
        range.selectNodeContents(article);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand("copy");
        selection.removeAllRanges();
        status.textContent = "已使用兼容模式复制。";
      }}
    }}
  </script>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2
    if "10_项目" not in input_path.parts:
        print("ERROR: input must be inside 10_项目/<日期_主题>/", file=sys.stderr)
        return 2

    source = clean_source(input_path.read_text(encoding="utf-8"))
    placeholders = sorted(set(PLACEHOLDER_RE.findall(source)))
    images, image_errors = validate_images(source)
    if placeholders or image_errors:
        print("ERROR: source is not ready for direct publishing.", file=sys.stderr)
        for item in placeholders:
            print(f"  placeholder: {item}", file=sys.stderr)
        for item in image_errors:
            print(f"  invalid image: {item}", file=sys.stderr)
        print("Upload local images to an HTTPS image host and update the source first.", file=sys.stderr)
        return 2

    try:
        topic = sanitize_topic((args.topic or infer_topic(input_path)).strip())
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    output_dir = input_path.parent
    md_path, html_path = reserve_outputs(output_dir, topic, args.overwrite)

    title, article_html = markdown_to_html(source)
    md_path.write_text(source, encoding="utf-8")
    html_path.write_text(build_html(title, article_html), encoding="utf-8")

    print(f"MDNice: {md_path}")
    print(f"X Article: {html_path}")
    print(f"HTTPS images: {len(images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
