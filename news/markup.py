import markdown
import nh3
from django.utils.safestring import mark_safe

ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "strong", "em", "del", "code", "pre", "blockquote",
    "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
}
# Relative URLs are allowed so a post can use a file shipped under /static/.
ALLOWED_SCHEMES = {"http", "https", "mailto"}


def render_markdown(text):
    """Turn an author's Markdown into safe HTML.

    Authors are trusted staff, but the output still goes through an allow-list so a pasted
    script tag, event handler, or javascript: link can never reach visitors.
    """
    html = markdown.markdown(
        text or "",
        extensions=["extra", "sane_lists", "nl2br", "toc"],
        # A post's own title is the page's h1, so "# Heading" becomes an h2.
        extension_configs={"toc": {"baselevel": 2}},
    )
    clean = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_SCHEMES,
        link_rel="noopener noreferrer",
        set_tag_attribute_values={"img": {"loading": "lazy", "decoding": "async"}},
    )
    return mark_safe(clean)
