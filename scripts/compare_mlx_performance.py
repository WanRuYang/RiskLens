import json
from pathlib import Path
import pandas as pd
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OCR_ROOT = PROJECT_ROOT / "outputs" / "ocr_benchmark"
GROUNDED_ROOT = PROJECT_ROOT / "outputs" / "stage2_grounded_benchmark"

def get_latest_dir(root_dir, include_pattern="*", exclude_pattern=None):
    dirs = [d for d in root_dir.glob(include_pattern) if d.is_dir()]
    if exclude_pattern:
        dirs = [d for d in dirs if exclude_pattern not in d.name]
    if not dirs:
        return None
    return max(dirs, key=lambda d: d.name)

def compare_ocr():
    print("Comparing OCR Benchmarks...")
    transformers_dir = get_latest_dir(OCR_ROOT, "2026*", exclude_pattern="_mlx")
    mlx_dir = get_latest_dir(OCR_ROOT, "*_mlx")
    
    if not transformers_dir or not mlx_dir:
        print(f"Missing OCR data. T: {transformers_dir}, M: {mlx_dir}")
        return None
        
    print(f"T-dir: {transformers_dir.name}, M-dir: {mlx_dir.name}")
    t_summary = json.loads((transformers_dir / "ocr_summary.json").read_text())
    m_summary = json.loads((mlx_dir / "ocr_summary_mlx.json").read_text())
    
    t_df = pd.DataFrame(t_summary)
    m_df = pd.DataFrame(m_summary)
    
    # Merge on case_id
    comparison = pd.merge(t_df, m_df, on="case_id", suffixes=("_transformers", "_mlx"))
    
    report = {
        "transformers_mean_recall": t_df["substring_recall"].mean(),
        "mlx_mean_recall": m_df["substring_recall"].mean(),
        "mlx_recall_delta": m_df["substring_recall"].mean() - t_df["substring_recall"].mean(),
    }
    
    return report

def compare_grounded():
    print("Comparing Grounded Benchmarks...")
    transformers_dir = get_latest_dir(GROUNDED_ROOT, "gemma_*")
    mlx_dir = get_latest_dir(GROUNDED_ROOT, "mlx_*")
    
    if not transformers_dir or not mlx_dir:
        print("Missing Grounded data for comparison.")
        return None
        
    t_summary = json.loads((transformers_dir / "stage2_grounded_summary.json").read_text())
    m_summary = json.loads((mlx_dir / "stage2_grounded_summary_mlx.json").read_text())
    
    report = {
        "transformers_cat_acc": t_summary["mean_category_correct"],
        "mlx_cat_acc": m_summary["mean_category_correct"],
        "transformers_mat_acc": t_summary["mean_material_correct"],
        "mlx_mat_acc": m_summary["mean_material_correct"],
        "transformers_priority_acc": t_summary["mean_information_priority_correct"],
        "mlx_priority_acc": m_summary["mean_priority_correct"],
        "transformers_duration": t_summary.get("total_duration_sec", 0), # Transformers script might not have this
        "mlx_duration": m_summary["total_duration_sec"],
    }
    
    return report

def main():
    ocr_report = compare_ocr()
    grounded_report = compare_grounded()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = PROJECT_ROOT / "outputs" / f"comparison_report_{timestamp}.md"
    
    lines = ["# MLX vs. Transformers Performance Comparison", ""]
    
    if ocr_report:
        lines.extend([
            "## OCR Comparison",
            f"- **Transformers Mean Recall**: {ocr_report['transformers_mean_recall']:.4f}",
            f"- **MLX Mean Recall**: {ocr_report['mlx_mean_recall']:.4f}",
            f"- **Delta**: {ocr_report['mlx_recall_delta']:+.4f}",
            ""
        ])
        
    if grounded_report:
        lines.extend([
            "## Grounded Pipeline Comparison",
            f"- **Category Accuracy**: Transformers {grounded_report['transformers_cat_acc']:.2%}, MLX {grounded_report['mlx_cat_acc']:.2%}",
            f"- **Material Accuracy**: Transformers {grounded_report['transformers_mat_acc']:.2%}, MLX {grounded_report['mlx_mat_acc']:.2%}",
            f"- **Priority Accuracy**: Transformers {grounded_report['transformers_priority_acc']:.2%}, MLX {grounded_report['mlx_priority_acc']:.2%}",
            f"- **Total Duration**: MLX {grounded_report['mlx_duration']:.2f}s",
            ""
        ])
        
    report_file.write_text("\n".join(lines))
    print(f"Comparison report saved to {report_file}")

if __name__ == "__main__":
    main()
