from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import pycaret.classification as pyc
import shap
import logging
import os
import joblib

# ── Initialize FastAPI ────────────────────────────────────────────────────

app = FastAPI(title="AutoInsight ML Microservice", version="1.0")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Logging ────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Data Models ────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    data: list[dict]  # e.g., [{"age": 25, "income": 50000, "target": 1}, ...]

class TrainRequest(BaseModel):
    data: list[dict]
    target_column: str | None = None  # If not provided, uses last column

class PredictionResponse(BaseModel):
    status: str
    best_model: str
    predictions: list
    feature_importance: dict

# ── Model Cache ────────────────────────────────────────────────────────────

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_META_PATH = os.path.join(MODEL_DIR, "model_meta.pkl")

def load_cached_model():
    """Load the cached model if it exists."""
    if os.path.exists(MODEL_META_PATH):
        try:
            meta = joblib.load(MODEL_META_PATH)
            model = pyc.load_model(os.path.join(MODEL_DIR, "best_model"))
            logger.info("Loaded cached model: %s", meta.get("model_type", "unknown"))
            return model, meta
        except Exception as e:
            logger.warning("Failed to load cached model: %s", e)
    return None, None

def save_model(model, model_type: str, feature_names: list):
    """Save the trained model and metadata to cache."""
    try:
        pyc.save_model(model, os.path.join(MODEL_DIR, "best_model"))
        joblib.dump({
            "model_type": model_type,
            "feature_names": feature_names,
            "trained_at": pd.Timestamp.now().isoformat(),
        }, MODEL_META_PATH)
        logger.info("Model cached: %s", model_type)
    except Exception as e:
        logger.warning("Failed to cache model: %s", e)

# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    model, meta = load_cached_model()
    return {
        "status": "healthy",
        "message": "ML Service is running",
        "model_cached": model is not None,
        "model_type": meta.get("model_type") if meta else None,
    }

@app.post("/train", response_model=dict)
def train_model(request: TrainRequest):
    """
    Train a new model on the provided data.
    This endpoint caches the best model for future predictions.
    """
    try:
        df = pd.DataFrame(request.data)
        target = request.target_column or df.columns[-1]

        if df.empty or len(df.columns) < 2:
            raise HTTPException(status_code=400, detail="Data must have at least 2 columns and 1 row")

        logger.info("Training model on %d rows, %d columns", len(df), len(df.columns))

        # PyCaret setup
        setup = pyc.setup(
            data=df,
            target=target,
            silent=True,
            html=False,
            verbose=False,
        )

        # AutoML: compare all models and select the best
        best_model = pyc.compare_models(n_select=1, verbose=False)

        model_type = str(type(best_model).__name__)
        feature_names = [c for c in df.columns if c != target]

        # Cache the trained model
        save_model(best_model, model_type, feature_names)

        return {
            "status": "success",
            "best_model": model_type,
            "features": feature_names,
            "rows_trained": len(df),
            "message": "Model trained and cached successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Training error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")

@app.post("/predict-and-explain", response_model=PredictionResponse)
def predict_and_explain(request: PredictionRequest):
    """
    Make predictions and generate SHAP feature importance explanations.
    Uses cached model if available, otherwise trains on the fly.
    """
    try:
        df = pd.DataFrame(request.data)

        if df.empty:
            raise HTTPException(status_code=400, detail="Data cannot be empty")

        logger.info("Predicting on %d rows", len(df))

        # Try to load cached model
        model, meta = load_cached_model()

        if model is None:
            # Train on the fly using last column as target
            logger.info("No cached model found — training on the fly")
            target = df.columns[-1]
            setup = pyc.setup(data=df, target=target, silent=True, html=False, verbose=False)
            model = pyc.compare_models(n_select=1, verbose=False)
            model_type = str(type(model).__name__)
            save_model(model, model_type, [c for c in df.columns if c != target])
        else:
            model_type = meta.get("model_type", "unknown")
            logger.info("Using cached model: %s", model_type)

        # Make predictions
        predictions = pyc.predict_model(model, data=df)

        # Generate SHAP feature importance
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(df)
            # Calculate mean absolute SHAP values
            if isinstance(shap_values, list):
                # For multi-class: use the first class
                mean_shap = pd.DataFrame(shap_values[0]).abs().mean().to_dict()
            else:
                mean_shap = pd.DataFrame(shap_values).abs().mean().to_dict()
        except Exception as shap_err:
            logger.warning("SHAP explanation failed: %s", shap_err)
            mean_shap = {}

        return {
            "status": "success",
            "best_model": model_type,
            "predictions": predictions["prediction_label"].tolist(),
            "feature_importance": mean_shap,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Prediction error: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.get("/model-info")
def model_info():
    """Get information about the currently cached model."""
    model, meta = load_cached_model()
    if model is None:
        return {"status": "no_model", "message": "No model trained yet"}
    return {
        "status": "cached",
        "model_type": meta.get("model_type"),
        "feature_names": meta.get("feature_names"),
        "trained_at": meta.get("trained_at"),
    }
