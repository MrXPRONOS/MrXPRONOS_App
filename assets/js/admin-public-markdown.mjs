// Identical sanitizer and Markdown parser used by the public article reader.
// Kept isolated from main.js so rendering an admin preview never starts public
// analytics, event handlers or user-facing football data loads.
import {isSafeCmsUrl} from "./cms-url-guard.mjs";
const escapeHtml = text => {
 const div=document.createElement("div");div.textContent=String(text??"");return div.innerHTML;
};
export function sanitizeHtml(unsafeHtml = "") {
  const template = document.createElement("template");
  template.innerHTML = unsafeHtml;

  const allowedTags = new Set([
    "div",
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
    "video",
    "source",
    "span",
    "hr",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
  ]);

  const allowedAttrs = {
    "*": new Set(["class"]),
    a: new Set(["href", "target", "rel"]),
    img: new Set(["src", "alt", "loading", "decoding"]),
    video: new Set(["src", "controls", "poster", "preload", "playsinline", "width", "height"]),
    source: new Set(["src", "type"]),
    table: new Set(["class"]),
    th: new Set(["class"]),
    td: new Set(["class"]),
  };

  const cleanNode = (node) => {
    [...node.childNodes].forEach((child) => {
      if (child.nodeType === Node.COMMENT_NODE) {
        child.remove();
        return;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) return;

      const tag = child.tagName.toLowerCase();
      if (!allowedTags.has(tag)) {
        const fragment = document.createDocumentFragment();
        while (child.firstChild) fragment.appendChild(child.firstChild);
        child.replaceWith(fragment);
        cleanNode(node);
        return;
      }

      [...child.attributes].forEach((attr) => {
        const name = attr.name.toLowerCase();
        const value = attr.value || "";
        const isAllowed =
          (allowedAttrs[tag] && allowedAttrs[tag].has(name)) ||
          (allowedAttrs["*"] && allowedAttrs["*"].has(name));

        if (name.startsWith("on") || !isAllowed) {
          child.removeAttribute(attr.name);
          return;
        }
        if ((name === "href" || name === "src" || name === "poster") && !isSafeCmsUrl(value, name === "href" ? "link" : "image", window.location.href)) {
          child.removeAttribute(attr.name);
          return;
        }
        if (tag === "a" && name === "href") {
          child.setAttribute("target", "_blank");
          child.setAttribute("rel", "noopener noreferrer");
        }
      });

      cleanNode(child);
    });
  };

  cleanNode(template.content);
  return template.innerHTML;
}

export function renderSafeCmsMarkdown(content=""){
 try{
  if(window.marked?.parse)return sanitizeHtml(window.marked.parse(String(content)));
 }catch{ /* Markdown CDN may be unavailable; the escaped fallback is safe. */ }
 return sanitizeHtml(escapeHtml(String(content)).replace(/\n/g,"<br>"));
}
