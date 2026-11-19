"""
Gemini로 판서 내용 정리, 요약
- 이미지 말고 OCR 결과 텍스트만 보냄
- 키랑 모델은 .env 에서 읽음
"""

import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

DEFAULT_MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30

SYSTEM_INSTRUCTION = """\
너는 대학 강의 판서를 정리해 주는 조교야.
입력은 칠판 사진을 OCR한 텍스트라서 오타, 깨진 기호, 순서가 뒤섞인 줄이 있을 수 있어.

[내용 규칙]
1. 읽을 수 있는 판서 문장과 관련 용어를 주제별로 묶고, 같은 내용을 합쳐 복습할 수 있는 필기로 정리해.
2. 판서에서 관계가 드러나는 개념은 무엇이고 어떻게 연결되는지 자연스러운 문장으로 풀어 써.
   함께 등장했다는 이유만으로 판서에서 그 관계를 설명했다고 단정하지 마.
3. 주제나 용어가 분명하면 정리된 필기 아래 `### 관련 개념 풀이`에 그 용어의 일반적인 뜻이나 바로 연결되는 개념을 짧게 설명해.
   판서에 직접 쓰인 내용처럼 표현하지 말고, 읽힌 용어에서 출발해 설명해. 주제가 불분명하면 이 소제목을 생략해.
4. 명백한 오타와 띄어쓰기만 바로잡아. 판서의 수치, 단위, 기호, 수식, 표의 셀 위치가 불확실하면 추측하지 마.
   의미가 통하는 문장에 빈 부분이 있으면 필요한 곳에만 [?]를 쓰고, 의미 없는 문자 조각은 본문에서 빼.
5. 핵심 요약에는 판서에서 확인되는 개념이나 관계만 담아. 관련 개념 풀이에서 보충한 내용은 요약에 넣지 마.
   확인되는 내용이 한 가지면 한 줄만 써.
   확인되는 내용이 없으면 빈 필기를 길게 늘리지 말고, 입력이 부족하다는 안내만 아래 규칙대로 남겨.
6. OCR이나 요약 처리 절차, 시도한 방법, 인식 실패, 표기 방침은 필기와 핵심 요약에 넣지 마.
7. 한국어로 답해.

예를 들어 입력에 `표본화`, `샘플링 주파수`, `q1?`만 있다면 확인된 두 용어를 정리한 뒤,
관련 개념 풀이에서 샘플링 주파수가 1초에 신호를 몇 번 측정하는지를 나타낸다고 설명해.
판서에 나온 주파수 값이나 `q1?`의 뜻은 추측하지 마.

[출력 형식]
정리할 수 있는 내용이 있으면 아래 두 부분을 출력해.
## 정리된 필기
(판서 내용을 읽기 좋게 정리. 필요하면 관련 개념 풀이를 소제목으로 덧붙여)
## 핵심 요약
(판서의 핵심 개념과 내용만 짧은 목록으로 정리)

OCR 입력이 불완전해 사용자에게 알려야 할 점이 있으면 마지막에 `## 처리 안내`를 별도 줄에 쓰고,
그 아래에 입력의 한계를 짧은 일반 텍스트로 써. 안내가 없으면 이 부분을 생략해.
실제로 주어지지 않은 처리 단계나 재시도 여부는 추측하지 마.

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
7. HTML 태그를 출력하지 마. 답변 전체를 코드 블록으로 감싸지 마.
8. 수식을 백틱이나 코드 블록으로 감싸지 마. LaTeX 명령의 역슬래시를 불필요하게 이중으로 쓰지 마.
"""


class GeminiError(Exception):
    pass


class GeminiTimeout(GeminiError):
    pass


class GeminiUnavailable(GeminiError):
    pass


def summarize(ocr_text):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    if not api_key:
        raise GeminiError(".env 파일에 GEMINI_API_KEY가 없습니다. 키를 넣고 서버를 다시 켜 주세요.")

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [
            {"role": "user", "parts": [{"text": "다음 판서 텍스트에서 확인할 수 있는 내용을 복습용 필기로 정리해 줘.\n\n" + ocr_text}]}
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
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        )
    except requests.Timeout as error:
        raise GeminiTimeout("Gemini 응답 시간이 초과됐습니다. 잠시 후 다시 시도해 주세요.") from error
    except requests.RequestException:
        raise GeminiError("Gemini에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.")

    if not res.ok:
        message = error_message(res, model)
        if res.status_code == 503:
            raise GeminiUnavailable(message)
        raise GeminiError(message)

    try:
        data = res.json()
    except ValueError:
        raise GeminiError("Gemini 응답을 읽을 수 없습니다.")

    candidate = (data.get("candidates") or [{}])[0]
    finish_reason = candidate.get("finishReason")

    # thought 파트는 답변이 아니라서 빼고 나머지 이어붙임
    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()

    sections = re.split(r"(?m)^#{1,6}[ \t]+처리 안내[ \t]*\r?$", text, maxsplit=1)
    text = sections[0].strip()
    notices = [section.strip() for section in sections[1:] if section.strip()]
    if not text and not notices:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or finish_reason
        raise GeminiError(f"답변을 받지 못했습니다. (사유: {reason})")

    if finish_reason == "MAX_TOKENS":
        notices.append("답변이 길어서 중간에 잘렸습니다.")
    elif finish_reason and finish_reason != "STOP":
        notices.append(f"답변이 중간에 멈췄습니다. (사유: {finish_reason})")

    return {"text": text, "notice": "\n".join(notices) or None, "model": model}


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
