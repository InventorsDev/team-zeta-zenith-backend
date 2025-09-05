# app/api/ml_sprint3_endpoints.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Tuple
from functools import lru_cache
import time

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score

import torch
from transformers import AutoTokenizer, AutoModel

# Forecasting (statsmodels)
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from statsmodels.tsa.api import Holt

# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
router = APIRouter()

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class SimilarityRequest(BaseModel):
    text: str = Field(..., description="Query text to compare")
    corpus: Optional[List[str]] = Field(None, description="Optional corpus to search; if omitted, returns similarity of query to itself")
    top_k: int = Field(5, ge=1, le=100, description="How many closest items to return")
    use_transformer: bool = Field(False, description="Use DistilBERT embeddings instead of TF-IDF")

class SimilarityResponseItem(BaseModel):
    index: int
    text: str
    score: float

class SimilarityResponse(BaseModel):
    query: str
    results: List[SimilarityResponseItem]
    embedding_type: str
    corpus_size: int

class ClusteringRequest(BaseModel):
    texts: List[str] = Field(..., min_items=2, description="List of ticket texts to cluster")
    n_clusters: Optional[int] = Field(None, ge=2, le=100)
    method: str = Field("auto", description="auto | kmeans | agglomerative")
    use_transformer: bool = Field(False, description="Use DistilBERT embeddings instead of TF-IDF")

class ClusterItem(BaseModel):
    index: int
    text: str
    cluster: int

class ClusteringResponse(BaseModel):
    n_clusters: int
    method: str
    embedding_type: str
    clusters: List[ClusterItem]
    silhouette: Optional[float] = None

class DuplicatesRequest(BaseModel):
    texts: List[str] = Field(..., min_items=2)
    threshold: float = Field(0.85, ge=0.0, le=1.0, description="Cosine similarity threshold (0-1)")
    use_transformer: bool = Field(False)

class DuplicatePair(BaseModel):
    i: int
    j: int
    text_i: str
    text_j: str
    score: float

class DuplicatesResponse(BaseModel):
    threshold: float
    embedding_type: str
    duplicates: List[DuplicatePair]

class RecommendationsRequest(BaseModel):
    text: str
    corpus: List[str] = Field(..., min_items=1)
    top_k: int = Field(5, ge=1, le=100)
    use_transformer: bool = Field(False)

class RecommendationsResponse(BaseModel):
    query: str
    embedding_type: str
    recommendations: List[SimilarityResponseItem]

class ForecastVolumeRequest(BaseModel):
    counts: List[float] = Field(..., min_items=3, description="Historical counts by equal time step (daily/weekly)")
    periods: int = Field(7, ge=1, le=365, description="Forecast horizon")
    seasonal_periods: Optional[int] = Field(None, ge=2, description="Seasonal cycle length (e.g., 7 for weekly seasonality on daily data)")
    trend: Optional[str] = Field("add", description="'add' or 'mul' trend for Holt-Winters if seasonal")
    seasonal: Optional[str] = Field("add", description="'add' or 'mul' seasonality for Holt-Winters if seasonal")

    @validator("trend")
    def _valid_trend(cls, v):
        if v not in (None, "add", "mul"):
            raise ValueError("trend must be one of: None, 'add', 'mul'")
        return v

    @validator("seasonal")
    def _valid_seasonal(cls, v):
        if v not in (None, "add", "mul"):
            raise ValueError("seasonal must be one of: None, 'add', 'mul'")
        return v

class ForecastVolumeResponse(BaseModel):
    model: str
    fitted: List[float]
    forecast: List[float]
    conf_int: Optional[List[Tuple[float, float]]] = None
    seasonal_periods: Optional[int] = None

class ForecastCategoryRequest(BaseModel):
    series_by_category: Dict[str, List[float]] = Field(..., description="Dict of category -> historical counts")
    periods: int = Field(7, ge=1, le=365)
    seasonal_periods: Optional[int] = Field(None, ge=2)
    trend: Optional[str] = Field("add")
    seasonal: Optional[str] = Field("add")



class ForecastCategoryResponseItem(BaseModel):
    category: str
    model: str
    forecast: List[float]
    seasonal_periods: Optional[int] = None

class ForecastCategoryResponse(BaseModel):
    results: List[ForecastCategoryResponseItem]

class ForecastScenarioRequest(BaseModel):
    counts: List[float] = Field(..., min_items=3)
    periods: int = Field(7, ge=1, le=365)
    scenarios: Dict[str, float] = Field(..., description="Scenario name -> multiplicative factor, e.g. {'marketing_push': 1.2}")
    seasonal_periods: Optional[int] = Field(None, ge=2)
    trend: Optional[str] = Field("add")
    seasonal: Optional[str] = Field("add")

class ForecastScenarioResponse(BaseModel):
    base_model: str
    base_forecast: List[float]
    scenarios: Dict[str, List[float]]
    seasonal_periods: Optional[int] = None


# Request model for forecasting
class ForecastRequest(BaseModel):
    tickets: List[Dict[str, Any]]

class OptimizeBenchmarkRequest(BaseModel):
    texts: List[str] = Field(..., min_items=10)
    batch_size: int = Field(32, ge=1, le=1024)
    repetitions: int = Field(3, ge=1, le=20)
    use_transformer: bool = Field(False)

class OptimizeBenchmarkResponse(BaseModel):
    embedding_type: str
    avg_embed_time_ms: float
    avg_similarity_time_ms: float
    tokens_per_sec_est: Optional[float] = None
    notes: Optional[str] = None

# -----------------------------------------------------------------------------
# Embedding Utilities
# -----------------------------------------------------------------------------
TRANSFORMER_MODEL_NAME = "distilbert-base-uncased"

@lru_cache(maxsize=1)
def _load_transformer() -> Tuple[AutoTokenizer, AutoModel, torch.device]:
    """
    Load DistilBERT model/tokenizer once; prefer CPU for portability.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(TRANSFORMER_MODEL_NAME)
    model = AutoModel.from_pretrained(TRANSFORMER_MODEL_NAME)
    model.to(device)
    model.eval()
    return tokenizer, model, device

def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Mean-pool token embeddings with attention mask.
    """
    mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask_expanded, dim=1)
    counts = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
    return summed / counts

def embed_transformer(texts: List[str], batch_size: int = 16) -> np.ndarray:
    """
    Compute DistilBERT sentence embeddings (mean pooled).
    """
    tokenizer, model, device = _load_transformer()
    all_embs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            encoded = tokenizer(
                chunk,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt"
            ).to(device)
            outputs = model(**encoded)
            pooled = _mean_pool(outputs.last_hidden_state, encoded["attention_mask"])
            all_embs.append(pooled.cpu().numpy())
    return np.vstack(all_embs)

def embed_tfidf(texts: List[str]) -> Tuple[np.ndarray, TfidfVectorizer]:
    """
    Fit TF-IDF on texts and return dense vectors.
    """
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=5000)
    X = vectorizer.fit_transform(texts)
    return X.toarray(), vectorizer

def embed_with_existing_tfidf(texts: List[str], vectorizer: TfidfVectorizer) -> np.ndarray:
    """
    Transform with existing TF-IDF vectorizer.
    """
    X = vectorizer.transform(texts)
    return X.toarray()

# -----------------------------------------------------------------------------
# Similarity + Clustering Helpers
# -----------------------------------------------------------------------------
def top_k_similar(query_vec: np.ndarray, corpus_mat: np.ndarray, k: int) -> List[Tuple[int, float]]:
    sims = cosine_similarity(query_vec.reshape(1, -1), corpus_mat).ravel()
    top_idx = np.argsort(-sims)[:k]
    return [(int(i), float(sims[i])) for i in top_idx]

def auto_k_silhouette(emb: np.ndarray, k_min: int = 2, k_max: int = 10) -> Tuple[int, float]:
    """
    Pick k via silhouette on KMeans.
    """
    best_k = k_min
    best_score = -1.0
    for k in range(k_min, min(k_max, len(emb) - 1) + 1):
        try:
            km = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = km.fit_predict(emb)
            score = silhouette_score(emb, labels)
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            continue
    return best_k, best_score

# -----------------------------------------------------------------------------
# Forecasting Helpers (statsmodels)
# -----------------------------------------------------------------------------
def _fit_forecast_series(
    y: List[float],
    periods: int,
    seasonal_periods: Optional[int] = None,
    trend: Optional[str] = "add",
    seasonal: Optional[str] = "add"
) -> Tuple[str, np.ndarray, np.ndarray]:
    """
    Fit an appropriate smoothing model and forecast.
    Returns: (model_name, fitted_values, forecast_values)
    """
    y_arr = np.asarray(y, dtype=float)
    if np.any(~np.isfinite(y_arr)):
        raise ValueError("Series contains non-finite values.")

    model_name = ""
    fitted_vals = None
    forecast_vals = None

    if seasonal_periods and seasonal_periods >= 2 and len(y_arr) >= 2 * seasonal_periods:
        # Holt-Winters (with seasonality)
        try:
            hw = ExponentialSmoothing(
                y_arr,
                trend=trend,
                seasonal=seasonal,
                seasonal_periods=seasonal_periods,
                initialization_method="estimated"
            ).fit(optimized=True)
            fitted_vals = hw.fittedvalues
            forecast_vals = hw.forecast(periods)
            model_name = f"ExponentialSmoothing(trend={trend}, seasonal={seasonal}, m={seasonal_periods})"
            return model_name, np.asarray(fitted_vals, dtype=float), np.asarray(forecast_vals, dtype=float)
        except Exception:
            # Fall through to simpler models if Holt-Winters fails
            pass

    # If no seasonality or not enough data for seasonal model
    if len(y_arr) >= 3:
        try:
            ht = Holt(y_arr, initialization_method="estimated").fit(optimized=True)
            fitted_vals = ht.fittedvalues
            forecast_vals = ht.forecast(periods)
            model_name = "Holt"
            return model_name, np.asarray(fitted_vals, dtype=float), np.asarray(forecast_vals, dtype=float)
        except Exception:
            pass

    # Fallback to Simple Exponential Smoothing
    ses = SimpleExpSmoothing(y_arr, initialization_method="estimated").fit(optimized=True)
    fitted_vals = ses.fittedvalues
    forecast_vals = ses.forecast(periods)
    model_name = "SimpleExpSmoothing"
    return model_name, np.asarray(fitted_vals, dtype=float), np.asarray(forecast_vals, dtype=float)

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@router.post("/similarity", response_model=SimilarityResponse)
def similarity(req: SimilarityRequest):
    try:
        corpus = req.corpus or [req.text]
        if req.use_transformer:
            emb_type = "transformer"
            all_texts = [req.text] + corpus
            embs = embed_transformer(all_texts)
            query_vec = embs[0]
            corpus_mat = embs[1:]
        else:
            emb_type = "tfidf"
            # Fit on corpus for lexical similarity
            tfidf_mat, vec = embed_tfidf(corpus)
            query_vec = embed_with_existing_tfidf([req.text], vec)[0]
            corpus_mat = tfidf_mat

        k = min(req.top_k, len(corpus))
        top = top_k_similar(query_vec, corpus_mat, k)

        results = [
            SimilarityResponseItem(index=i, text=corpus[i], score=round(score, 6))
            for i, score in top
        ]
        return SimilarityResponse(
            query=req.text,
            results=results,
            embedding_type=emb_type,
            corpus_size=len(corpus)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Similarity error: {e}")

@router.post("/clustering", response_model=ClusteringResponse)
def clustering(req: ClusteringRequest):
    try:
        texts = req.texts
        if req.use_transformer:
            emb_type = "transformer"
            emb = embed_transformer(texts)
        else:
            emb_type = "tfidf"
            emb, _ = embed_tfidf(texts)

        method = req.method.lower()
        silhouette_val = None

        # Auto choose k (KMeans) via silhouette if not provided
        if req.n_clusters is None:
            k, silhouette_val = auto_k_silhouette(emb, 2, min(10, max(2, len(texts) - 1)))
        else:
            k = int(req.n_clusters)

        if method == "auto" or method == "kmeans":
            model = KMeans(n_clusters=k, n_init="auto", random_state=42)
            labels = model.fit_predict(emb)
            method_used = "kmeans"
            if silhouette_val is None and len(set(labels)) > 1:
                silhouette_val = silhouette_score(emb, labels)
        elif method == "agglomerative":
            model = AgglomerativeClustering(n_clusters=k, linkage="ward")
            labels = model.fit_predict(emb)
            method_used = "agglomerative"
            if len(set(labels)) > 1:
                silhouette_val = silhouette_score(emb, labels)
        else:
            raise ValueError("method must be one of: auto | kmeans | agglomerative")

        clusters = [
            ClusterItem(index=i, text=texts[i], cluster=int(labels[i]))
            for i in range(len(texts))
        ]
        return ClusteringResponse(
            n_clusters=int(k),
            method=method_used,
            embedding_type=emb_type,
            clusters=clusters,
            silhouette=None if silhouette_val is None else float(silhouette_val)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Clustering error: {e}")

@router.post("/duplicates", response_model=DuplicatesResponse)
def duplicates(req: DuplicatesRequest):
    try:
        texts = req.texts
        if req.use_transformer:
            emb_type = "transformer"
            emb = embed_transformer(texts)
        else:
            emb_type = "tfidf"
            emb, _ = embed_tfidf(texts)

        sim_mat = cosine_similarity(emb)
        dup_pairs: List[DuplicatePair] = []
        n = len(texts)
        for i in range(n):
            for j in range(i + 1, n):
                score = float(sim_mat[i, j])
                if score >= req.threshold:
                    dup_pairs.append(DuplicatePair(
                        i=i, j=j, text_i=texts[i], text_j=texts[j], score=round(score, 6)
                    ))

        # Sort by score descending
        dup_pairs.sort(key=lambda x: x.score, reverse=True)

        return DuplicatesResponse(
            threshold=req.threshold,
            embedding_type=emb_type,
            duplicates=dup_pairs
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Duplicates error: {e}")

@router.post("/recommendations", response_model=RecommendationsResponse)
def recommendations(req: RecommendationsRequest):
    try:
        corpus = req.corpus
        if req.use_transformer:
            emb_type = "transformer"
            all_texts = [req.text] + corpus
            embs = embed_transformer(all_texts)
            query_vec = embs[0]
            corpus_mat = embs[1:]
        else:
            emb_type = "tfidf"
            tfidf_mat, vec = embed_tfidf(corpus)
            query_vec = embed_with_existing_tfidf([req.text], vec)[0]
            corpus_mat = tfidf_mat

        k = min(req.top_k, len(corpus))
        top = top_k_similar(query_vec, corpus_mat, k)

        items = [
            SimilarityResponseItem(index=i, text=corpus[i], score=round(score, 6))
            for i, score in top
        ]

        return RecommendationsResponse(
            query=req.text,
            embedding_type=emb_type,
            recommendations=items
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Recommendations error: {e}")

@router.post("/forecast/volume", response_model=ForecastVolumeResponse)
def forecast_volume(req: ForecastVolumeRequest):
    try:
        model_name, fitted, forecast = _fit_forecast_series(
            y=req.counts,
            periods=req.periods,
            seasonal_periods=req.seasonal_periods,
            trend=req.trend,
            seasonal=req.seasonal
        )

        # Simple approximate confidence intervals:
        # use residual std of fitted values where available
        try:
            residuals = np.asarray(req.counts, dtype=float) - fitted
            sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 2 else 0.0
            ci = [(float(f - 1.96 * sigma), float(f + 1.96 * sigma)) for f in forecast]
        except Exception:
            ci = None

        return ForecastVolumeResponse(
            model=model_name,
            fitted=[float(x) for x in fitted.tolist()],
            forecast=[float(x) for x in forecast.tolist()],
            conf_int=ci,
            seasonal_periods=req.seasonal_periods
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Forecast error: {e}")

@router.post("/forecast/category", response_model=ForecastCategoryResponse)
def forecast_category(req: ForecastCategoryRequest):
    try:
        results: List[ForecastCategoryResponseItem] = []
        for cat, series in req.series_by_category.items():
            model_name, _, fc = _fit_forecast_series(
                y=series,
                periods=req.periods,
                seasonal_periods=req.seasonal_periods,
                trend=req.trend,
                seasonal=req.seasonal
            )
            results.append(ForecastCategoryResponseItem(
                category=cat,
                model=model_name,
                forecast=[float(x) for x in fc.tolist()],
                seasonal_periods=req.seasonal_periods
            ))
        return ForecastCategoryResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Category forecast error: {e}")

@router.post("/forecast/scenarios", response_model=ForecastScenarioResponse)
def forecast_scenarios(req: ForecastScenarioRequest):
    try:
        model_name, _, base_fc = _fit_forecast_series(
            y=req.counts,
            periods=req.periods,
            seasonal_periods=req.seasonal_periods,
            trend=req.trend,
            seasonal=req.seasonal
        )
        scenarios_out: Dict[str, List[float]] = {}
        for name, factor in req.scenarios.items():
            # multiplicative scenario: e.g., +20% traffic => factor=1.2
            adj = (np.asarray(base_fc, dtype=float) * float(factor)).tolist()
            scenarios_out[name] = [float(x) for x in adj]
        return ForecastScenarioResponse(
            base_model=model_name,
            base_forecast=[float(x) for x in base_fc.tolist()],
            scenarios=scenarios_out,
            seasonal_periods=req.seasonal_periods
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Scenario forecast error: {e}")

@router.post("/optimize/benchmark", response_model=OptimizeBenchmarkResponse)
def optimize_benchmark(req: OptimizeBenchmarkRequest):
    """
    Simple micro-benchmark to inform production optimizations:
    - Average time to embed N texts
    - Average time to compute pairwise cosine similarity on a batch
    """
    try:
        texts = req.texts
        bs = req.batch_size
        reps = req.repetitions

        # Ensure we have at least one full batch
        if len(texts) < bs:
            raise ValueError(f"Need at least batch_size={bs} texts for a fair benchmark.")

        embed_times = []
        sim_times = []
        tokens_per_sec = []

        for _ in range(reps):
            batch = texts[:bs]

            # Embedding
            t0 = time.perf_counter()
            if req.use_transformer:
                embeddings = embed_transformer(batch, batch_size=min(16, bs))
            else:
                emb, _ = embed_tfidf(batch)
                embeddings = emb
            t1 = time.perf_counter()
            embed_times.append((t1 - t0) * 1000.0)  # ms

            # Approximate token count (for transformer)
            if req.use_transformer:
                tokenizer, _, _ = _load_transformer()
                total_tokens = sum(len(tokenizer.encode(x, truncation=True, max_length=256)) for x in batch)
                tokens_per_sec.append(total_tokens / max(t1 - t0, 1e-9))

            # Pairwise similarity time
            t2 = time.perf_counter()
            _ = cosine_similarity(embeddings)
            t3 = time.perf_counter()
            sim_times.append((t3 - t2) * 1000.0)

        resp = OptimizeBenchmarkResponse(
            embedding_type="transformer" if req.use_transformer else "tfidf",
            avg_embed_time_ms=float(np.mean(embed_times)),
            avg_similarity_time_ms=float(np.mean(sim_times)),
            tokens_per_sec_est=(float(np.mean(tokens_per_sec)) if tokens_per_sec else None),
            notes="Transformer numbers depend on CPU/GPU and sequence length."
        )
        return resp
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Benchmark error: {e}")




@router.post("/forecast")
async def forecast_tickets(req: ForecastRequest):
    """
    Time-series forecasting for ticket volume trends using statsmodels.
    Groups by category and forecasts ticket counts.
    """
    try:
        df = pd.DataFrame(req.tickets)
        if "category" not in df.columns:
            raise HTTPException(status_code=400, detail="Tickets must include 'category' field.")

        # Count tickets per category (daily-style index for forecasting)
        counts = df["category"].value_counts()
        series = counts.values

        if len(series) < 3:
            return {"detail": "Not enough data for forecasting."}

        # Simple seasonal forecast with Holt-Winters
        model = ExponentialSmoothing(series, trend="add", seasonal=None)
        fit = model.fit(optimized=True)
        forecast = fit.forecast(7)  # Next 7 periods

        return {
            "method": "holt-winters",
            "input_length": len(series),
            "forecast_horizon": 7,
            "forecast": forecast.tolist(),
            "categories": counts.to_dict()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Forecasting failed: {str(e)}")
