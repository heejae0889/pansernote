"""Local Korean PaddleOCR adapter with bounded detection resolution."""

_ocr = None
OCR_VERSION = 'PP-OCRv5'
OCR_MAX_SIDE = 2048


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


def run_ocr(image, *, max_side=OCR_MAX_SIDE):
    """Return text/score rows. Bound the detector cost on large phone photos.

    The original high-resolution pixels remain available to the recognition
    stage. Do not filter low-confidence text or guess corrected wording here.
    """
    if max_side < 32:
        raise ValueError('OCR max_side must be at least 32')
    results = get_ocr().predict(image, text_det_limit_side_len=max_side,
                                text_det_limit_type='max')
    lines = []
    for result in results:
        for text, score in zip(result['rec_texts'], result['rec_scores']):
            if text.strip():
                lines.append({'text': text, 'score': round(float(score), 3)})
    return lines
