from flask import Flask, jsonify, request, send_file, redirect, url_for, render_template, flash
from models import Daira, Municipality, Pharmacist, DutySchedule, User, Vacation
from database import firestore_db as db
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os, sys, threading, webbrowser
import pandas as pd
from io import BytesIO

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    data_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = base_dir

template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None


@login_manager.user_loader
def load_user(user_id):
    return db.get_user_by_id(user_id)


try:
    db.create_default_admin()
except Exception:
    pass

from services.roster_service import generate_roster, get_roster_data, get_days_in_month
from services.pdf_service import generate_roster_pdf, generate_batch_roster_pdf
import calendar


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
        else:
            username = request.form.get('username')
            password = request.form.get('password')

        user = db.get_user_by_username(username)
        if user and user.check_password(password):
            flask_user = UserObject(user)
            login_user(flask_user)
            if request.is_json:
                return jsonify({"status": "success", "message": "Logged in successfully"})
            return redirect(url_for('index'))

        if request.is_json:
            return jsonify({"status": "error", "message": "Invalid username or password"}), 401
        flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "Pharmacy Roster API", "authenticated": current_user.is_authenticated})


@app.route('/api/roster', methods=['GET'])
@login_required
def get_roster_json():
    month = int(request.args.get('month', 2))
    year = int(request.args.get('year', 2026))
    daira_id = request.args.get('daira_id', '1')

    generate_roster(year, month, daira_id)

    duties = db.get_duties_for_month(year, month, daira_id)

    result = []
    for d in duties:
        ph = db.get_pharmacist(d.pharmacist_id)
        muni = db.get_municipality(d.municipality_id)
        result.append({
            "date": d.date.isoformat(),
            "pharmacist": ph.name_fr if ph else "",
            "municipality": muni.name_fr if muni else "",
            "shift_type": d.shift_type,
            "is_holiday": d.is_holiday,
        })

    return jsonify(result)


@app.route('/api/roster/generated-months', methods=['GET'])
@login_required
def get_generated_months():
    results = db.get_generated_months()
    return jsonify(results)


@app.route('/api/roster/delete', methods=['DELETE'])
@login_required
def delete_roster_month():
    data = request.json
    month = data.get('month')
    year = data.get('year')
    if not month or not year:
        return jsonify({"error": "Month and year are required"}), 400

    db.delete_duties_for_month(int(year), int(month))
    return jsonify({"message": f"Roster for {month}/{year} deleted successfully"})


@app.route('/history')
@login_required
def history_page():
    return render_template('history.html')


@app.route('/api/reports/monthly-pdf', methods=['GET'])
@login_required
def generate_monthly_pdf_api():
    month = int(request.args.get('month', 2))
    year = int(request.args.get('year', 2026))
    daira_id = request.args.get('daira_id', '1')

    try:
        generate_roster(year, month, daira_id)

        daira = db.get_daira(daira_id)
        municipalities = db.get_municipalities_by_daira(daira_id)
        days = get_days_in_month(year, month)
        pharmacist_dict = db.get_all_pharmacists_dict()
        all_duties = db.get_duties_for_month_bulk(year, month)

        muni_ids = {m.id for m in municipalities}
        duty_index = {}
        for d in all_duties:
            if d.municipality_id in muni_ids:
                key = (d.date.isoformat(), d.municipality_id)
                duty_index.setdefault(key, []).append(d)

        table_data = []
        day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        day_names_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

        for d in days:
            day_duties_grouped = []
            for muni in municipalities:
                key = (d.isoformat(), muni.id)
                duties = duty_index.get(key, [])
                day_duties_grouped.append(duties)

            table_data.append((
                d,
                day_names_fr[d.weekday()],
                day_names_ar[d.weekday()],
                day_duties_grouped
            ))

        pdf_bytes = generate_roster_pdf(year, month, daira, table_data, municipalities, pharmacist_dict)

        filename = f"Garde_{calendar.month_name[month]}_{year}_{daira.name_fr}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/reports/all-dairas-pdf', methods=['GET'])
@login_required
def generate_all_dairas_pdf_api():
    month = int(request.args.get('month', 2))
    year = int(request.args.get('year', 2026))

    try:
        dairas = db.get_all_dairas()
        all_municipalities = db.get_all_municipalities()

        muni_by_daira = {}
        for m in all_municipalities:
            muni_by_daira.setdefault(m.daira_id, []).append(m)

        for daira in dairas:
            generate_roster(year, month, daira.id)

        pharmacist_dict = db.get_all_pharmacists_dict()
        all_duties = db.get_duties_for_month_bulk(year, month)

        muni_to_daira = {m.id: m.daira_id for m in all_municipalities}
        duty_by_daira = {}
        for d in all_duties:
            daira_id = muni_to_daira.get(d.municipality_id)
            if daira_id:
                key = (daira_id, d.date.isoformat(), d.municipality_id)
                duty_by_daira.setdefault(key, []).append(d)

        all_dairas_data = []
        day_names_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        day_names_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]

        for daira in dairas:
            municipalities = muni_by_daira.get(daira.id, [])
            if not municipalities:
                continue

            days = get_days_in_month(year, month)
            table_data = []
            for d in days:
                day_duties_grouped = []
                for muni in municipalities:
                    key = (daira.id, d.isoformat(), muni.id)
                    duties = duty_by_daira.get(key, [])
                    day_duties_grouped.append(duties)

                table_data.append((
                    d,
                    day_names_fr[d.weekday()],
                    day_names_ar[d.weekday()],
                    day_duties_grouped
                ))

            all_dairas_data.append((daira, table_data, municipalities))

        pdf_bytes = generate_batch_roster_pdf(year, month, all_dairas_data, pharmacist_dict)

        filename = f"Garde_Toutes_Dairas_{calendar.month_name[month]}_{year}.pdf"

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/roster/preview', methods=['GET'])
@login_required
def get_roster_preview():
    month = int(request.args.get('month', 2))
    year = int(request.args.get('year', 2026))
    daira_id = request.args.get('daira_id', '1')

    duties = db.get_duties_for_month(year, month, daira_id)
    duties.sort(key=lambda d: (d.date, d.shift_type))

    result = []
    for d in duties:
        ph = db.get_pharmacist(d.pharmacist_id)
        muni = db.get_municipality(d.municipality_id)
        result.append({
            "id": d.id,
            "date": d.date.isoformat(),
            "pharmacist": ph.name_fr if ph else "",
            "municipality": muni.name_fr if muni else "",
            "shift_type": d.shift_type,
            "is_holiday": d.is_holiday,
        })

    return jsonify(result)


@app.route('/api/duties/<id>', methods=['DELETE', 'PUT'])
@login_required
def manage_duty(id):
    duty = db.get_duty(id)
    if not duty:
        return jsonify({"error": "Not found"}), 404

    if request.method == 'DELETE':
        db._delete("duty_schedule", id)
        return jsonify({"message": "Duty schedule deleted"})

    if request.method == 'PUT':
        data = request.json
        update_data = {}
        if 'pharmacist_id' in data:
            update_data['pharmacist_id'] = data['pharmacist_id']
        if 'shift_type' in data:
            update_data['shift_type'] = data['shift_type']
        if update_data:
            db._update("duty_schedule", id, update_data)
        return jsonify({"message": "Duty schedule updated"})


@app.route('/api/dairas', methods=['GET', 'POST'])
@app.route('/api/dairas/<id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_dairas(id=None):
    if request.method == 'POST':
        data = request.json
        d = db.create_daira(name_ar=data['name_ar'], name_fr=data['name_fr'])
        return jsonify({"message": "Daira created", "id": d.id}), 201

    if id:
        daira = db.get_daira(id)
        if not daira:
            return jsonify({"error": "Not found"}), 404

        if request.method == 'GET':
            return jsonify({"id": daira.id, "name_ar": daira.name_ar, "name_fr": daira.name_fr})
        if request.method == 'PUT':
            data = request.json
            db.update_daira(id, name_ar=data.get('name_ar'), name_fr=data.get('name_fr'))
            return jsonify({"message": "Daira updated"})
        if request.method == 'DELETE':
            db.delete_daira(id)
            return jsonify({"message": "Daira deleted"})

    dairas = db.get_all_dairas()
    return jsonify([{"id": d.id, "name_ar": d.name_ar, "name_fr": d.name_fr} for d in dairas])


@app.route('/api/municipalities', methods=['GET', 'POST'])
@app.route('/api/municipalities/<id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_municipalities(id=None):
    if request.method == 'POST':
        data = request.json
        m = db.create_municipality(name_ar=data['name_ar'], name_fr=data['name_fr'], daira_id=str(data['daira_id']))
        return jsonify({"message": "Municipality created", "id": m.id}), 201

    if id:
        muni = db.get_municipality(id)
        if not muni:
            return jsonify({"error": "Not found"}), 404

        if request.method == 'GET':
            return jsonify({"id": muni.id, "name_ar": muni.name_ar, "name_fr": muni.name_fr, "daira_id": muni.daira_id})
        if request.method == 'PUT':
            data = request.json
            db.update_municipality(id,
                                   name_ar=data.get('name_ar'),
                                   name_fr=data.get('name_fr'),
                                   daira_id=data.get('daira_id'))
            return jsonify({"message": "Municipality updated"})
        if request.method == 'DELETE':
            db.delete_municipality(id)
            return jsonify({"message": "Municipality deleted"})

    daira_id = request.args.get('daira_id')
    if daira_id:
        munis = db.get_municipalities_by_daira(daira_id)
    else:
        munis = db.get_all_municipalities()
    return jsonify([{"id": m.id, "name_ar": m.name_ar, "name_fr": m.name_fr, "daira_id": m.daira_id} for m in munis])


@app.route('/api/pharmacists/import-excel', methods=['POST'])
@login_required
def import_pharmacists_excel():
    muni_id = request.form.get('municipality_id')
    if not muni_id:
        return jsonify({"error": "Municipality ID is required"}), 400

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        df = pd.read_excel(file)

        name_col = next((c for c in df.columns if 'Nom_fr' in c.lower()), df.columns[0])
        addr_col = next((c for c in df.columns if 'adrs' in c.lower()),
                        df.columns[1] if len(df.columns) > 1 else None)
        order_col = next((c for c in df.columns if 'order' in c.lower() or 'ordre' in c.lower()),
                         df.columns[2] if len(df.columns) > 2 else None)

        imported_count = 0
        for _, row in df.iterrows():
            name = str(row[name_col]).strip()
            if not name or name.lower() == 'nan':
                continue

            addr = str(row[addr_col]).strip() if addr_col and not pd.isna(row[addr_col]) else ""
            order = int(row[order_col]) if order_col and not pd.isna(row[order_col]) else 0

            db.create_pharmacist(
                name_fr=name,
                address_fr=addr,
                municipality_id=str(muni_id),
                rotation_order=order,
            )
            imported_count += 1

        return jsonify({"message": f"Successfully imported {imported_count} pharmacists"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/pharmacists', methods=['GET', 'POST'])
@app.route('/api/pharmacists/<id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def manage_pharmacists(id=None):
    if request.method == 'POST':
        data = request.json
        p = db.create_pharmacist(
            name_fr=data['name_fr'],
            address_fr=data.get('address_fr', ''),
            municipality_id=str(data['municipality_id']),
            rotation_order=data.get('rotation_order', 0),
        )
        return jsonify({"message": "Pharmacist created", "id": p.id}), 201

    if id:
        p = db.get_pharmacist(id)
        if not p:
            return jsonify({"error": "Not found"}), 404

        if request.method == 'GET':
            return jsonify({
                "id": p.id, "name_fr": p.name_fr,
                "address_fr": p.address_fr, "municipality_id": p.municipality_id,
                "rotation_order": p.rotation_order
            })
        if request.method == 'PUT':
            data = request.json
            db.update_pharmacist(id,
                                 name_fr=data.get('name_fr'),
                                 address_fr=data.get('address_fr'),
                                 municipality_id=data.get('municipality_id'),
                                 rotation_order=data.get('rotation_order'))
            return jsonify({"message": "Pharmacist updated"})
        if request.method == 'DELETE':
            db.delete_pharmacist(id)
            return jsonify({"message": "Pharmacist deleted"})

    muni_id = request.args.get('municipality_id')
    if muni_id:
        pharmacists = db.get_pharmacists_by_municipality(muni_id)
    else:
        pharmacists = db.get_all_pharmacists()
    return jsonify([{
        "id": p.id,
        "name_fr": p.name_fr,
        "address_fr": p.address_fr,
        "municipality_id": p.municipality_id,
        "rotation_order": p.rotation_order
    } for p in pharmacists])


@app.route('/api/vacations', methods=['GET', 'POST'])
@app.route('/api/vacations/<id>', methods=['DELETE'])
@login_required
def manage_vacations(id=None):
    if request.method == 'POST':
        data = request.json
        v = db.create_vacation(
            pharmacist_id=str(data['pharmacist_id']),
            start_date=datetime.strptime(data['start_date'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(data['end_date'], '%Y-%m-%d').date(),
        )
        return jsonify({"message": "Vacation recorded", "id": v.id}), 201

    if id and request.method == 'DELETE':
        db.delete_vacation(id)
        return jsonify({"message": "Vacation deleted"})

    ph_id = request.args.get('pharmacist_id')
    if ph_id:
        vacations = db.get_vacations_by_pharmacist(ph_id)
    else:
        docs = list(db._col("vacation").stream())
        vacations = [Vacation.from_dict(d.id, d.to_dict()) for d in docs]
    return jsonify([{
        "id": v.id,
        "pharmacist_id": v.pharmacist_id,
        "start_date": v.start_date.isoformat(),
        "end_date": v.end_date.isoformat()
    } for v in vacations])


@app.route('/')
@login_required
def index():
    return render_template('index.html')


class UserObject:
    def __init__(self, user: User):
        self._user = user

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self._user.id

    @property
    def username(self):
        return self._user.username

    def check_password(self, password):
        return self._user.check_password(password)


if __name__ == '__main__':
    def open_browser():
        webbrowser.open_new('http://127.0.0.1:5000/')

    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.5, open_browser).start()

    app.run(host='0.0.0.0', port=5000, debug=False)
