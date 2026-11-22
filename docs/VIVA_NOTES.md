# Viva preparation: where to look

* **Problem:** students under-estimate how much time is lost to postponing and interruptions; SPD turns their own records into explainable feedback.
* **Workflow to explain end to end:** create task -> start focus session (`services/session_service.py`) -> record saved (`database/repositories.finish_session`) -> analytics (`analytics/service.py`) -> score (`analytics/scoring.py`) -> indicators/recommendations -> report/PDF (`services/export_service.py`).
* **Why layered:** pages never touch SQL; repositories validate and own transactions; analytics are pure functions over DataFrames, which makes them testable.
* **Likely questions:**
  * *How is the score computed and why those weights?* README table; weights are a documented starting point, not a validated psychometric.
  * *What if there is no data?* Missing parts are rescaled out; no data gives no score.
  * *Is the ML trustworthy?* Only shown if it beats a baseline on newer held-out tasks; otherwise predictions are hidden.
  * *Privacy?* Consent gate in `tracking/consent.py`; only idle seconds and an app category are ever stored.
