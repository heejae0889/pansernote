# 판서노트

강의 판서 사진을 올리면 글자를 인식하고 내용을 정리해 주는 웹 서비스 (오픈소스기초설계 공통반 4팀)

## 실행 방법 (Ubuntu 기준)

Python 3.10 ~ 3.12 권장

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python src/app.py
```
브라우저에서 http://localhost:5001 접속

> 처음 OCR을 돌릴 때 PaddleOCR 모델 파일을 자동으로 다운로드하기 때문에 시간이 걸림.
> (모델은 `~/.paddlex/official_models/` 에 저장됨)

## 폴더 구조

```
src/
├── app.py            # 웹 서버 (업로드 처리)
├── preprocess.py     # OpenCV 전처리
├── ocr.py            # PaddleOCR 문자 인식
├── templates/
│   └── index.html
└── static/
    ├── style.css
    └── uploads/      # 업로드된 사진 저장 (git 제외)
```

## 사용한 오픈소스

- [OpenCV](https://github.com/opencv/opencv) - Apache 2.0
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - Apache 2.0
- [Flask](https://github.com/pallets/flask) - BSD-3-Clause
