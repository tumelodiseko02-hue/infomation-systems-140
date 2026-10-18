"""AgriMinds MVP: Flask app (login + capture forms + JSON API + dashboard + CI chart + Supabase sync)."""
import base64
import os
import secrets
from datetime import date

import pandas as pd
from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for

import ci as cimod
import dashboard as dash
from auth import AuthDB
from storage import make_storage
from supabase_client import SupabaseClient, SupabaseNotConfigured
from trial_db import GROUP_FIELDS, OPTIONAL, SECTIONS, TrialDB, label

CROPS = ["Maize", "Sorghum", "Beans", "Groundnuts", "Cassava", "Wheat"]
TREATMENTS = ["Control", "Fertilizer", "Compost", "Improved seed"]
PUBLIC_ENDPOINTS = {"login", "register", "api_login", "health", "static"}


def create_app(storage=None, supabase=None, auth=None, trials=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,  # CSV uploads up to 2 MB
        storage=storage or make_storage(),
        supabase=supabase or SupabaseClient(),
        auth=auth or AuthDB(),
        trials=trials or TrialDB(),
    )
    allow_registration = os.getenv("ALLOW_REGISTRATION", "1") == "1"

    def store():
        return app.config["storage"]

    #  authentication
    @app.before_request
    def require_login():
        if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if session.get("user"):
            return None
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required", hint="POST /api/login"), 401
        return redirect(url_for("login", next=request.path))

    def safe_next(target):
        # only allow local paths, never "//evil.com" or "http://..."
        if target and target.startswith("/") and not target.startswith("//"):
            return target
        return url_for("form")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error, code = None, 200
        if request.method == "POST":
            status, name = app.config["auth"].verify(request.form.get("username"), request.form.get("pin"))
            if status == "ok":
                session.clear()
                session["user"] = name
                return redirect(safe_next(request.form.get("next")))
            error = ("Too many failed attempts. Try again in a few minutes." if status == "locked"
                     else "Incorrect username or PIN.")
            code = 429 if status == "locked" else 401
        return render_template("login.html", error=error,
                               next=request.values.get("next", ""),
                               can_register=allow_registration), code

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if not allow_registration:
            return render_template("register.html", error="Registration is disabled.",
                                   disabled=True), 403
        error, code = None, 200
        if request.method == "POST":
            if request.form.get("pin") != request.form.get("pin2"):
                error, code = "PINs do not match", 400
            else:
                try:
                    app.config["auth"].create_user(request.form.get("username"), request.form.get("pin"))
                    return render_template("login.html", error=None, next="", can_register=True,
                                           info="Account created. You can log in now."), 201
                except ValueError as exc:
                    error, code = str(exc), 400
        return render_template("register.html", error=error, disabled=False), code

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.post("/api/login")
    def api_login():
        body = request.get_json(silent=True) or {}
        status, name = app.config["auth"].verify(body.get("username"), body.get("pin"))
        if status == "ok":
            session.clear()
            session["user"] = name
            return jsonify(user=name)
        if status == "locked":
            return jsonify(error="Too many failed attempts, try again later"), 429
        return jsonify(error="Incorrect username or PIN"), 401

    @app.post("/api/logout")
    def api_logout():
        session.clear()
        return jsonify(ok=True)

    # validation for the farmer/yield form + API
    def validate(payload):
        """Return (clean_dict, errors_dict)."""
        errors, clean = {}, {}

        def text(key, required=False, maxlen=120):
            v = str(payload.get(key) or "").strip()
            if required and not v:
                errors[key] = "Required"
            elif len(v) > maxlen:
                errors[key] = f"Max {maxlen} characters"
            clean[key] = v or None

        def number(key, required=False, minimum=0.0, maximum=None):
            raw = payload.get(key)
            if raw in (None, ""):
                if required:
                    errors[key] = "Required"
                clean[key] = None
                return
            try:
                v = float(raw)
            except (TypeError, ValueError):
                errors[key] = "Must be a number"
                return
            if v != v or v in (float("inf"), float("-inf")):
                errors[key] = "Must be a number"
                return
            if v < minimum or (maximum is not None and v > maximum):
                errors[key] = f"Must be between {minimum:g} and {maximum:g}" if maximum \
                    else f"Must be at least {minimum:g}"
                return
            clean[key] = v

        text("name", required=True)
        text("phone", required=True, maxlen=30)
        text("village")
        number("farm_size_ha", minimum=0.01, maximum=100000)
        text("crop", required=True, maxlen=60)
        text("variety")
        text("treatment", maxlen=60)
        text("notes", maxlen=500)
        number("yield_kg_per_ha", required=True, minimum=0, maximum=100000)

        pd_raw = str(payload.get("planting_date") or "").strip()
        if pd_raw:
            try:
                date.fromisoformat(pd_raw)
            except ValueError:
                errors["planting_date"] = "Use YYYY-MM-DD"
        clean["planting_date"] = pd_raw or None
        return clean, errors

    def save(clean):
        """Upsert the farmer (by phone) and add the trial. Returns (farmer, trial)."""
        farmer = store().find_farmer_by_phone(clean["phone"]) or store().add_farmer(clean)
        trial = store().add_trial({**clean, "farmer_id": farmer["id"]})
        return farmer, trial

    # farmer / yield capture
    @app.get("/")
    def form():
        return render_template("form.html", crops=CROPS, treatments=TREATMENTS,
                               values={}, errors={}, saved=request.args.get("saved"),
                               today=date.today().isoformat())

    @app.post("/submit")
    def submit():
        clean, errors = validate(request.form)
        if errors:
            return render_template("form.html", crops=CROPS, treatments=TREATMENTS,
                                   values=request.form, errors=errors, saved=None,
                                   today=date.today().isoformat()), 400
        save(clean)
        return redirect(url_for("form", saved=1))

    @app.get("/dashboard")
    def dashboard():
        df = dash.trials_frame(store().list_trials(), store().list_farmers())
        summary = dash.summary_by_crop(df)
        rows = [{k: (None if v != v else v) for k, v in r.items()}
                for r in summary.to_dict("records")]
        return render_template(
            "dashboard.html",
            stats=dash.overview(df, store().list_farmers()),
            rows=rows,
            backend=store().name,
            supabase_ready=app.config["supabase"].configured,
        )

    @app.get("/chart.png")
    def chart():
        df = dash.trials_frame(store().list_trials(), store().list_farmers())
        png = dash.ci_chart_png(dash.summary_by_crop(df))
        return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})

    # ---------- trial measurements (agritrial.db / trial_data) ----------
    def trial_form_ctx(**kw):
        ctx = dict(sections=[(t, [(f, label(f)) for f in fs]) for t, fs in SECTIONS],
                   values={}, errors={}, saved=None, today=date.today().isoformat())
        ctx.update(kw)
        return ctx

    @app.get("/trial-data")
    def trial_form():
        return render_template("trial_form.html", **trial_form_ctx(saved=request.args.get("saved")))

    @app.post("/trial-data")
    def trial_submit():
        clean, errors = app.config["trials"].clean(request.form)
        if errors:
            return render_template("trial_form.html",
                                   **trial_form_ctx(values=request.form, errors=errors)), 400
        app.config["trials"].save(clean)
        return redirect(url_for("trial_form", saved=1))

    @app.get("/api/trial-data")
    def api_trial_data():
        return jsonify(app.config["trials"].list())

    @app.post("/api/trial-data")
    def api_add_trial_data():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Body must be a JSON object"), 400
        clean, errors = app.config["trials"].clean(payload)
        if errors:
            return jsonify(error="Validation failed", fields=errors), 422
        return jsonify(id=app.config["trials"].save(clean)), 201

    # CI chart (your "real CI chart" script)
    def parse_groups(text):
        return [g.strip() for g in (text or "").split(",") if g.strip()]

    def png_b64(png):
        return base64.b64encode(png).decode("ascii")

    def db_ci(args):

        column, group_by = args.get("column", ""), args.get("group_by", "treatment_group")
        if column not in OPTIONAL:  # whitelist: never trust a column name from the client
            return None, f"Unknown measurement '{column}'"
        if group_by not in GROUP_FIELDS:
            return None, f"Cannot group by '{group_by}'"
        rows_in = app.config["trials"].list()
        if not rows_in:
            return None, "No trial data yet. Add some on the Trial data page."
        df = pd.DataFrame(rows_in)
        crop = (args.get("crop") or "").strip()
        if crop:  # mixing crops with different scales makes a CI meaningless, so allow filtering
            df = df[df["crop"].str.lower() == crop.lower()]
            if df.empty:
                return None, f"No trial data for crop '{crop}'"
        stats = cimod.group_stats(df, column, group_by, parse_groups(args.get("groups")))
        return {"column": column, "group_by": group_by, "crop": crop or None,
                "confidence": 0.95, "groups": stats}, None

    @app.get("/ci")
    def ci_page():
        ctx = dict(optional=[(f, label(f)) for f in OPTIONAL],
                   group_fields=[(f, label(f)) for f in GROUP_FIELDS],
                   values=request.args, error=None, db=None, csv=None, csv_values={})
        if request.args.get("column"):
            result, error = db_ci(request.args)
            ctx["error"] = error
            if result:
                title = f"{label(result['column'])} by {label(result['group_by']).lower()} (95% CI)"
                if result["crop"]:
                    title = f"{result['crop']}: {title}"
                result["png"] = png_b64(cimod.ci_groups_png(result["groups"], label(result["column"]), title))
                ctx["db"] = result
        return render_template("ci.html", **ctx), (422 if ctx["error"] else 200)

    @app.post("/ci/csv")
    def ci_csv():
        f = request.files.get("file")
        v = request.form
        ctx = dict(optional=[(x, label(x)) for x in OPTIONAL],
                   group_fields=[(x, label(x)) for x in GROUP_FIELDS],
                   values={}, error=None, db=None, csv=None, csv_values=v)
        try:
            if not f or not f.filename:
                raise ValueError("Choose a CSV file")
            df = pd.read_csv(f.stream)
            col, grp = v.get("column", "").strip(), v.get("group_column", "").strip()
            for name in (col, grp):
                if name not in df.columns:
                    raise ValueError(f"Column '{name}' not found. Columns are: {', '.join(map(str, df.columns))}")
            groups = parse_groups(v.get("groups"))
            stats = cimod.group_stats(df, col, grp, groups)
            title = f"{col} with 95% confidence interval"
            ctx["csv"] = {"column": col, "group_by": grp, "groups": stats,
                          "png": png_b64(cimod.ci_groups_png(stats, col, title))}
        except (ValueError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            ctx["error"] = str(exc) or "Could not read that file"
        return render_template("ci.html", **ctx), (422 if ctx["error"] else 200)

    @app.get("/api/ci")
    def api_ci():
        result, error = db_ci(request.args)
        if error:
            return jsonify(error=error), 422
        return jsonify(result)

    # ---------- JSON API for farmer / yield data ----------
    @app.get("/api/health")
    def health():
        return jsonify(status="ok", storage=store().name,
                       supabase_configured=app.config["supabase"].configured)

    @app.get("/api/farmers")
    def api_farmers():
        return jsonify(store().list_farmers())

    @app.get("/api/trials")
    def api_trials():
        trials = store().list_trials()
        crop = request.args.get("crop")
        if crop:
            trials = [t for t in trials if (t["crop"] or "").lower() == crop.lower()]
        return jsonify(trials)

    @app.post("/api/trials")
    def api_add_trial():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Body must be a JSON object"), 400
        clean, errors = validate(payload)
        if errors:
            return jsonify(error="Validation failed", fields=errors), 422
        farmer, trial = save(clean)
        return jsonify(farmer=farmer, trial=trial), 201

    @app.get("/api/summary")
    def api_summary():
        df = dash.trials_frame(store().list_trials(), store().list_farmers())
        summary = dash.summary_by_crop(df)
        records = [{k: (None if v != v else v) for k, v in r.items()}
                   for r in summary.to_dict("records")]
        return jsonify(overview=dash.overview(df, store().list_farmers()),
                       by_crop=records, confidence=0.95)

    @app.post("/api/sync")
    def api_sync():
        try:
            result = app.config["supabase"].sync(store().list_farmers(), store().list_trials())
        except SupabaseNotConfigured:
            return jsonify(error="Supabase not configured",
                           hint="Set SUPABASE_URL and SUPABASE_KEY, then retry"), 503
        except Exception as exc:  # network / auth / schema errors
            return jsonify(error="Supabase sync failed", detail=str(exc)), 502
        return jsonify(synced=result)

    return app


if __name__ == "__main__":
    create_app().run(debug=os.getenv("FLASK_DEBUG", "1") == "1", port=int(os.getenv("PORT", "5000")))
