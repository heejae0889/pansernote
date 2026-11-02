"""
판서 이미지 전처리 (OpenCV)

  1. 크기 조정   : 너무 큰 사진은 긴 변 기준으로 줄임
  2. 흑백 변환
  3. 색 반전     : 칠판(어두운 배경 + 밝은 글씨)이면 흰 배경 + 검은 글씨로 뒤집음
  4. 명암 보정   : CLAHE
  5. 노이즈 제거

TODO
  - 기울기 보정 (deskew)
  - 원근 보정 (칠판 영역 찾아서 정면으로 펴기)
  - 이진화(adaptive threshold) 적용했을 때 OCR 결과 비교
"""

import cv2

MAX_SIDE = 1600          # 긴 변 최대 길이
DARK_THRESHOLD = 127     # 평균 밝기가 이 값보다 낮으면 칠판으로 판단, 아마 조정이 필요할 수도


def resize_max(image, max_side=MAX_SIDE):
    h, w = image.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)


def to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def invert_if_dark(gray):
    if gray.mean() < DARK_THRESHOLD:
        return cv2.bitwise_not(gray)
    return gray


def enhance_contrast(gray):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def remove_noise(gray):
    return cv2.fastNlMeansDenoising(gray, h=10)


def preprocess_image(image):
    """BGR 이미지를 받아서 전처리된 BGR 이미지를 돌려준다.
    (PaddleOCR 입력이 3채널이라 마지막에 다시 BGR로 바꿈)"""
    image = resize_max(image)
    gray = to_gray(image)
    gray = invert_if_dark(gray)
    gray = enhance_contrast(gray)
    gray = remove_noise(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
