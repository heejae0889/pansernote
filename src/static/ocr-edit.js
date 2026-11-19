(() => {
  'use strict';

  function showNotice(element, message) {
    element.textContent = message || '';
    element.hidden = !message;
  }

  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!form.matches('.ocr-edit-form')) return;
    event.preventDefault();
    const input = form.elements.text;
    const button = form.querySelector('button[type="submit"]');
    const summary = form.closest('.results-section').querySelector('.summary-card');
    const content = summary.querySelector('.summary-text');
    const source = document.getElementById(content.dataset.source);
    const error = summary.querySelector('.summary-error');
    const notice = summary.querySelector('.summary-notice');
    const time = summary.querySelector('.summary-time');
    const label = button.textContent;

    if (button.disabled) return;
    button.disabled = true;
    input.readOnly = true;
    button.textContent = '다시 요약하는 중…';
    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: input.value })
      });
      const result = await response.json();
      if (!response.ok) {
        showNotice(error, result.error);
        return;
      }
      source.value = result.summary.text;
      content.hidden = !result.summary.text;
      content.dispatchEvent(new Event('summary:updated', { bubbles: true }));
      showNotice(error, '');
      showNotice(notice, result.summary.notice);
      showNotice(time, `요약 처리 시간 ${result.seconds.toFixed(2)}초`);
    } catch {
      showNotice(error, '다시 요약하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      input.readOnly = false;
      button.disabled = false;
      button.textContent = label;
    }
  });
})();
