from typing import Any, Dict, List, Sequence, Union
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from statsmodels.tsa.ar_model import AutoReg

class AnalyticsEngine:
    @staticmethod
    def train_supervised_model(
        df: pd.DataFrame, 
        target_col: str, 
        feature_cols: Sequence[str], 
        model_type: str = "ols", 
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Treina e valida modelos de regressão linear e não linear multivariados,
        garantindo conformidade estrita de tipos com NumPy, Scikit-Learn e Pylance.
        """
        cols_needed = [target_col] + list(feature_cols)
        data = df.dropna(subset=cols_needed)

        # Conversão explícita para ndarray float64 para eliminar avisos de ExtensionArray
        X: np.ndarray = np.asarray(data[list(feature_cols)].to_numpy(), dtype=np.float64)
        y: np.ndarray = np.asarray(data[target_col].to_numpy(), dtype=np.float64).ravel()

        if len(y) < 10:
            raise ValueError("Amostras insuficientes para treinamento (mínimo de 10 registos válidos).")

        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        # Instanciação do regressor
        model: Union[LinearRegression, Ridge, Lasso, RandomForestRegressor, DecisionTreeRegressor]

        if model_type == "ols":
            model = LinearRegression()
        elif model_type == "ridge":
            alpha_val = float(kwargs.get("alpha", 1.0))
            model = Ridge(alpha=alpha_val)
        elif model_type == "lasso":
            alpha_val = float(kwargs.get("alpha", 0.1))
            model = Lasso(alpha=alpha_val)
        elif model_type == "random_forest":
            n_est = int(kwargs.get("n_estimators", 50))
            model = RandomForestRegressor(n_estimators=n_est, random_state=42)
        elif model_type == "decision_tree":
            max_d = int(kwargs.get("max_depth", 6))
            model = DecisionTreeRegressor(max_depth=max_d, random_state=42)
        else:
            raise ValueError(f"Modelo não suportado: {model_type}")

        model.fit(X_train, y_train)
        preds: np.ndarray = np.asarray(model.predict(X_test), dtype=np.float64)

        # Cálculo das métricas com coerção estrita para float nativo
        r2_val = float(r2_score(y_test, preds))
        mse_val = float(mean_squared_error(y_test, preds))
        mae_val = float(mean_absolute_error(y_test, preds))
        rmse_val = float(np.sqrt(mse_val))

        metrics: Dict[str, float] = {
            "r2": round(r2_val, 4),
            "rmse": round(rmse_val, 4),
            "mae": round(mae_val, 4)
        }

        # Extração defensiva de parâmetros através de getattr para mitigar restrições de união de tipos
        params: Dict[str, Any] = {}

        coef_attr = getattr(model, "coef_", None)
        intercept_attr = getattr(model, "intercept_", None)
        feat_imp_attr = getattr(model, "feature_importances_", None)

        if coef_attr is not None:
            coef_array = np.asarray(coef_attr, dtype=np.float64).ravel()
            params["coefficients"] = {
                str(f): round(float(c), 4) for f, c in zip(feature_cols, coef_array)
            }
            if intercept_attr is not None:
                params["intercept"] = round(float(intercept_attr), 4)
        elif feat_imp_attr is not None:
            feat_imp_array = np.asarray(feat_imp_attr, dtype=np.float64).ravel()
            params["feature_importances"] = {
                str(f): round(float(i), 4) for f, i in zip(feature_cols, feat_imp_array)
            }

        actual_list: List[float] = [round(float(v), 2) for v in y_test[:100]]
        predicted_list: List[float] = [round(float(v), 2) for v in preds[:100]]

        return {
            "metrics": metrics,
            "params": params,
            "actual": actual_list,
            "predicted": predicted_list
        }

    @staticmethod
    def forecast_autoregressive(
        series: pd.Series, 
        lags: int = 5, 
        steps: int = 20
    ) -> Dict[str, Any]:
        """
        Executa estimativa autorregressiva estocástica sobre séries temporais
        garantindo tipagem nativa 1D em np.float64.
        """
        clean_array: np.ndarray = np.asarray(series.dropna().to_numpy(), dtype=np.float64)

        if len(clean_array) <= lags:
            raise ValueError(f"O tamanho da série ({len(clean_array)}) deve ser estritamente superior ao número de lags ({lags}).")

        ar_model = AutoReg(clean_array, lags=lags, old_names=False).fit()
        forecast_res: np.ndarray = np.asarray(
            ar_model.predict(start=len(clean_array), end=len(clean_array) + steps - 1),
            dtype=np.float64
        )

        model_params: np.ndarray = np.asarray(ar_model.params, dtype=np.float64)
        params_dict: Dict[str, float] = {
            f"lag_{i}": round(float(p), 4) for i, p in enumerate(model_params)
        }

        forecast_list: List[float] = [round(float(v), 2) for v in forecast_res]

        return {
            "params": params_dict,
            "forecast": forecast_list
        }