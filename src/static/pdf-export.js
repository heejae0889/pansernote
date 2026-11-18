/* 처리 결과(원본 사진 + OCR 글자 + Gemini 요약)를 한 개의 PDF로 저장한다.
   화면에 이미 그려진 결과(마크다운/수식 렌더링 포함)를 그대로 사용하므로 서버 작업이 필요 없다. */
(() => {
  'use strict';

  const PDF_CSS = `
    .pdf-doc { font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif; color: #202c43; font-size: 13px; line-height: 1.7; background: #fff; }
    .pdf-doc h1 { font-size: 22px; margin: 0 0 4px; color: #1f3a66; }
    .pdf-doc .pdf-meta { font-size: 11px; color: #606d83; margin: 0 0 18px; padding-bottom: 10px; border-bottom: 2px solid #365b91; }
    .pdf-doc h2 { font-size: 16px; margin: 22px 0 10px; padding-left: 9px; border-left: 4px solid #365b91; color: #1f3a66; }
    .pdf-doc h3 { font-size: 14px; margin: 14px 0 6px; }
    .pdf-doc .pdf-photo { text-align: center; }
    .pdf-doc .pdf-photo img { max-width: 100%; max-height: 520px; border: 1px solid #d5deea; }
    .pdf-doc .pdf-note { font-size: 11px; color: #606d83; margin: 0 0 6px; }
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

  async function buildDocument(section, filename) {
    const doc = node('div', 'pdf-doc');
    doc.append(node('style', '', PDF_CSS));
    doc.append(node('h1', '', '판서노트 정리'));
    doc.append(node('p', 'pdf-meta', `${filename} · ${new Date().toLocaleString('ko-KR')}`));

    // 1. 원본 사진
    doc.append(node('h2', '', '1. 원본 사진'));
    const photo = node('div', 'pdf-photo');
    const original = section.querySelector('.image-grid figure img');
    if (original) {
      const image = document.createElement('img');
      image.alt = '원본 사진';
      image.src = await photoSource(original);
      photo.append(image);
    } else {
      photo.append(node('p', 'pdf-note', '원본 사진이 없습니다.'));
    }
    doc.append(photo);

    return doc;
  }

  async function exportPdf(button) {
    const section = button.closest('.results-section');
    const label = button.textContent;
    if (!window.html2pdf) return;
    button.disabled = true;
    button.textContent = 'PDF 만드는 중…';
    try {
      const base = (button.dataset.filename || '판서노트').replace(/\.[^.]+$/, '').replace(/[\\/:*?"<>|]/g, '_');
      const doc = await buildDocument(section, button.dataset.filename || '판서노트');
      await window.html2pdf().set({
        margin: [14, 14, 14, 14],
        filename: `판서노트_${base}.pdf`,
        image: { type: 'jpeg', quality: 0.95 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
      }).from(doc).save();
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
