# ML

Stub only — this session scaffolds structure, not implementation. No ML code exists yet.

Planned future contents, per the OG-PIOS product spec:
- Anomaly detection (rolling averages, z-score, Isolation Forest) over production, pressure,
  temperature, and equipment readings.
- Production forecasting (7/30/90-day) with baseline statistical models compared against
  scikit-learn/XGBoost models, evaluated via MAE/RMSE/MAPE.
- Equipment health scoring.

All model outputs must be framed as estimates requiring engineering review — see the standing
AI-output guardrail in the root `CLAUDE.md`. Never a guaranteed conclusion, never autonomous
control of field equipment.

`requirements.txt` lists intended future dependencies; nothing here is installed or wired up
yet.
