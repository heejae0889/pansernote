"""
판서노트 - 웹 서버 (Flask)

실행:  python src/app.py   ->  http://localhost:5001
"""

import json
import os
import uuid
from time import perf_counter, sleep

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request, url_for

from ocr import run_ocr
from preprocess import detect_board, preprocess_image, resize_max
from summarize import GeminiError, GeminiTimeout, GeminiUnavailable, summarize

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"jpg", "jpeg", "png"}
MAX_IMAGES = 5
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_EDITED_TEXT_LENGTH = 50_000


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGES * MAX_IMAGE_BYTES + 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_ext(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def save_image(path, image):
    # cv2.imwrite 는 경로에 한글이 있으면 실패할 때가 있어서 imencode 사용
    ext = os.path.splitext(path)[1]
    ok, buf = cv2.imencode(ext, image)
    if not ok:
        raise OSError("이미지를 인코딩하지 못했습니다.")
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


def validate_uploads(files):
    if not files:
        return "사진을 선택해주세요.", 400
    if len(files) > MAX_IMAGES:
        return "사진은 최대 5장까지 업로드할 수 있습니다.", 400
    for file in files:
        if get_ext(file.filename) not in ALLOWED_EXT:
            return "JPG, PNG 파일만 올릴 수 있습니다.", 400
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_IMAGE_BYTES:
            return "사진 한 장당 최대 10MB까지 업로드할 수 있습니다.", 413
    return None, 200


def decode_upload(file):
    data = np.frombuffer(file.read(), np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


@app.route("/board-detection", methods=["POST"])
def board_detection():
    files = [file for file in request.files.getlist("image") if file.filename]
    error, status = validate_uploads(files)
    if error:
        return jsonify(error=error), status
    failed = []
    for index, file in enumerate(files):
        image = decode_upload(file)
        if image is not None and min(image.shape[:2]) >= 2 and detect_board(resize_max(image)) is None:
            failed.append(index)
    return jsonify(failed=failed)


@app.route("/summarize-edited", methods=["POST"])
def summarize_edited():
    payload = request.get_json(silent=True)
    text = payload.get("text") if isinstance(payload, dict) else None
    if not isinstance(text, str) or not text.strip():
        return jsonify(error="요약할 글자를 입력해 주세요."), 400
    if len(text) > MAX_EDITED_TEXT_LENGTH:
        return jsonify(error="수정한 글자는 50,000자까지 요약할 수 있습니다."), 400

    started = perf_counter()
    try:
        summary = summarize(text.strip())
    except GeminiError as error:
        return jsonify(error=str(error)), 502
    return jsonify(summary=summary, seconds=perf_counter() - started)


@app.route("/upload", methods=["POST"])
def upload():
    files = [file for file in request.files.getlist("image") if file.filename]
    error, status = validate_uploads(files)
    if error:
        return render_template("index.html", error=error), status
    try:
        adjustments = json.loads(request.form.get("board_adjustments", "null"))
        if adjustments is None:
            adjustments = [None] * len(files)
        if not isinstance(adjustments, list) or len(adjustments) != len(files):
            raise ValueError
    except ValueError:
        return render_template("index.html", error="칠판 조정 정보가 올바르지 않습니다."), 400
    photos = []
    statuses = []
    for file, adjustment in zip(files, adjustments):
        result, status = process_file(file, adjustment=adjustment)
        photos.append(dict(result, filename=file.filename))
        statuses.append(status)
    status = 200 if any(code == 200 for code in statuses) else max(statuses)
    return render_template("index.html", photos=photos, result_batch=uuid.uuid4().hex), status


def process_file(file, *, adjustment=None):

    ext = get_ext(file.filename)
    if ext not in ALLOWED_EXT:
        return {"error": "JPG, PNG 파일만 올릴 수 있습니다."}, 400


    # ------------------------------------------------------------------------------------------------------------------------------ 업로드된 파일 -> OpenCV 이미지
    image = decode_upload(file)
    if image is None or min(image.shape[:2]) < 2:
        return {"error": "이미지를 읽을 수 없습니다."}, 400

    # ------------------------------------------------------------------------------------------------------------------------------전처리
    preprocessing_started = perf_counter()
    try:
        board_corners = None
        perspective_status = "원근 보정 미적용"
        if adjustment is False:
            processed = preprocess_image(image)
        else:
            processed, details = preprocess_image(
                image, perspective=adjustment is None, corners=adjustment, return_details=True
            )
            if details["perspective_applied"]:
                board_corners = details["perspective"]["corners"]
                perspective_status = "자동 원근 보정 적용" if adjustment is None else "수동 원근 보정 적용"
            del details
    except (TypeError, ValueError):
        if adjustment is not None and adjustment is not False:
            return {"error": "칠판 모서리가 올바르지 않습니다. 사진을 다시 선택해 주세요."}, 400
        app.logger.exception("이미지 전처리 실패")
        return {"error": "사진을 보정하지 못했습니다. 다른 사진으로 다시 시도해 주세요."}, 500
    except Exception:
        app.logger.exception("이미지 전처리 실패")
        return {"error": "사진을 보정하지 못했습니다. 다른 사진으로 다시 시도해 주세요."}, 500
    preprocessing_seconds = perf_counter()-preprocessing_started

    # 화면에 보여주려고 원본/전처리 이미지 저장
    name = uuid.uuid4().hex
    original_file = f"{name}_original.{ext}"
    processed_file = f"{name}_processed.png"
    try:
        save_image(os.path.join(UPLOAD_DIR, original_file), image)
        save_image(os.path.join(UPLOAD_DIR, processed_file), processed)
    except (OSError, cv2.error):
        app.logger.exception("이미지 저장 실패")
        return {"error": "사진을 저장하지 못했습니다. 다시 시도해 주세요."}, 500

    # ------------------------------------------------------------------------------------------------------------------------------문자 인식
    ocr_notice = None
    ocr_seconds = None
    ocr_started = perf_counter()
    try:
        lines = run_ocr(processed)
    except Exception as e:
        app.logger.exception("OCR 실패")
        return dict(
            error=f"OCR 처리 중 오류가 났습니다: {e}",
            perspective_status=perspective_status,
            original_url=url_for("static", filename=f"uploads/{original_file}"),
            processed_url=url_for("static", filename=f"uploads/{processed_file}"),
        ), 500

    if board_corners is not None:
        try:
            full_image = preprocess_image(image)
            lines.extend(run_ocr(full_image, outside_board=board_corners if lines else None))
        except Exception:
            app.logger.exception("보정 영역 밖 글자 추출 실패")
            ocr_notice = "보정 영역 밖 글자를 추가로 추출하지 못했습니다."
    results = [make_result("추출한 글자", lines)]
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
                try:
                    summary = summarize(ocr_text)
                except (GeminiTimeout, GeminiUnavailable) as error:
                    if isinstance(error, GeminiUnavailable):
                        sleep(1)
                    summary = summarize(ocr_text)
            except Exception as e:  # 요약이 실패해도 OCR 결과는 보여줌
                summary_error = str(e)
            summary_seconds = perf_counter()-summary_started

    return dict(
        timings={"preprocess": preprocessing_seconds, "ocr": ocr_seconds, "summary": summary_seconds},
        perspective_status=perspective_status,
        original_url=url_for("static", filename=f"uploads/{original_file}"),
        processed_url=url_for("static", filename=f"uploads/{processed_file}"),
        results=results,
        summary=summary,
        summary_error=summary_error,
        ocr_notice=ocr_notice,
        summary_label=summary_label,
    ), 200


@app.errorhandler(413)
def too_large(e):
    return render_template("index.html", error="사진은 최대 5장, 한 장당 최대 10MB까지 업로드할 수 있습니다."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True, use_reloader=False, threaded=False)
