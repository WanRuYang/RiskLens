from PIL import Image
from pathlib import Path
from vision_utils import calculate_dynamic_grid

def test_adaptive_logic():
    print("=== Testing Adaptive Tiling Logic (v24.0) ===")
    
    test_cases = [
        ("Square", 1000, 1000, (2, 2)),
        ("Wide (Wrap)", 3000, 500, (4, 1)),
        ("Tall (Bottle)", 500, 3000, (1, 4)),
        ("Horizontal Rect", 2000, 1000, (2, 2)), # Standard
        ("Wide 16:9", 1920, 1080, (2, 2)),
        ("Wide 3:1", 3000, 1000, (4, 1)),
    ]
    
    for name, w, h, expected in test_cases:
        grid = calculate_dynamic_grid(w, h)
        status = "PASS" if grid == expected else f"FAIL (Got {grid})"
        print(f"[{status}] {name:15} | {w}x{h} (Aspect {w/h:.2f}) -> {grid}")

if __name__ == "__main__":
    test_adaptive_logic()
