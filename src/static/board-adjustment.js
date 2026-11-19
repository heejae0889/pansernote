(() => {
  'use strict';

  const form = document.getElementById('upload-form');
  const submit = document.getElementById('btn');
  const submitLabel = submit.innerHTML;
  const status = document.getElementById('processing-status');
  const uploadError = document.getElementById('board-detection-error');
  const adjustments = document.getElementById('board-adjustments');
  const confirm = document.getElementById('board-confirm');
  const editor = document.getElementById('board-editor');
  const preview = editor.querySelector('.board-preview');
  const image = preview.querySelector('img');
  const canvas = preview.querySelector('canvas');
  const context = canvas.getContext('2d');
  const corners = [...preview.querySelectorAll('.board-corner')];
  const editorError = editor.querySelector('.board-editor-error');
  let points;

  function choose(dialog, filename) {
    dialog.querySelector('.board-filename').textContent = filename;
    dialog.returnValue = 'skip';
    return new Promise(resolve => {
      dialog.addEventListener('close', () => resolve(dialog.returnValue), { once: true });
      dialog.showModal();
    });
  }

  function draw() {
    canvas.width = preview.clientWidth;
    canvas.height = preview.clientHeight;
    context.beginPath();
    points.forEach(([x, y], index) => {
      corners[index].style.left = `${x * 100}%`;
      corners[index].style.top = `${y * 100}%`;
      const position = [x * canvas.width, y * canvas.height];
      if (index === 0) context.moveTo(...position);
      else context.lineTo(...position);
    });
    context.closePath();
    context.fillStyle = '#2674ce33';
    context.fill();
    context.strokeStyle = '#fff';
    context.lineWidth = 4;
    context.stroke();
    context.strokeStyle = '#1765b8';
    context.lineWidth = 2;
    context.stroke();
  }

  function move(index, x, y) {
    const clamp = value => Math.max(0, Math.min(1, value));
    points[index] = [clamp(x), clamp(y)];
    editorError.hidden = true;
    draw();
  }

  corners.forEach((corner, index) => {
    corner.addEventListener('pointerdown', event => {
      if (event.button === 0) corner.setPointerCapture(event.pointerId);
    });
    corner.addEventListener('pointermove', event => {
      if (!corner.hasPointerCapture(event.pointerId)) return;
      const bounds = preview.getBoundingClientRect();
      move(index, (event.clientX - bounds.left) / bounds.width,
        (event.clientY - bounds.top) / bounds.height);
    });
    corner.addEventListener('keydown', event => {
      const offsets = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      const offset = offsets[event.key];
      if (!offset) return;
      event.preventDefault();
      const [x, y] = points[index];
      move(index, x + offset[0] / 100, y + offset[1] / 100);
    });
  });
  window.addEventListener('resize', () => { if (editor.open) draw(); });

  editor.querySelector('form').addEventListener('submit', event => {
    if (event.submitter?.value !== 'apply') return;
    const valid = points.every(([x, y], index) => {
      const [nextX, nextY] = points[(index + 1) % 4];
      const [lastX, lastY] = points[(index + 2) % 4];
      return (nextX - x) * (lastY - nextY) - (nextY - y) * (lastX - nextX) > 0;
    });
    if (!valid) {
      event.preventDefault();
      editorError.textContent = '모서리를 겹치거나 교차하지 않게 배치해 주세요.';
      editorError.hidden = false;
    }
  });

  async function adjust(file) {
    if (await choose(confirm, file.name) !== 'adjust') return false;
    const url = URL.createObjectURL(file);
    try {
      image.src = url;
      try {
        await image.decode();
      } catch {
        throw new Error(`사진 미리보기를 열 수 없습니다. ${file.name} 파일을 다시 선택해 주세요.`);
      }
      points = [[.08, .08], [.92, .08], [.92, .92], [.08, .92]];
      editorError.hidden = true;
      const choice = choose(editor, file.name);
      draw();
      return await choice === 'apply' ? points : false;
    } finally {
      image.removeAttribute('src');
      URL.revokeObjectURL(url);
    }
  }

  function reset() {
    submit.disabled = false;
    submit.innerHTML = submitLabel;
    status.hidden = true;
    adjustments.value = 'null';
  }
  window.addEventListener('pageshow', reset);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const data = new FormData(form);
    const files = data.getAll('image');
    uploadError.hidden = true;
    submit.disabled = true;
    submit.textContent = '칠판 테두리 확인 중…';
    try {
      const response = await fetch(form.dataset.boardDetection, { method: 'POST', body: data });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      const selections = files.map(() => null);
      for (const index of result.failed) selections[index] = await adjust(files[index]);
      const currentFiles = new FormData(form).getAll('image');
      if (currentFiles.length !== files.length || currentFiles.some((file, index) => file !== files[index])) {
        throw new Error('사진 선택이 변경됐습니다. 다시 실행해 주세요.');
      }
      adjustments.value = JSON.stringify(selections);
      submit.textContent = '처리 중…';
      status.hidden = false;
      form.submit();
    } catch (error) {
      reset();
      uploadError.textContent = error instanceof SyntaxError ? '칠판을 확인하지 못했습니다. 다시 시도해 주세요.' : error.message;
      uploadError.hidden = false;
    }
  });
})();
