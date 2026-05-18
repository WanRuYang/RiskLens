from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class CropCandidate:
    path: str
    bbox: tuple[int, int, int, int]
    score: float
    reason: str


def _merge_boxes(boxes: list[tuple[int, int, int, int]], *, overlap_margin: int) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: (item[1], item[0])):
        x1, y1, x2, y2 = box
        absorbed = False
        for idx, current in enumerate(merged):
            cx1, cy1, cx2, cy2 = current
            if x1 <= cx2 + overlap_margin and x2 >= cx1 - overlap_margin and y1 <= cy2 + overlap_margin and y2 >= cy1 - overlap_margin:
                merged[idx] = (min(cx1, x1), min(cy1, y1), max(cx2, x2), max(cy2, y2))
                absorbed = True
                break
        if not absorbed:
            merged.append(box)
    return merged


def _expand_box(
    box: tuple[int, int, int, int],
    *,
    width: int,
    height: int,
    pad_ratio: float = 0.06,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    pad_x = int((x2 - x1) * pad_ratio) + 8
    pad_y = int((y2 - y1) * pad_ratio) + 8
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(width, x2 + pad_x),
        min(height, y2 + pad_y),
    )


def _panel_score(binary: np.ndarray, box: tuple[int, int, int, int], *, image_area: int) -> float:
    x1, y1, x2, y2 = box
    crop = binary[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    box_area = max((x2 - x1) * (y2 - y1), 1)
    area_ratio = box_area / max(image_area, 1)
    text_density = float(np.count_nonzero(crop)) / box_area
    aspect = (x2 - x1) / max(y2 - y1, 1)
    aspect_bonus = 0.15 if 0.45 <= aspect <= 4.5 else 0.0
    size_bonus = min(area_ratio, 0.35)
    return round(text_density * 2.0 + size_bonus + aspect_bonus, 4)


def find_text_panel_crops(
    image_path: str,
    output_dir: str | Path,
    *,
    max_crops: int = 3,
    min_area_ratio: float = 0.025,
    max_area_ratio: float = 0.75,
) -> list[CropCandidate]:
    """Find likely dense text panels for OCR without running a model.

    This is intentionally conservative: it returns only a few large text-rich
    regions so the pipeline gets better crops without turning into a slow
    multi-crop vision sweep.
    """
    source = Path(image_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(source) as pil_img:
            pil_img = ImageOps.exif_transpose(pil_img).convert("RGB")
            width, height = pil_img.size
            image_area = width * height
            rgb = np.array(pil_img)
    except Exception as exc:
        print(f"CV panel cropper skipped {source.name}: {exc}")
        return []

    if width < 180 or height < 180:
        return []

    scale = min(1.0, 1200 / max(width, height))
    if scale < 1.0:
        small = cv2.resize(rgb, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    else:
        small = rgb
    small_h, small_w = small.shape[:2]

    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(gray, 5, 45, 45)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )

    # Connect letters into lines and nearby lines into panel-like blocks.
    line_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(12, small_w // 45), 3))
    block_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(18, small_w // 32), max(10, small_h // 80)))
    connected = cv2.dilate(binary, line_kernel, iterations=1)
    connected = cv2.dilate(connected, block_kernel, iterations=1)
    connected = cv2.morphologyEx(connected, cv2.MORPH_CLOSE, block_kernel)

    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes_small: list[tuple[int, int, int, int]] = []
    small_area = small_w * small_h
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < 60 or h < 28:
            continue
        ratio = (w * h) / max(small_area, 1)
        if ratio < min_area_ratio or ratio > max_area_ratio:
            continue
        boxes_small.append((x, y, x + w, y + h))

    boxes_small = _merge_boxes(boxes_small, overlap_margin=max(8, int(18 * scale)))
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for box in boxes_small:
        x1, y1, x2, y2 = box
        full_box = (
            int(x1 / scale),
            int(y1 / scale),
            int(x2 / scale),
            int(y2 / scale),
        )
        full_box = _expand_box(full_box, width=width, height=height)
        score = _panel_score(binary, box, image_area=small_area)
        if score > 0.08:
            candidates.append((score, full_box))

    # Prefer larger/dense panels, but avoid near-duplicates.
    selected: list[tuple[float, tuple[int, int, int, int]]] = []
    for score, box in sorted(candidates, key=lambda item: item[0], reverse=True):
        x1, y1, x2, y2 = box
        too_similar = False
        for _, existing in selected:
            ex1, ey1, ex2, ey2 = existing
            inter_w = max(0, min(x2, ex2) - max(x1, ex1))
            inter_h = max(0, min(y2, ey2) - max(y1, ey1))
            inter = inter_w * inter_h
            area = max((x2 - x1) * (y2 - y1), 1)
            existing_area = max((ex2 - ex1) * (ey2 - ey1), 1)
            if inter / min(area, existing_area) > 0.65:
                too_similar = True
                break
        if not too_similar:
            selected.append((score, box))
        if len(selected) >= max_crops:
            break

    saved: list[CropCandidate] = []
    stem = source.stem.replace(" ", "_")
    for idx, (score, box) in enumerate(selected):
        x1, y1, x2, y2 = box
        crop = pil_img.crop((x1, y1, x2, y2))
        crop_path = out_dir / f"{stem}_panel_{idx}.png"
        crop.save(crop_path, format="PNG")
        saved.append(CropCandidate(path=str(crop_path), bbox=box, score=score, reason="cv_text_panel_density"))
    return saved


def crop_candidates_as_dicts(candidates: list[CropCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "path": candidate.path,
            "bbox": list(candidate.bbox),
            "score": candidate.score,
            "reason": candidate.reason,
        }
        for candidate in candidates
    ]
