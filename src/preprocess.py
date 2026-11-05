"""Board image preprocessing. Public input/output: uint8 BGR ndarray."""
from itertools import combinations

import cv2
import numpy as np

MAX_SIDE = 2800
DARK_THRESHOLD = 127
_EDGE_SAMPLES = np.linspace(.06, .94, 90)[None, :, None]
_GRID_SAMPLES = np.linspace(.10, .90, 13)[:, None]


def validate_image(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError('image must be a uint8 numpy array')
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 2:
        raise ValueError('image must be a nonempty BGR image, at least 2x2')


def resize_max(image, max_side=MAX_SIDE):
    if max_side < 2:
        raise ValueError('max_side must be at least 2')
    h, w = image.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale == 1:
        return image.copy()
    return cv2.resize(image, (max(2, round(w * scale)), max(2, round(h * scale))), interpolation=cv2.INTER_AREA)


def to_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def normalize_illumination(gray):
    """Estimate the background without ink, then divide out uneven lighting.

    No erosion of the output, pixel deletion, or generative restoration is used.
    A broad kernel follows lighting rather than individual text strokes.
    """
    size = max(15, min(121, int(round(min(gray.shape) * 0.04)) | 1))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (size, size))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    background = cv2.GaussianBlur(background, (0, 0), size / 6)
    normalized = cv2.divide(gray, np.maximum(background, 1), scale=245)
    return normalized, background


def enhance_contrast(gray):
    """Bounded global stretch: avoid CLAHE amplifying shadow boundaries/noise."""
    low, high = np.percentile(gray, (1, 99))
    if high - low < 35:
        return gray.copy()
    return np.clip((gray.astype(np.float32) - low) * 255 / (high - low), 0, 255).astype(np.uint8)


def adaptive_binary(gray):
    """Optional comparison only: thresholding can remove faint handwriting."""
    size = max(3, min(101, int(round(min(gray.shape) * 0.035)) | 1))
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                 cv2.THRESH_BINARY, size, 13)


def _ordered(points):
    points = np.asarray(points, np.float32).reshape(4, 2)
    center = points.mean(axis=0)
    points = points[np.argsort(np.arctan2(points[:, 1]-center[1], points[:, 0]-center[0]))]
    return np.roll(points, -np.argmin(points.sum(axis=1)), axis=0)


def _sample(image, points):
    xy = np.rint(points).astype(int)
    return image[np.clip(xy[..., 1], 0, image.shape[0]-1),
                 np.clip(xy[..., 0], 0, image.shape[1]-1)]


def _score(points, gray, distance):
    h, w = gray.shape
    if not cv2.isContourConvex(points.astype(np.float32)):
        return None
    area = abs(cv2.contourArea(points)) / (h*w)
    if not 0.25 <= area <= 0.94:
        return None
    if np.any(points[:, 0] < 2) or np.any(points[:, 0] > w-3) or np.any(points[:, 1] < 2) or np.any(points[:, 1] > h-3):
        return None
    lengths = np.linalg.norm(np.roll(points, -1, axis=0)-points, axis=1)
    if lengths.min() < min(h, w)*0.22 or lengths.max()/lengths.min() > 6:
        return None
    ends = np.roll(points, -1, axis=0)
    directions = ends-points
    normals = np.stack((-directions[:, 1], directions[:, 0]), axis=1)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    center = points.mean(axis=0)
    inward = np.sum(normals*(center-(points+ends)/2), axis=1)
    normals[inward < 0] *= -1
    edge = points[:, None, :]*(1-_EDGE_SAMPLES)+ends[:, None, :]*_EDGE_SAMPLES
    supports = np.mean(_sample(distance, edge) <= 3.0, axis=1)
    # Reject unsupported frames before sampling their interiors/contrast.
    if supports.min() < .40 or supports.mean() < .65:
        return None
    u = _GRID_SAMPLES
    left = points[0]*(1-u)+points[3]*u
    right = points[1]*(1-u)+points[2]*u
    grid = left[:, None, :]*(1-u[None, :, :])+right[:, None, :]*u[None, :, :]
    interior = _sample(gray, grid)
    polarity = 1 if np.median(interior) >= 127 else -1
    inside = _sample(gray, edge+normals[:, None, :]*7).astype(float)
    outside = _sample(gray, edge-normals[:, None, :]*7).astype(float)
    contrasts = np.median(inside-outside, axis=1)*polarity
    if np.count_nonzero(contrasts > 8) < 2:
        return None
    contrast = float(np.mean(np.clip(contrasts, 0, 100)) / 100)
    smoothness = max(0, 1-float(np.std(interior))/65)
    score = .45*np.mean(supports)+.30*contrast+.15*smoothness+.10*np.sqrt(area)
    return float(score), [round(x, 3) for x in supports]


def _line_groups(lines, h, w):
    horizontal, vertical = [], []
    for segment in sorted(lines, key=lambda q: -np.hypot(q[2]-q[0], q[3]-q[1])):
        x1, y1, x2, y2 = map(float, segment)
        dx, dy = x2-x1, y2-y1
        length = np.hypot(dx, dy)
        if length < .18*min(h, w):
            continue
        a, b = y1-y2, x2-x1
        norm = np.hypot(a, b)
        line = np.array([a, b, x1*y2-x2*y1])/norm
        angle = (np.degrees(np.arctan2(dy, dx))+90) % 180-90
        if abs(dy) <= abs(dx)*1.0:
            position = -(line[0]*(w/2)+line[2])/line[1]
            group = horizontal
        elif abs(dx) <= abs(dy)*.35:
            position = -(line[1]*(h/2)+line[2])/line[0]
            group = vertical
        else:
            continue
        if not any(abs(position-p) < 9 and min(abs(angle-ang), 180-abs(angle-ang)) < 3 for _, p, ang in group):
            group.append((line, position, angle))
    return horizontal[:14], vertical[:14]


def _frame_quads(horizontal, vertical, h, w):
    if len(horizontal) < 2 or len(vertical) < 2:
        return
    h_lines = np.array([item[0] for item in horizontal])
    v_lines = np.array([item[0] for item in vertical])
    # Each line intersection is shared by many quadrilaterals: compute once.
    cross = np.cross(h_lines[:, None, :], v_lines[None, :, :])
    valid = np.abs(cross[:, :, 2]) >= 1e-7
    intersections = np.full(cross.shape[:2]+(2,), np.nan, np.float32)
    np.divide(cross[:, :, :2], cross[:, :, 2, None],
              out=intersections, where=valid[:, :, None])
    vertical_pairs = []
    for pair in combinations(range(len(vertical)), 2):
        left, right = sorted(pair, key=lambda i: vertical[i][1])
        if vertical[right][1]-vertical[left][1] >= w*.25:
            vertical_pairs.append((left, right))
    for pair in combinations(range(len(horizontal)), 2):
        top, bottom = sorted(pair, key=lambda i: horizontal[i][1])
        if horizontal[bottom][1]-horizontal[top][1] < h*.25:
            continue
        for left, right in vertical_pairs:
            points = intersections[[top, top, bottom, bottom], [left, right, right, left]]
            if not np.isfinite(points).all():
                continue
            if points[0, 0] >= points[1, 0] or points[3, 0] >= points[2, 0] or points[0, 1] >= points[3, 1] or points[1, 1] >= points[2, 1]:
                continue
            yield points


def detect_board(image):
    """Return frame evidence and TL/TR/BR/BL corners, or None.

    This is a geometric heuristic, not a semantic board recognizer. Detection
    runs at bounded resolution and never extrapolates outside the photograph.
    """
    original_h, original_w = image.shape[:2]
    scale = min(1, 1100/max(original_h, original_w))
    small = cv2.resize(image, (round(original_w*scale), round(original_h*scale)), interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.GaussianBlur(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    h, w = gray.shape
    edges = cv2.Canny(gray, 40, 120)
    distance = cv2.distanceTransform(cv2.bitwise_not(edges), cv2.DIST_L2, 3)
    best = None
    def consider(points, method):
        nonlocal best
        score = _score(points, gray, distance)
        if score is not None and (best is None or score[0] > best[0]):
            best = (score[0], points, method, score[1])
    joined = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(joined, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:30]:
        for epsilon in (.015, .025):
            polygon = cv2.approxPolyDP(contour, epsilon*cv2.arcLength(contour, True), True)
            if len(polygon) == 4:
                consider(_ordered(polygon), 'contour')
    segments = cv2.HoughLinesP(edges, 1, np.pi/720, threshold=max(35, min(h, w)//14),
                               minLineLength=max(30, int(.18*min(h, w))), maxLineGap=max(10, int(.035*min(h, w))))
    if segments is not None:
        horizontal, vertical = _line_groups(segments.reshape(-1, 4), h, w)
        for points in _frame_quads(horizontal, vertical, h, w):
            consider(points, 'frame_lines')
    if best is None or best[0] < .60:
        return None
    score, points, method, supports = best
    points = points/np.array([w/original_w, h/original_h], np.float32)
    return {'corners': points.tolist(), 'method': method, 'score': round(score, 4),
            'edge_support': supports}


def estimate_aspect_ratio(points, image_shape):
    """Estimate rectangular-plane W/H assuming square pixels and centered optics.

    Unknown camera calibration/cropping makes this an approximation. Return
    None for degenerate or implausible calibration instead of forcing a ratio.
    """
    points = np.asarray(points, np.float32)
    corners = np.column_stack((points, np.ones(4)))
    top = np.cross(corners[0], corners[1])
    bottom = np.cross(corners[3], corners[2])
    left = np.cross(corners[0], corners[3])
    right = np.cross(corners[1], corners[2])
    horizontal = np.cross(top, bottom)
    vertical = np.cross(left, right)
    for point in (horizontal, vertical):
        if abs(point[2]) < 1e-7*np.linalg.norm(point[:2]):
            return None
    horizontal = horizontal[:2]/horizontal[2]
    vertical = vertical[:2]/vertical[2]
    height, width = image_shape[:2]
    center = np.array([width/2, height/2])
    focal_squared = -np.dot(horizontal-center, vertical-center)
    if not np.isfinite(focal_squared) or focal_squared <= 0:
        return None
    focal = np.sqrt(focal_squared)
    if not .35*max(width, height) <= focal <= 8*max(width, height):
        return None
    camera = np.array([[focal, 0, center[0]], [0, focal, center[1]], [0, 0, 1]])
    homography = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), points)
    metric = np.linalg.solve(camera, homography)
    ratio = np.linalg.norm(metric[:, 0])/np.linalg.norm(metric[:, 1])
    return float(ratio) if np.isfinite(ratio) and .25 <= ratio <= 4 else None


def rectify_board(image):
    """Detect and rectify one board, preserving the full image on rejection."""
    detection = detect_board(image)
    if detection is None:
        return image.copy(), {'requested': True, 'applied': False, 'reason': 'No supported board quadrilateral found'}
    points = np.float32(detection['corners'])
    tl, tr, br, bl = points
    width = max(np.linalg.norm(tr-tl), np.linalg.norm(br-bl))
    height = max(np.linalg.norm(bl-tl), np.linalg.norm(br-tr))
    ratio = estimate_aspect_ratio(points, image.shape)
    aspect_method = 'projected_edge_lengths'
    if ratio is not None:
        aspect_method = 'vanishing_points_centered_camera_assumption'
        long_side = max(width, height)
        if ratio >= 1:
            width, height = long_side, long_side/ratio
        else:
            width, height = long_side*ratio, long_side
    width, height = max(2, round(width)), max(2, round(height))
    target = np.float32([[0, 0], [width-1, 0], [width-1, height-1], [0, height-1]])
    matrix = cv2.getPerspectiveTransform(points, target)
    warped = cv2.warpPerspective(image, matrix, (width, height))
    details = dict(detection, requested=True, applied=True, output_size=[width, height],
                   aspect_method=aspect_method, estimated_aspect_ratio=ratio,
                   transform=matrix.tolist(),
                   caveat='Geometric heuristic; physical aspect ratio and OCR accuracy are not guaranteed.')
    return warped, details


def correct_perspective(image, *, return_details=False):
    corrected, details = rectify_board(image)
    if return_details:
        return corrected, details['applied'], details
    return corrected, details['applied']


def estimate_skew(image):
    """Estimate near-horizontal line tilt in image coordinates; skip ambiguous cases."""
    gray = to_gray(image)
    h, w = gray.shape
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=max(20, w // 12),
                            minLineLength=max(15, w // 10), maxLineGap=10)
    if lines is None:
        return 0.0
    angles, weights = [], []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = (np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1))) + 90) % 180 - 90
        # Ignore outer frame edges when estimating text tilt.
        if abs(angle) <= 12 and 0.04*h < (y1+y2)/2 < 0.96*h:
            angles.append(angle)
            weights.append(np.hypot(x2-x1, y2-y1))
    if len(angles) < 3:
        return 0.0
    angles, weights = np.asarray(angles), np.asarray(weights)
    order = np.argsort(angles)
    angle = float(angles[order[np.searchsorted(np.cumsum(weights[order]), weights.sum()/2)]])
    agreement = weights[np.abs(angles-angle) <= 2].sum() / weights.sum()
    return angle if agreement >= 0.65 and abs(angle) >= 0.4 else 0.0


def deskew(image):
    angle = estimate_skew(image)
    if angle == 0:
        return image.copy(), angle
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
    cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
    nw, nh = int(np.ceil(h*sine+w*cosine)), int(np.ceil(h*cosine+w*sine))
    matrix[0, 2] += (nw-w)/2
    matrix[1, 2] += (nh-h)/2
    border = tuple(int(x) for x in np.median(image.reshape(-1, 3), axis=0))
    return cv2.warpAffine(image, matrix, (nw, nh), borderValue=border), angle


def preprocess_image(image, *, perspective=False, correct_skew=False,
                     max_side=MAX_SIDE, background="auto", variant="conservative",
                     return_details=False):
    """Prepare OCR input without cropping/rotating by default.

    background: auto, light, dark. Auto assumes the majority is background.
    variant: conservative (default), enhanced, gray, binary. Output is always uint8 BGR.
    Perspective/line-based skew heuristics remain available as explicit opt-ins;
    diagram lines are not a reliable measure of handwriting orientation.
    """
    validate_image(image)
    if background not in ("auto", "light", "dark"):
        raise ValueError("background must be auto, light or dark")
    if variant not in ("conservative", "enhanced", "gray", "binary"):
        raise ValueError("variant must be conservative, enhanced, gray or binary")
    resized = resize_max(image, max_side)
    perspective_info = {"requested": bool(perspective), "applied": False}
    if perspective:
        geometry, applied, perspective_info = correct_perspective(resized, return_details=True)
    else:
        geometry, applied = resized, False
    geometry, angle = deskew(geometry) if correct_skew else (geometry, 0.0)
    if applied or angle:
        geometry = resize_max(geometry, max_side)
    gray = to_gray(geometry)
    inverted = background == "dark" or (background == "auto" and np.median(gray) < DARK_THRESHOLD)
    polarity = cv2.bitwise_not(gray) if inverted else gray
    if variant == "gray" and not return_details:
        return cv2.cvtColor(polarity, cv2.COLOR_GRAY2BGR)
    normalized, illumination = normalize_illumination(polarity)
    enhanced = enhance_contrast(normalized) if variant == "enhanced" or return_details else None
    conservative = None
    if variant == "conservative" or return_details:
        color = cv2.bitwise_not(geometry) if inverted else geometry
        gain = 245 / np.maximum(illumination.astype(np.float32), 1)
        corrected = np.clip(color.astype(np.float32) * gain[:, :, None], 0, 255).astype(np.uint8)
        conservative = cv2.addWeighted(color, 0.75, corrected, 0.25, 0)
    selected = {"enhanced": enhanced, "gray": polarity}.get(variant)
    if variant == "binary":
        selected = adaptive_binary(normalized)
    result = conservative if variant == "conservative" else cv2.cvtColor(selected, cv2.COLOR_GRAY2BGR)
    if return_details:
        return result, {"perspective_applied": applied, "perspective": perspective_info, "skew_angle": angle,
                        "inverted": bool(inverted), "variant": variant,
                        "max_side": max_side, "resized": resized,
                        "geometry": geometry, "gray": polarity,
                        "illumination": illumination, "normalized": normalized,
                        "enhanced": enhanced, "conservative": conservative,
                        "illumination_strength": 0.25 if variant == "conservative" else (0.0 if variant == "gray" else 1.0)}
    return result



def main():
    """Process one image without loading PaddleOCR."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--perspective', action='store_true')
    parser.add_argument('--deskew', action='store_true')
    parser.add_argument('--background', choices=('auto', 'light', 'dark'), default='auto')
    parser.add_argument('--variant', choices=('conservative', 'gray', 'enhanced', 'binary'), default='conservative')
    parser.add_argument('--max-side', type=int, default=MAX_SIDE)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Input and output paths must be different')
    try:
        data = np.fromfile(args.input, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
        result = preprocess_image(image, perspective=args.perspective,
                                  correct_skew=args.deskew, background=args.background,
                                  variant=args.variant, max_side=args.max_side)
        ok, encoded = cv2.imencode(args.output.suffix, result)
        if not ok:
            raise OSError('Cannot encode output image')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encoded.tofile(args.output)
        print(str(args.output))
    except (OSError, ValueError, cv2.error) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
