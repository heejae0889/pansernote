"""
Gemini로 판서 내용 정리, 요약
- 이미지 말고 OCR 결과 텍스트만 보냄
- 키랑 모델은 .env 에서 읽음
"""

import json
import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 90

SYSTEM_INSTRUCTION = """\
너는 대학 강의 판서를 정리해 주는 조교야.
입력은 칠판 사진을 OCR한 텍스트라서 오타, 깨진 기호, 순서가 뒤섞인 줄이 있을 수 있어.

[내용 규칙]
1. 문맥상 명백한 인식 오류만 바로잡아. 판서에 없는 내용을 지어내지 마.
2. 원래 무엇이었는지 확신할 수 없는 부분은 [?]로 표시해.
3. 판서에 쓰인 내용을 빠뜨리지 말고 정리해. 설명을 덧붙일 때는 판서 내용과 구분되게 써.
4. 한국어로 답해.

[출력 형식]
아래 두 부분만 출력해.
## 정리된 필기
(판서 내용을 읽기 좋게 정리. 소제목, 목록, 표를 자유롭게 사용)
## 핵심 요약
(3~5개의 짧은 목록)

[표기 규칙]
1. 전체는 마크다운(Markdown)으로 작성해. 표가 필요하면 마크다운 표를 써.
2. 수학 공식과 수학 기호는 반드시 LaTeX로 써. 문장 속 수식은 $...$, 따로 떼어 쓰는 수식은 $$...$$로 감싸.
2-1. 코드, 파일명, 명령어처럼 수학이 아닌 것은 LaTeX로 감싸지 말고 백틱(`)을 써.
3. [가장 중요] 수식 블록($ 또는 $$) 안에는 한글 설명을 섞지 마.
   - 잘못된 예: $$ x^2 입니다. 따라서 y^2 $$
   - 올바른 예: $$ x^2 $$ 입니다. 따라서 $$ y^2 $$
4. 여러 줄 수식 전개는 $$ 안에서 \\begin{aligned} ... \\end{aligned}를 써. \\begin{align}은 쓰지 마.
5. KaTeX가 지원하는 기본 문법만 사용해.
6. 괄호와 $, $$ 기호의 짝을 반드시 맞춰.
"""


class GeminiError(Exception):
    pass


def summarize(ocr_text):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    if not api_key:
        raise GeminiError(".env 파일에 GEMINI_API_KEY가 없습니다. 키를 넣고 서버를 다시 켜 주세요.")

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [
            {"role": "user", "parts": [{"text": "다음은 판서 사진을 OCR한 결과야. 정리해 줘.\n\n" + ocr_text}]}
        ],
    }
    # thinkingLevel은 gemini-3 모델만 됨 (minimal로 하면 지시를 잘 안 따라서 low로 함)
    if model.startswith("gemini-3"):
        body["generationConfig"] = {"thinkingConfig": {"thinkingLevel": "low"}}

    try:
        res = requests.post(
            API_URL.format(model=model),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=body,
            timeout=TIMEOUT,
        )
    except requests.Timeout:
        raise GeminiError("Gemini 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.")
    except requests.RequestException:
        raise GeminiError("Gemini에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.")

    if not res.ok:
        raise GeminiError(error_message(res, model))

    try:
        data = res.json()
    except ValueError:
        raise GeminiError("Gemini 응답을 읽을 수 없습니다.")

    candidate = (data.get("candidates") or [{}])[0]
    finish_reason = candidate.get("finishReason")

    # thought 파트는 답변이 아니라서 빼고 나머지 이어붙임
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()

    if not text:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or finish_reason
        raise GeminiError(f"답변을 받지 못했습니다. (사유: {reason})")

    notice = None
    if finish_reason == "MAX_TOKENS":
        notice = "답변이 길어서 중간에 잘렸습니다."
    elif finish_reason and finish_reason != "STOP":
        notice = f"답변이 중간에 멈췄습니다. (사유: {finish_reason})"

    return {"text": text, "notice": notice, "model": model}


def error_message(res, model):
    try:
        detail = json.loads(res.text).get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detail = ""

    code = res.status_code
    if code in (401, 403):
        msg = f"API 키가 올바르지 않습니다. ({code})"
    elif code in (400, 404):
        msg = f"요청이 거부됐습니다. ({code}) 모델 이름({model})이나 키를 확인해 주세요."
    elif code == 429:
        msg = "사용량 한도를 넘었습니다. (429) 잠시 후 다시 시도해 주세요."
    elif code >= 500:
        msg = f"Gemini 서버 오류입니다. ({code}) 잠시 후 다시 시도해 주세요."
    else:
        msg = f"요청이 실패했습니다. ({code})"
    return f"{msg}\n{detail}" if detail else msg
