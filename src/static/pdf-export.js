/* 처리 결과(원본·보정 사진 + Gemini 요약)를 한 개의 PDF로 저장한다.
   화면에 이미 그려진 결과(마크다운/수식 렌더링 포함)를 그대로 사용하므로 서버 작업이 필요 없다. */
(() => {
  'use strict';

  const PDF_CSS = `
    .pdf-doc { font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; color: #202c43; font-size: 13px; line-height: 1.7; background: #fff; }
    .pdf-doc h1 { font-size: 22px; margin: 0 0 4px; color: #1f3a66; }
    .pdf-doc .pdf-meta { font-size: 11px; color: #606d83; margin: 0 0 18px; padding-bottom: 10px; border-bottom: 2px solid #365b91; }
    .pdf-doc h2 { font-size: 16px; margin: 4px 0 10px; padding-left: 9px; border-left: 4px solid #365b91; color: #1f3a66; }
    .pdf-doc h3 { font-size: 14px; margin: 14px 0 6px; }
    .pdf-doc .pdf-photos { display: flex; gap: 12px; align-items: flex-start; }
    .pdf-doc .pdf-photo { flex: 1 1 0; min-width: 0; margin: 0; text-align: center; }
    .pdf-doc .pdf-photo figcaption { font-size: 12px; font-weight: 700; color: #1f3a66; margin: 0 0 6px; }
    .pdf-doc .pdf-photo img { max-width: 100%; max-height: 560px; border: 1px solid #d5deea; }
    .pdf-doc .pdf-ocr { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; padding: 12px 14px; background: #f5f7fb; border: 1px solid #d5deea; border-radius: 6px; font-family: inherit; font-size: 12.5px; line-height: 1.8; }
    .pdf-doc .pdf-line { white-space: pre-wrap; overflow-wrap: anywhere; }
    .pdf-doc .pdf-note { font-size: 11px; color: #606d83; margin: 0 0 6px; }
    .pdf-doc .pdf-error { color: #a63827; }
    .pdf-doc .pdf-summary { overflow-wrap: anywhere; }
    .pdf-doc .pdf-summary h1, .pdf-doc .pdf-summary h2, .pdf-doc .pdf-summary h3, .pdf-doc .pdf-summary h4 { font-size: 14px; margin: 14px 0 6px; padding: 0; border: 0; color: #202c43; }
    .pdf-doc .pdf-summary ul, .pdf-doc .pdf-summary ol { padding-left: 22px; margin: 6px 0; }
    .pdf-doc .pdf-summary p { margin: 6px 0; }
    .pdf-doc .pdf-summary table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12px; }
    .pdf-doc .pdf-summary th, .pdf-doc .pdf-summary td { border: 1px solid #c9d4e3; padding: 5px 8px; text-align: left; }
    .pdf-doc .pdf-summary th { background: #eef2f8; }
    .pdf-doc .pdf-summary code { background: #eef2f8; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
    .pdf-doc .pdf-summary pre { background: #f5f7fb; padding: 10px; border-radius: 6px; white-space: pre-wrap; }
    .pdf-doc .pdf-summary blockquote { margin: 8px 0; padding: 2px 12px; border-left: 3px solid #c9d4e3; color: #606d83; }
    .pdf-doc .summary-math-block { display: block; text-align: center; margin: 8px 0; }
  `;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  // 원본 사진은 용량이 크므로 PDF에 넣기 전에 긴 변 1600px로 줄인다.
  async function photoSource(img) {
    try {
      if (img.decode) await img.decode();
      const w = img.naturalWidth, h = img.naturalHeight;
      if (!w || !h) return img.src;
      const scale = Math.min(1, 1600 / Math.max(w, h));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      const context = canvas.getContext('2d');
      context.fillStyle = '#fff';
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(img, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/jpeg', 0.88);
    } catch (error) {
      return img.src;
    }
  }

  function textBlock(text) {
    const block = node('div', 'pdf-ocr');
    text.split('\n').forEach(line => block.append(node('div', 'pdf-line', line || '\u00a0')));
    return block;
  }

  async function buildDocument(section, filename) {
    const doc = node('div', 'pdf-doc');
    doc.append(node('style', '', PDF_CSS));
    doc.append(node('h1', '', '판서노트 정리'));
    doc.append(node('p', 'pdf-meta', `${filename} · ${new Date().toLocaleString('ko-KR')}`));

    // 1. 원본·보정 사진 (왼쪽 원본, 오른쪽 보정)
    doc.append(node('h2', '', '1. 원본 · 보정 사진'));
    const photos = node('div', 'pdf-photos');
    const sources = section.querySelectorAll('.image-grid figure img');
    const labels = ['원본 이미지', '보정 이미지'];
    for (let i = 0; i < labels.length; i += 1) {
      const figure = node('figure', 'pdf-photo');
      figure.append(node('figcaption', '', labels[i]));
      if (sources[i] && sources[i].getAttribute('src')) {
        const image = document.createElement('img');
        image.alt = labels[i];
        image.src = await photoSource(sources[i]);
        try { await image.decode(); } catch (error) { /* 로드 실패 시 아래 캡처에서 처리 */ }
        figure.append(image);
      } else {
        figure.append(node('p', 'pdf-note', '사진이 없습니다.'));
      }
      photos.append(figure);
    }
    doc.append(photos);

    // 2. Gemini 요약
    doc.append(node('div', 'html2pdf__page-break'));
    doc.append(node('h2', '', '2. Gemini 정리·요약'));
    const summary = section.querySelector('.summary-text');
    if (summary) {
      const body = node('div', 'pdf-summary');
      if (summary.classList.contains('is-rendered')) {
        const clone = summary.cloneNode(true);
        // KaTeX의 보이지 않는 MathML 사본은 PDF 캡처에서 수식이 두 번 나오게 하므로 제거한다.
        clone.querySelectorAll('.katex-mathml').forEach(item => item.remove());
        body.append(...clone.childNodes);
      } else {
        const raw = document.getElementById(summary.dataset.source);
        body.append(textBlock(raw ? raw.value : summary.textContent));
      }
      doc.append(body);
    } else {
      const message = section.querySelector('.summary-card .error, .summary-card .hint');
      doc.append(node('p', 'pdf-note pdf-error', message ? message.textContent : '요약 결과가 없습니다.'));
    }
    return doc;
  }

  async function exportPdf(button) {
    const section = button.closest('.results-section');
    const status = section.querySelector('.pdf-status');
    const label = button.textContent;
    const say = message => { if (status) { status.textContent = message; status.hidden = !message; } };
    if (!window.html2pdf) {
      say('PDF 도구를 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침해 주세요.');
      return;
    }
    button.disabled = true;
    button.textContent = 'PDF 만드는 중…';
    say('');
    try {
      if (document.fonts && document.fonts.ready) await document.fonts.ready;
      const base = (button.dataset.filename || '판서노트').replace(/\.[^.]+$/, '').replace(/[\\/:*?"<>|]/g, '_');
      const doc = await buildDocument(section, button.dataset.filename || '판서노트');
      await window.html2pdf().set({
        margin: [14, 14, 14, 14],
        filename: `판서노트_${base}.pdf`,
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false, scrollX: 0, scrollY: 0 },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak: { mode: ['css', 'legacy'], avoid: ['img', 'tr', 'blockquote', '.summary-math-block', 'h2', 'h3', 'li', 'p', '.pdf-line'] }
      }).from(doc).save();
    } catch (error) {
      console.error(error);
      say('PDF를 만들지 못했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('.pdf-btn');
    if (button && !button.disabled) exportPdf(button);
  });
})();
