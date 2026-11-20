"""Local Korean PaddleOCR adapter with bounded detection resolution."""

import cv2
import numpy as np

_ocr = None
OCR_VERSION = 'PP-OCRv5'
OCR_MAX_SIDE = 1280


def get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(
            lang='korean',
            ocr_version=OCR_VERSION,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return _ocr


def run_ocr(image, *, max_side=OCR_MAX_SIDE, outside_board=None):
    """Return text/score rows. Bound the detector cost on large phone photos.

    The original high-resolution pixels remain available to the recognition
    stage. Do not filter low-confidence text or guess corrected wording here.
    """
    if max_side < 32:
        raise ValueError('OCR max_side must be at least 32')
    results = get_ocr().predict(image, text_det_limit_side_len=max_side,
                                text_det_limit_type='max')
    lines = []
    board = np.asarray(outside_board, dtype=np.float32) if outside_board is not None else None
    for result in results:
        for index, (text, score) in enumerate(zip(result['rec_texts'], result['rec_scores'])):
            if not text.strip():
                continue
            if board is not None:
                polygon = cv2.convexHull(np.asarray(result['rec_polys'][index], dtype=np.float32))
                area = cv2.contourArea(polygon)
                if area <= 0:
                    continue
                inside, _ = cv2.intersectConvexConvex(board, polygon)
                # Keep boundary-crossing text, allowing a small detection margin.
                if inside >= area * .90:
                    continue
            lines.append({'text': text, 'score': round(float(score), 3)})
    return lines
