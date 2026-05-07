from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

def enhance_image(img: Image.Image) -> Image.Image:
    """
    Applies contrast enhancement and sharpening to improve OCR character recognition.
    """
    # 1. Increase contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # 2. Apply sharpening filter
    img = img.filter(ImageFilter.SHARPEN)
    
    return img

def binarize_image(img: Image.Image) -> Image.Image:
    """
    Converts an image to high-contrast black and white to sharpen text edges.
    """
    return img.convert("L").point(lambda x: 0 if x < 128 else 255, '1')

def get_tiles(image_path: str, grid=(2, 2), overlap=0.3, enhance=False, binarize=False) -> list[Image.Image]:
    """
    Splits an image into overlapping tiles with optional enhancement and binarization.
    """
    img = Image.open(image_path).convert("RGB")
    
    if enhance:
        img = enhance_image(img)
        
    width, height = img.size
    cols, rows = grid
    
    tile_w = width / (cols - (cols - 1) * overlap)
    tile_h = height / (rows - (rows - 1) * overlap)
    
    step_x = tile_w * (1 - overlap)
    step_y = tile_h * (1 - overlap)
    
    tiles = []
    # Original color view
    tiles.append(img)
    
    # Optional original binarized view
    if binarize:
        tiles.append(binarize_image(img).convert("RGB"))
    
    for r in range(rows):
        for c in range(cols):
            left = int(c * step_x)
            top = int(r * step_y)
            right = min(int(left + tile_w), width)
            bottom = min(int(top + tile_h), height)
            
            if (right - left) > 50 and (bottom - top) > 50:
                crop = img.crop((left, top, right, bottom))
                tiles.append(crop)
                if binarize:
                    tiles.append(binarize_image(crop).convert("RGB"))
                
    return tiles

def save_tiles(tiles: list[Image.Image], output_dir: Path, prefix: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, tile in enumerate(tiles):
        path = output_dir / f"{prefix}_tile_{i}.png"
        tile.save(path)
        paths.append(str(path))
    return paths
