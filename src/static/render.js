// Gemini 결과(마크다운 + 수식) 렌더링
// 마크다운을 먼저 바꾸면 수식 안의 \ _ * 가 깨져서 수식은 따로 빼뒀다가 다시 넣음

function escapeHtml(str) {
  return str.replace(/</g, '&lt;');
}

// 답변에 들어있는 html 태그는 그냥 글자로 보이게
marked.use({
  renderer: {
    html: function (token) {
      const raw = (typeof token === 'string') ? token : (token && (token.raw || token.text)) || '';
      return escapeHtml(raw);
    }
  }
});

// KaTeX가 & % # 때문에 에러나는 거 방지 (aligned 안의 &는 줄맞춤용이라 그대로 둠)
function sanitizeMath(mathStr) {
  if (!/\\begin\{/.test(mathStr)) {
    mathStr = mathStr.replace(/(?<!\\)&/g, '\\&');
  }
  return mathStr
    .replace(/(?<!\\)%/g, '\\%')
    .replace(/(?<!\\)#/g, '\\#');
}

function renderMarkdownMath(rawText) {
  const mathBlocks = [];
  const keep = function (match) {
    mathBlocks.push(escapeHtml(sanitizeMath(match)));
    return 'MATHBLOCK' + (mathBlocks.length - 1) + 'ENDMATH';
  };
  rawText = rawText.replace(/\$\$([\s\S]*?)\$\$/g, keep);
  rawText = rawText.replace(/\$([^$\n]+?)\$/g, keep);

  // **권한(Permission)**에 처럼 괄호 뒤에 조사가 붙으면 굵게가 안 먹혀서 따로 처리
  const boldBlocks = [];
  rawText = rawText.replace(/\*\*([^\n*]*[\p{P}\p{S}])\*\*(?=[^\s\p{P}\p{S}])/gu, function (match, inner) {
    boldBlocks.push(escapeHtml(inner));
    return 'BOLDMARK' + (boldBlocks.length - 1) + 'ENDBOLD';
  });

  let html = marked.parse(rawText);
  html = html.replace(/BOLDMARK(\d+)ENDBOLD/g, function (match, i) {
    return '<strong>' + boldBlocks[i] + '</strong>';
  });
  html = html.replace(/MATHBLOCK(\d+)ENDMATH/g, function (match, i) {
    return mathBlocks[i];
  });
  return html;
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.markdown-math').forEach(function (target) {
    const source = document.getElementById(target.dataset.source);
    if (!source) return;
    target.innerHTML = renderMarkdownMath(source.value || source.textContent);
    renderMathInElement(target, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false }
      ],
      throwOnError: false
    });
  });
});
