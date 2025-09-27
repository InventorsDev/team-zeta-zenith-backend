# app/analytics/ticket_forecaster.py
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from datetime import timedelta


class TicketForecaster:
    def __init__(self, order=(5, 1, 0)):
        """
        Initialize the ticket forecaster with ARIMA parameters.
        Default order=(5, 1, 0) is simple, but can be tuned.
        """
        self.order = order
        self.model = None
        self.fitted_model = None

    def fit(self, ticket_data: pd.DataFrame):
        """
        Fit ARIMA model to ticket volume data.

        ticket_data: DataFrame with columns ["date", "ticket_count"]
        """
        ticket_data = ticket_data.sort_values("date")
        ticket_data["date"] = pd.to_datetime(ticket_data["date"])
        ticket_data.set_index("date", inplace=True)

        self.model = ARIMA(ticket_data["ticket_count"], order=self.order)
        self.fitted_model = self.model.fit()

    def forecast(self, days=7):
        """
        Forecast future ticket volumes.

        Returns DataFrame with ["date", "forecast"].
        """
        if not self.fitted_model:
            raise ValueError("Model not trained. Call fit() first.")

        forecast = self.fitted_model.get_forecast(steps=days)
        forecast_df = forecast.summary_frame()
        forecast_df.reset_index(inplace=True)
        forecast_df.rename(columns={"index": "date", "mean": "forecast"}, inplace=True)

        return forecast_df[["date", "forecast", "mean_ci_lower", "mean_ci_upper"]]


if __name__ == "__main__":
    # Example usage
    data = pd.DataFrame({
        "date": pd.date_range(start="2025-07-01", periods=30, freq="D"),
        "ticket_count": [50, 52, 48, 55, 60, 62, 59, 65, 70, 68,
                         72, 74, 76, 78, 75, 80, 82, 85, 87, 90,
                         88, 85, 83, 80, 78, 76, 74, 72, 70, 68]
    })

    forecaster = TicketForecaster(order=(2, 1, 2))
    forecaster.fit(data)
    print(forecaster.forecast(7))
