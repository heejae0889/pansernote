/* Keep LaTeX out of the Markdown parser, then render it into sanitized DOM. */
(function () {
  'use strict';

  function renderSummary(target, rawText) {
    const status = document.getElementById('summary-render-status');
    function notice(message) {
      if (status) { status.textContent = message; status.hidden = false; }
    }
    if (!window.marked || !window.DOMPurify || !window.katex) {
      notice('서식 파일을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침해 주세요.');
      return;
    }

    // Some responses wrap the entire answer in a Markdown/HTML code fence.
    const wrapper = rawText.trim().match(/^```(?:markdown|md|html)\s*\n([\s\S]*?)\n```$/i);
    if (wrapper) rawText = wrapper[1];

    const formulas = [];
    const prefix = 'PNMATH' + Math.random().toString(36).slice(2) + 'TOKEN';
    // Code is consumed first so formulas inside code examples stay untouched.
    const protectedText = rawText.replace(
      /(```[\s\S]*?```|`+[^`\n]*`+)|\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|(?<![\\$])\$(?!\$)((?:\\.|[^$\n\\])+)\$(?!\$)/g,
      (match, code, dollarBlock, bracketBlock, inlineBracket, inlineDollar) => {
        if (code) return code;
        const displayMode = dollarBlock !== undefined || bracketBlock !== undefined;
        const tex = dollarBlock ?? bracketBlock ?? inlineBracket ?? inlineDollar;
        const token = prefix + formulas.length + 'END';
        formulas.push({ token, tex, displayMode });
        return displayMode ? '\n\n' + token + '\n\n' : token;
      }
    );
    target.innerHTML = DOMPurify.sanitize(marked.parse(protectedText, { gfm: true }), {
      ALLOWED_TAGS: ['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 's', 'del', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'a'],
      ALLOWED_ATTR: ['href', 'title', 'start', 'colspan', 'rowspan']
    });

    const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      if (!walker.currentNode.parentElement.closest('pre, code')) nodes.push(walker.currentNode);
    }
    const tokenPattern = new RegExp(prefix + '(\\d+)END', 'g');
    let failed = false;
    nodes.forEach(node => {
      const text = node.textContent;
      tokenPattern.lastIndex = 0;
      if (!tokenPattern.test(text)) return;
      tokenPattern.lastIndex = 0;
      const fragment = document.createDocumentFragment();
      let last = 0;
      for (const match of text.matchAll(tokenPattern)) {
        fragment.append(document.createTextNode(text.slice(last, match.index)));
        const formula = formulas[Number(match[1])];
        const element = document.createElement('span');
        element.className = formula.displayMode ? 'summary-math-block' : 'summary-math-inline';
        try {
          katex.render(formula.tex.trim(), element, {
            displayMode: formula.displayMode, throwOnError: true,
            trust: false, strict: 'ignore', maxExpand: 1000
          });
        } catch (error) {
          // Preserve unsupported expressions as text instead of losing content.
          element.className = 'summary-math-fallback';
          element.textContent = formula.tex;
          failed = true;
        }
        fragment.append(element);
        last = match.index + match[0].length;
      }
      fragment.append(document.createTextNode(text.slice(last)));
      node.replaceWith(fragment);
    });
    if (failed) notice('일부 수식은 형식을 해석하지 못해 원문으로 표시했습니다.');
    target.classList.add('is-rendered');
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.markdown-math').forEach(target => {
      const source = document.getElementById(target.dataset.source);
      if (!source) return;
      try { renderSummary(target, source.value || source.textContent); }
      catch (error) {
        target.textContent = source.value || source.textContent;
        const status = document.getElementById('summary-render-status');
        if (status) { status.textContent = '서식을 표시하지 못해 원문으로 표시했습니다.'; status.hidden = false; }
      }
    });
  });
})();
