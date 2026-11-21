from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError:
    Image = None

try:
    import numpy as np
except ImportError:
    np = None


def analyze_road_image(image_path):
    """Analyze road damage using an explainable image heuristic.

    This runs without a trained model and can later be replaced by YOLO
    detection while preserving the same API contract.
    """
    path = Path(image_path)
    if not path.exists() or Image is None or np is None:
        return _fallback("Image analysis unavailable.")

    try:
        image = Image.open(path).convert("RGB")
        image.thumbnail((800, 800))
        gray = image.convert("L")

        # Edge density is useful as a rough proxy for cracks and broken surfaces.
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_array = np.asarray(edges, dtype=np.float32)
        edge_density = float(edge_array.mean()) / 255.0

        rgb = np.asarray(image, dtype=np.float32)
        luminance = rgb.mean(axis=2)
        darkness_ratio = float((luminance < 75).mean())
        contrast = float(luminance.std()) / 255.0

        roughness = min(1.0, (edge_density * 2.2) + (contrast * 0.75))
        size_signal = min(1.0, darkness_ratio * 3.0)
        damage_score = (roughness * 0.65) + (size_signal * 0.35)

        if damage_score >= 0.68:
            severity = "Critical"
            damage_type = "Severe pothole or surface failure"
            priority = 95
        elif damage_score >= 0.48:
            severity = "High"
            damage_type = "Large crack or pothole"
            priority = 78
        elif damage_score >= 0.28:
            severity = "Medium"
            damage_type = "Surface cracking"
            priority = 55
        else:
            severity = "Low"
            damage_type = "Minor surface wear"
            priority = 30

        confidence = min(0.99, max(0.55, 0.55 + damage_score * 0.4))
        notes = (
            f"Edge density {edge_density:.2f}; contrast {contrast:.2f}; "
            f"dark-area ratio {darkness_ratio:.2f}. "
            "AI estimate - field verification recommended."
        )
        return {
            "damage_type": damage_type,
            "severity": severity,
            "priority_score": priority,
            "confidence": round(confidence, 3),
            "notes": notes,
        }
    except Exception as exc:
        return _fallback(f"Analysis failed: {exc}")


def _fallback(note):
    return {
        "damage_type": "Not analyzed",
        "severity": "Low",
        "priority_score": 20,
        "confidence": 0.0,
        "notes": note,
    }
