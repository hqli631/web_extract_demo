// 在外观正常的原网页浏览器控制台运行；下载后改成原样本文件名。
(() => {
  const omitted = new Set(['SCRIPT', 'NOSCRIPT', 'BASE']);
  let count = 0;
  function copy(node) {
    if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.textContent);
    if (node.nodeType !== Node.ELEMENT_NODE || omitted.has(node.tagName)) return null;
    if (node.tagName === 'META' && /content-security-policy|refresh/i.test(node.httpEquiv)) return null;
    const el = node.cloneNode(false);
    for (const attr of [...el.attributes]) if (/^on/i.test(attr.name)) el.removeAttribute(attr.name);
    if (node instanceof HTMLImageElement && node.currentSrc) {
      el.src = node.currentSrc; el.removeAttribute('srcset'); el.loading = 'eager';
    }
    // Capture the actual rendered styles, including adoptedStyleSheets in Shadow DOM.
    // Geometry remains responsive to the review iframe; pseudo elements are not serialized.
    const css = getComputedStyle(node);
    for (const key of css) el.style.setProperty(key, css.getPropertyValue(key), 'important');
    count++;
    if (node.shadowRoot) {
      const template = document.createElement('template');
      template.setAttribute('shadowrootmode', 'open');
      for (const child of node.shadowRoot.childNodes) {
        const c = copy(child); if (c) template.content.append(c);
      }
      el.append(template);
    }
    if (node.tagName === 'TEMPLATE') return el;
    for (const child of node.childNodes) { const c = copy(child); if (c) el.append(c); }
    return el;
  }
  const html = copy(document.documentElement);
  const base = document.createElement('base'); base.href = location.href;
  html.querySelector('head')?.prepend(base);
  const url = URL.createObjectURL(new Blob(['<!doctype html>\n' + html.outerHTML], {type:'text/html;charset=utf-8'}));
  const a = document.createElement('a'); a.href = url; a.download = 'captured_page.html'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  console.log('已保存 ' + count + ' 个元素及其当前样式。图片仍可能需要联网；伪元素、canvas、跨域 iframe 不保证完整。');
})();
