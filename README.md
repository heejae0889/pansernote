# 판서노트

판서 사진을 OpenCV로 전처리하고 PaddleOCR로 문자를 추출하는 Flask 웹 프로그램입니다.

## 주요 개선 사항

- **사진 업로드** — 파일 선택, 카메라 촬영, 드래그 앤 드롭으로 최대 5장을 올릴 수 있습니다. 사진을 선택하면 칠판 아이콘이 파란색으로 채워지고, 선택한 사진 수와 파일명이 표시됩니다.
- **칠판 원근 보정** — 자동으로 테두리를 찾기 어렵거나 감지 점수가 낮으면 수동 조정을 제안합니다. 네 모서리를 직접 맞추거나 보정을 건너뛸 수 있으며, 결과 화면에서 보정 적용 여부를 확인할 수 있습니다.
- **보정 영역 안팎의 글자 추출** — 보정 이미지에서 칠판 안쪽을 읽고, 원본 사진에서 보정 영역 밖이나 경계에 걸친 글자를 추가로 읽습니다.
- **OCR 텍스트 수정과 재요약** — 잘못 읽혔거나 빠진 글자를 직접 고친 뒤, 사진을 다시 올리지 않고 해당 사진의 요약을 갱신할 수 있습니다.
- **Gemini 정리·요약** — 읽힌 판서를 주제별로 정리하고, 주제가 분명하면 관련 개념 풀이를 덧붙입니다. 핵심 요약에는 판서에서 확인된 내용만 담고, 처리 안내는 구분선 아래에 작은 회색 글씨로 표시합니다.
- **Gemini 오류 시 자동 재시도** — 업로드 직후 자동 요약이 시간 초과되거나 `503` 오류가 발생하면 한 번 더 요청합니다. 재시도도 실패하면 안내를 표시하며 추출한 글자는 계속 볼 수 있습니다.
- **처리 결과 책갈피** — 제출할 때마다 번호가 붙은 결과 페이지가 추가됩니다. 새 사진을 처리하는 동안에도 이전 결과와 수정한 글자를 볼 수 있습니다. 처리 중인 페이지는 점 세 개로 표시되며, 새로고침하면 책갈피 기록이 초기화됩니다.
- **Docker 실행 환경** — Docker Compose로 앱과 의존성을 실행할 수 있도록 구성했습니다. 컨테이너 헬스체크를 추가하고, 업로드 파일과 OCR 모델 캐시는 Docker 볼륨에 저장합니다.

## 실행

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/app.py
```

Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python src/app.py
```

브라우저에서 http://localhost:5001 에 접속합니다. 최초 OCR 실행 시 모델을 내려받습니다.

### Gemini 요약 설정

[Google AI Studio](https://aistudio.google.com/app/apikey)에서 API 키를 발급받고, `.env.example`을 `.env`로 복사한 뒤 `GEMINI_API_KEY`에 키를 넣습니다. `GEMINI_MODEL`을 비워두면 `gemini-3.5-flash-lite`를 사용합니다. `.env`는 Git에서 제외됩니다.

```bash
cp .env.example .env
```

## 파일 구성

```text
src/
├── app.py              # 업로드 처리 및 전처리·OCR 연결
├── preprocess.py       # OpenCV 전처리 및 자동 원근 보정
├── ocr.py              # PaddleOCR 문자 추출
├── summarize.py        # Gemini 요약
├── templates/index.html
└── static/
    ├── style.css
    └── render.js       # 마크다운, 수식(KaTeX) 표시
```

업로드 이미지는 실행 중 생성되는 `src/static/uploads/`에 저장되며 Git에서 제외합니다.

## 전처리 연결

```python
from preprocess import preprocess_image

processed = preprocess_image(image)
# 자동 원근 보정이 필요한 경우
processed = preprocess_image(image, perspective=True)
```

입력과 출력은 `uint8` BGR 3채널 배열입니다. 기본 처리는 최대 변 2800픽셀 제한, 어두운 배경 반전, 원본 색과 획을 유지하는 약한 밝기 보정입니다. 원근·기울기 보정은 선택 기능입니다. 경계를 찾지 못하면 원근 보정은 건너뜁니다. 가로세로 비율은 카메라 가정에 따른 추정값입니다.

사진 한 장을 OCR 없이 처리하려면:

```powershell
.\.venv\Scripts\python.exe src/preprocess.py input.jpg preprocess_output/processed.png --perspective
```

옵션은 `src/preprocess.py --help`에서 확인합니다. 출력은 처리된 이미지 한 장이며, OCR 비교 보고서나 중간 이미지는 생성하지 않습니다.

## 사용한 오픈소스

- [OpenCV](https://github.com/opencv/opencv) — Apache 2.0
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — Apache 2.0
- [Flask](https://github.com/pallets/flask) — BSD-3-Clause
- [KaTeX](https://github.com/KaTeX/KaTeX) — MIT
- [marked](https://github.com/markedjs/marked) — MIT

웹 업로드에서는 자동 원근 보정을 기본으로 시도합니다. 칠판 경계를 찾지 못한 사진은 원근 보정을 건너뜁니다. `preprocess_image(image)`를 직접 호출할 때는 `perspective=True`를 지정해야 원근 보정이 활성화됩니다.

웹에서 「전처리만 (OCR 없음)」 모드를 선택하면 원근·밝기 보정 이미지만 확인할 수 있습니다. 결과에 전처리 시간과 OCR 시간을 따로 표시합니다. OCR 모드는 모델 초기 로딩과 문자 추론 시간이 추가됩니다.

## 외부 API

- [Gemini API](https://ai.google.dev/) — OCR로 인식한 텍스트를 정리·요약합니다. 텍스트가 Google 서버로 전송됩니다.

