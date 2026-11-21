# RoadGuard AI

RoadGuard AI is a Flask-based road damage complaint system with:

- Guided, four-step public complaint form
- Optional photo upload and browser geolocation
- Image-based damage severity estimation
- Priority scoring and duplicate detection
- Admin dashboard with filtering and status updates
- SQLite persistence and REST API

## Run locally (Windows PowerShell)

```powershell
py -m pip install -r requirements.txt
py app.py
```

`app.py` now starts Waitress, a production WSGI server. For a separate WSGI
process or hosting platform, use `wsgi:app` as the application entry point.
In VS Code, select **Launch RoadGuard AI** in Run and Debug and press **F5**.

Open `http://localhost:5000` for the public form and
`http://localhost:5000/dashboard` for the dashboard.

The database (`roadguard.db`) and uploaded images (`static/uploads/`) are created
automatically. Allow location access in the browser to attach coordinates; a
descriptive road or landmark is still required. Photo upload is optional and
supports JPG, PNG, and WEBP files up to 10 MB.

## Complaint submission flow

1. **Location & issue:** Enter a road or landmark, describe the damage, and
   optionally attach current coordinates.
2. **Your details:** Enter a name and optional phone number or email address.
3. **Advanced details:** Specify hazard type, road type, traffic impact, safety risk, observation time, and affected area.
4. **Evidence & review:** Optionally add a photo, check the summary, then submit.

The server validates all submitted fields and image content, analyzes an
uploaded image, checks for an active complaint at the same location, and stores
the report in SQLite. The included image analyzer is a lightweight heuristic,
not a trained detection model; AI severity and priority are estimates and need
field verification.

## API

- `GET /api/complaints` — list reports; supports `status`, `severity`, and
  `search` query parameters.
- `POST /api/complaints` — submit a multipart form with `citizen_name` and
  `location`; optional fields are `phone`, `email`, `latitude`, `longitude`,
  `description`, `hazard_type`, `road_type`, `traffic_impact`, `safety_risk`,
  `observed_at`, `affected_area`, and `image`.
- `GET /api/complaints/<id>` — fetch one report.
- `PATCH /api/complaints/<id>` — update status with JSON, for example
  `{"status":"Resolved"}`.
- `GET /api/stats` — dashboard summary counts.

The dashboard is intended as a local/demo admin interface. Add authentication
and deployment configuration before exposing it to a public network.
