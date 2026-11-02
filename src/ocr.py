"""
- 우선적으로 한글 판서가 대부분이라 lang을 korean으로 설정해놓음, 아마 나중에 더 늘려가면 될듯
"""

_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR

        _ocr = PaddleOCR(
            lang="korean",
            use_doc_orientation_classify=False,  # 문서 방향 분류 안 씀
            use_doc_unwarping=False,             # 문서 펴기 안 씀
            use_textline_orientation=False,      # 글줄 방향 분류 안 씀
        )
    return _ocr


def run_ocr(image):
    """BGR 이미지(numpy 배열)를 받아서 [{"text": ..., "score": ...}, ...] 를 돌려줌"""
    ocr = get_ocr()
    results = ocr.predict(image)

    lines = []
    for res in results:
        for text, score in zip(res["rec_texts"], res["rec_scores"]):
            if text.strip():
                lines.append({"text": text, "score": round(float(score), 3)})
    return lines
