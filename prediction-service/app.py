"""
StarDist Prediction Microservice.

A lightweight Flask API that:
  - Lists available StarDist models (built-in + custom from /models directory)
  - Runs StarDist prediction on an uploaded image and returns polygon contours

Expects the /models directory to be mounted from the host.
"""

import os
import io
import json
import logging
import numpy as np
from flask import Flask, request, jsonify
from PIL import Image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

MODELS_DIR = os.environ.get("MODELS_DIR", "/models")

# Built-in pretrained models from the stardist package
BUILTIN_MODELS = [
    "2D_versatile_fluo",
    "2D_versatile_he",
    "2D_demo",
]

# Cache loaded models to avoid reloading on every request
_model_cache = {}


def get_model(model_name):
    """Load and cache a StarDist model."""
    if model_name in _model_cache:
        return _model_cache[model_name]

    from stardist.models import StarDist2D

    if model_name in BUILTIN_MODELS:
        logger.info(f"Loading built-in model: {model_name}")
        model = StarDist2D.from_pretrained(model_name)
    else:
        # Custom model from /models directory
        model_path = os.path.join(MODELS_DIR, model_name)
        if not os.path.isdir(model_path):
            raise FileNotFoundError(f"Model directory not found: {model_path}")
        logger.info(f"Loading custom model from: {model_path}")
        model = StarDist2D(None, name=model_name, basedir=MODELS_DIR)

    _model_cache[model_name] = model
    return model


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/models", methods=["GET"])
def list_models():
    """
    List all available models: built-in + custom from /models directory.
    Returns JSON: { models: [ {value, label, type} ] }
    """
    models = []

    # Built-in models
    for name in BUILTIN_MODELS:
        models.append({
            "value": name,
            "label": f"{name} (Built-in)",
            "type": "builtin",
        })

    # Custom models from mounted directory
    if os.path.isdir(MODELS_DIR):
        for entry in sorted(os.listdir(MODELS_DIR)):
            entry_path = os.path.join(MODELS_DIR, entry)
            if os.path.isdir(entry_path):
                # Check if it looks like a stardist model (has config.json or thresholds.json)
                has_config = os.path.exists(os.path.join(entry_path, "config.json"))
                has_thresholds = os.path.exists(os.path.join(entry_path, "thresholds.json"))
                has_weights = any(
                    f.endswith((".h5", ".keras", ".pb"))
                    for f in os.listdir(entry_path)
                )
                if has_config or has_thresholds or has_weights:
                    models.append({
                        "value": entry,
                        "label": f"{entry} (Custom)",
                        "type": "custom",
                    })

    return jsonify({"models": models})


@app.route("/predict", methods=["POST"])
def predict():
    """
    Run StarDist prediction on an uploaded image.

    Expects multipart/form-data:
      - image: the image file (PNG/JPEG/TIFF)
      - model: model name string

    Returns JSON:
      {
        "polygons": [
          { "points": [[x, y], ...], "probability": float },
          ...
        ],
        "count": int
      }
    """
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    model_name = request.form.get("model", "2D_versatile_fluo")

    try:
        model = get_model(model_name)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error loading model {model_name}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to load model: {str(e)}"}), 500

    try:
        # Read image
        image_file = request.files["image"]
        img = Image.open(io.BytesIO(image_file.read()))

        # Convert to numpy array
        img_np = np.array(img)

        # Handle different image shapes
        if img_np.ndim == 3:
            # If RGB or RGBA, convert to grayscale for fluorescence models
            if img_np.shape[2] == 4:
                # RGBA -> RGB -> Gray
                img_np = img_np[:, :, :3]
            if model_name in ["2D_versatile_he"]:
                # H&E model expects RGB
                pass
            else:
                # Fluorescence models expect single channel
                if img_np.shape[2] == 3:
                    img_np = np.mean(img_np, axis=2)

        # Normalize
        from csbdeep.utils import normalize
        img_normalized = normalize(img_np, 1, 99.8, axis=(0, 1) if img_np.ndim == 2 else (0, 1, 2))

        # Predict
        labels, details = model.predict_instances(img_normalized)

        # Extract polygon contours from details
        polygons = []
        coord = details.get("coord", None)
        prob = details.get("prob", None)
        points_list = details.get("points", None)

        if coord is not None:
            # coord has shape (n_objects, 2, n_rays) — row/col per ray
            for i in range(coord.shape[0]):
                # coord[i] is (2, n_rays) -> rows, cols
                rows = coord[i][0]  # y coordinates  
                cols = coord[i][1]  # x coordinates
                # Convert to [[x, y], ...] for frontend
                pts = [[float(cols[j]), float(rows[j])] for j in range(len(rows))]
                p = float(prob[i]) if prob is not None else 1.0
                polygons.append({
                    "points": pts,
                    "probability": p,
                })

        return jsonify({
            "polygons": polygons,
            "count": len(polygons),
        })

    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500


if __name__ == "__main__":
    # Pre-load default model on startup for faster first request
    logger.info("StarDist service starting...")
    app.run(host="0.0.0.0", port=5000, debug=False)
