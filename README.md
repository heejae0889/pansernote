# 판서노트

판서 사진을 OpenCV로 전처리하고 PaddleOCR로 문자를 추출하는 Flask 웹 프로그램입니다.

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

