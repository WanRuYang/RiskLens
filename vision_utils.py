from PIL import Image
from pathlib import Path

def get_tiles(image_path: str, grid=(2, 2), overlap=0.1) -> list[Image.Image]:
    """
    Splits an image into overlapping tiles to preserve high-resolution detail for OCR.
    """
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    cols, rows = grid
    
    tile_w = width / (cols - (cols - 1) * overlap)
    tile_h = height / (rows - (rows - 1) * overlap)
    
    # Calculate step size
    step_x = tile_w * (1 - overlap)
    step_y = tile_h * (1 - overlap)
    
    tiles = []
    # Always include the original full image as the first context tile
    tiles.append(img)
    
    for r in range(rows):
        for c in range(cols):
            left = int(c * step_x)
            top = int(r * step_y)
            right = min(int(left + tile_w), width)
            bottom = min(int(top + tile_h), height)
            
            # Ensure we don't have tiny slivers
            if (right - left) > 50 and (bottom - top) > 50:
                tiles.append(img.crop((left, top, right, bottom)))
                
    return tiles

def save_tiles(tiles: list[Image.Image], output_dir: Path, prefix: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, tile in enumerate(tiles):
        path = output_dir / f"{prefix}_tile_{i}.png"
        tile.save(path)
        paths.append(str(path))
    return paths
