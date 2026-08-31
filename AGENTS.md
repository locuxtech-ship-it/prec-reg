# AGENTS — Precursores Regulares Dashboard

## Quick launch (local)
```
python run.py        # dev server on http://localhost:5000
```

## Quick launch (deployed)
- Live: https://locuxtech.pythonanywhere.com
- Login: `alameda2024` (admin) | `invitado2024` (invitado)

## Codebase structure
- `app.py` — main Flask app (all routes, auth, PDF generation, annual report)
- `templates/` — HTML templates (index, login, registrar, PDFs)
- `prec.csv` — monthly hour records (semicolon-separated)
- `precursores.csv` — precursor metadata (name, appointment date, token)
- `requirements.txt` — dependencies (includes gunicorn)
- `.gitignore` — ignores __pycache__, venv, .env, *.csv (but tracks prec.csv & precursores.csv)
- `static/favicon.png` — favicon

## Critical conventions
- **Service year**: Sep–Aug cycle. Months Ene–Ago → year 2026; Sep→Dic → year 2025.
  Formula: `anio = 2026 if mes in (Ene,Feb,Mar,Abr,May,Jun,Jul,Agosto) else 2025`
- **Auth**: Session-based. `session['rol']` stores `'admin'` or `'invitado'`.
  - Admin (`alameda2024`): can register, edit, generate tokens
  - Invitado (`invitado2024`): view-only, no edit/create buttons
- **Status in PDF**: `"OK"` if any hours or SS were reported that month, `"Pendiente"` if no record exists (regardless of total vs goal)
- **Annual report**: `/reporte-anual` shows three groups: Umbral (560-599h), No cumplieron (<560h), Cumplieron (600h+)
- **Token access**: Precursors get individual links via `/precursor/<nombre>/generar-token` (admin only). Links go to `/acceso/<token>` showing only that pioneer's data + PDF download.

## Data store notes
- CSV files are **tracked in git** (precisely: `!prec.csv` and `!precursores.csv` in .gitignore allow them).
- On PythonAnywhere free plan, CSV data **persists across restarts** (unlike Render's ephemeral filesystem).
- Always commit after editing CSV data: `git add prec.csv precursores.csv && git commit -m "..." && git push`

## Commands that matter
```
# Dev locally
python run.py

# Deploy (after git push)
# On PythonAnywhere console Bash:
cd ~/prec-reg && git pull   # then click "Reload" in Web tab

# Generate a precursor access link (admin)
# From dashboard: click 🔗 Link button next to a precursor
# A modal shows the URL; copy and share with the pioneer

# Admin passwords
#   alameda2024 — full access
#   invitado2024 — view only

# Test the app locally
python -c "import app; app.app.test_client().get('/'); print('OK')"
```

## Directory ownership
- `app.py` — all routes, auth logic, PDF generation, annual report logic
- `templates/` — all HTML; changes to navbar, modals, or views here affect both admin and guest
- `prec.csv` / `precursores.csv` — data; edit via admin forms or directly (respect CSV format: semicolons, encoding utf-8-sig)
- `requirements.txt` — add packages only; `pip install -r requirements.txt` then commit

## Common pitfalls
- **Year column confusion**: The dashboard table column labeled "Año" shows the service-year ending year (2025 or 2026), NOT the calendar year. Months Sep-Dec 2025 show as 2025; Ene-Aug 2026 show as 2026.
- **Login redirects**: `/` and most routes require `@login_required`. Accessing `/login` directly shows the login page. After login, `/reporte-anual` is accessible for both roles.
- **Token vs password**: The `/acceso/<token>` route does NOT use the login system. Precursors enter their token on the login page's "Acceso para precursores" field, or click the "Link" button from the admin dashboard.
- **CSV semicolons**: The CSV uses semicolons (`;`) as delimiters. Editing in Excel may convert them; use a text editor or import with semicolon separator.
- **Free plan sleep**: PythonAnywhere free plan deactivates the site after ~1 month of inactivity. Log in and click "Activar hasta dentro de un mes" in the Web tab.
- **Gunicorn vs run.py**: In production, gunicorn uses `app:app`. `run.py` is only for local dev (`python run.py`).

## Files to never edit casually
- `.gitignore` — carefully; the `!prec.csv` / `!precursores.csv` exceptions are intentional
- `requirements.txt` — only add; do not remove existing packages or pip may break
- `app.py` — the service-year formula (`determinar_anio_servicio`) and CSV column mapping are critical; changing them breaks year display across the entire app