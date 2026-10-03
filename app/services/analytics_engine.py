import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from statsmodels.tsa.ar_model import AutoReg

class AnalyticsEngine:
    @staticmethod
    def train_supervised_model(df: pd.DataFrame, target_col: str, feature_cols: list, model_type: str = "ols", **kwargs):
        data = df.dropna(subset=[target_col] + feature_cols)
        X = data[feature_cols].values
        y = data[target_col].values

        if len(y) < 10:
            raise ValueError("Amostras insuficientes para treinamento (mínimo 10 registros).")

        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        if model_type == "ols":
            model = LinearRegression()
        elif model_type == "ridge":
            model = Ridge(alpha=kwargs.get("alpha", 1.0))
        elif model_type == "lasso":
            model = Lasso(alpha=kwargs.get("alpha", 0.1))
        elif model_type == "random_forest":
            model = RandomForestRegressor(n_estimators=kwargs.get("n_estimators", 50), random_state=42)
        elif model_type == "decision_tree":
            model = DecisionTreeRegressor(max_depth=kwargs.get("max_depth", 6), random_state=42)
        else:
            raise ValueError(f"Modelo não suportado: {model_type}")

        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        metrics = {
            "r2": round(float(r2_score(y_test, preds)), 4),
            "rmse": round(float(np.sqrt(mean_squared_error(y_test, preds))), 4),
            "mae": round(float(mean_absolute_error(y_test, preds)), 4)
        }

        params = {}
        if hasattr(model, "coef_"):
            params["coefficients"] = {f: round(float(c), 4) for f, c in zip(feature_cols, model.coef_)}
            params["intercept"] = round(float(model.intercept_), 4)
        elif hasattr(model, "feature_importances_"):
            params["feature_importances"] = {f: round(float(i), 4) for f, i in zip(feature_cols, model.feature_importances_)}

        return {
            "metrics": metrics,
            "params": params,
            "actual": y_test.tolist()[:100],
            "predicted": preds.tolist()[:100]
        }

    @staticmethod
    def forecast_autoregressive(series: pd.Series, lags: int = 5, steps: int = 20):
        clean_series = series.dropna().values
        if len(clean_series) <= lags:
            raise ValueError(f"Tamanho da série deve ser maior que os lags ({lags}).")

        ar_model = AutoReg(clean_series, lags=lags, old_names=False).fit()
        forecast = ar_model.predict(start=len(clean_series), end=len(clean_series) + steps - 1)

        return {
            "params": {f"lag_{i}": round(float(p), 4) for i, p in enumerate(ar_model.params)},
            "forecast": [round(float(v), 2) for v in forecast]
        }