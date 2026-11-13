"""
판서노트 - 웹 서버 (Flask)

실행:  python src/app.py   ->  http://localhost:5001
"""

import os
import uuid
from time import perf_counter

import cv2
import numpy as np
from flask import Flask, render_template, request, url_for

from ocr import run_ocr
from preprocess import preprocess_image
from summarize import summarize

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"jpg", "jpeg", "png"}


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024 
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_ext(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def save_image(path, image):
    # cv2.imwrite 는 경로에 한글이 있으면 실패할 때가 있어서 imencode 사용
    ext = os.path.splitext(path)[1]
    ok, buf = cv2.imencode(ext, image)
    if ok:
        buf.tofile(path)


def make_result(label, lines):
    # OCR 결과 한 개를 화면에 보여줄 형태로 정리 (줄 수, 평균 신뢰도 포함)
    scores = [line["score"] for line in lines]
    avg_score = round(sum(scores) / len(scores), 3) if scores else 0
    return {
        "label": label,
        "lines": lines,
        "text": "\n".join(line["text"] for line in lines),
        "count": len(lines),
        "avg_score": avg_score,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("image")
    if file is None or file.filename == "":
        return render_template("index.html", error="사진을 선택해주세요."), 400

    ext = get_ext(file.filename)
    if ext not in ALLOWED_EXT:
        return render_template("index.html", error="JPG, PNG 파일만 올릴 수 있습니다."), 400


    # ------------------------------------------------------------------------------------------------------------------------------ 업로드된 파일 -> OpenCV 이미지
    data = np.frombuffer(file.read(), np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    if image is None:
        return render_template("index.html", error="이미지를 읽을 수 없습니다."), 400

    # ------------------------------------------------------------------------------------------------------------------------------전처리
    preprocessing_started = perf_counter()
    try:
        processed = preprocess_image(image, perspective=True)
    except Exception:
        app.logger.exception("이미지 전처리 실패")
        return render_template("index.html", error="사진을 보정하지 못했습니다. 다른 사진으로 다시 시도해 주세요."), 500
    preprocessing_seconds = perf_counter()-preprocessing_started

    # 화면에 보여주려고 원본/전처리 이미지 저장
    name = uuid.uuid4().hex
    original_file = f"{name}_original.{ext}"
    processed_file = f"{name}_processed.png"
    save_image(os.path.join(UPLOAD_DIR, original_file), image)
    save_image(os.path.join(UPLOAD_DIR, processed_file), processed)

    # ------------------------------------------------------------------------------------------------------------------------------문자 인식
    # 보정한 이미지에서 문자를 추출합니다.
    results = []
    ocr_seconds = None
    ocr_started = perf_counter()
    try:
        results.append(make_result("추출한 글자", run_ocr(processed)))
    except Exception as e:
        app.logger.exception("OCR 실패")
        return render_template(
            "index.html",
            error=f"OCR 처리 중 오류가 났습니다: {e}",
            original_url=url_for("static", filename=f"uploads/{original_file}"),
            processed_url=url_for("static", filename=f"uploads/{processed_file}"),
        ), 500

    ocr_seconds = perf_counter()-ocr_started

    # ------------------------------------------------------------------------------------------------------------------------------정리·요약
    # 추출한 글자를 자동으로 정리하고 요약합니다.
    summary, summary_error, summary_seconds = None, None, None
    summary_label = results[-1]["label"] if results else None
    if results:
        ocr_text = results[-1]["text"]
        if not ocr_text.strip():
            summary_error = "인식된 글자가 없어서 요약하지 않았습니다."
        else:
            summary_started = perf_counter()
            try:
                summary = summarize(ocr_text)
            except Exception as e:  # 요약이 실패해도 OCR 결과는 보여줌
                summary_error = str(e)
            summary_seconds = perf_counter()-summary_started

    return render_template(
        "index.html",
        timings={"preprocess": preprocessing_seconds, "ocr": ocr_seconds, "summary": summary_seconds},
        original_url=url_for("static", filename=f"uploads/{original_file}"),
        processed_url=url_for("static", filename=f"uploads/{processed_file}"),
        results=results,
        summary=summary,
        summary_error=summary_error,
        summary_label=summary_label,
    )


@app.errorhandler(413)
def too_large(e):
    return render_template("index.html", error="파일이 너무 큽니다. (최대 10MB)"), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True, use_reloader=False, threaded=False)
