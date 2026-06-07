from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
import json, os
from datetime import datetime

app = Flask(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def load_json(path):
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def clubs_path(): return os.path.join(DATA_DIR, 'clubs.json')
def staff_path(club_id): return os.path.join(DATA_DIR, f'staff_{club_id}.json')
def shifts_path(club_id): return os.path.join(DATA_DIR, f'shifts_{club_id}.json')

# ── Главная ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    clubs = load_json(clubs_path())
    return render_template('index.html', clubs=clubs)

# ── Клубы ────────────────────────────────────────────────────────────────────

@app.route('/clubs')
def clubs():
    data = load_json(clubs_path())
    return render_template('clubs.html', clubs=data)

@app.route('/clubs/add', methods=['POST'])
def add_club():
    data = load_json(clubs_path())
    club_id = request.form['club_id'].strip().lower().replace(' ', '_')
    data[club_id] = {
        'name': request.form['name'],
        'has_hostess': True,
    }
    save_json(clubs_path(), data)
    return redirect(url_for('clubs'))

@app.route('/clubs/<club_id>/delete', methods=['POST'])
def delete_club(club_id):
    data = load_json(clubs_path())
    if club_id in data:
        del data[club_id]
        save_json(clubs_path(), data)
    return redirect(url_for('clubs'))

# ── Сотрудники ───────────────────────────────────────────────────────────────

ROLE_ORDER = ['Т', 'КМ', 'Х', 'Б', 'О', 'Г', 'УБ', 'Д', 'К', 'КАС', 'АДМ', 'ОХР']
ROLE_NAMES = {
    'Т': 'Танцовщица', 'КМ': 'Комфорка', 'Х': 'Хостес',
    'Б': 'Бармен', 'О': 'Официант', 'Г': 'Гоу-гоу',
    'УБ': 'Уборщица', 'Д': 'Диджей', 'К': 'Кальянщик',
    'КАС': 'Кассир', 'АДМ': 'Администратор', 'ОХР': 'Охрана',
}

@app.route('/clubs/<club_id>/staff')
def staff(club_id):
    clubs = load_json(clubs_path())
    club  = clubs.get(club_id, {})
    data  = load_json(staff_path(club_id))
    return render_template('staff.html', club_id=club_id, club=club, staff=data,
                           role_order=ROLE_ORDER, role_names=ROLE_NAMES)

@app.route('/clubs/<club_id>/staff/add', methods=['POST'])
def add_staff(club_id):
    data   = load_json(staff_path(club_id))
    number = request.form['number'].strip().upper()
    data[number] = {
        'name':     request.form['name'].strip(),
        'role':     request.form['role'].strip(),
        'guarantee': float(request.form.get('guarantee') or 0),
        'guarantee_custom': request.form.get('guarantee_custom', ''),
        'active':   True,
    }
    save_json(staff_path(club_id), data)
    return redirect(url_for('staff', club_id=club_id))

@app.route('/clubs/<club_id>/staff/<number>/toggle', methods=['POST'])
def toggle_staff(club_id, number):
    data = load_json(staff_path(club_id))
    if number in data:
        data[number]['active'] = not data[number].get('active', True)
        save_json(staff_path(club_id), data)
    return redirect(url_for('staff', club_id=club_id))

@app.route('/clubs/<club_id>/staff/<number>/delete', methods=['POST'])
def delete_staff(club_id, number):
    data = load_json(staff_path(club_id))
    if number in data:
        del data[number]
        save_json(staff_path(club_id), data)
    return redirect(url_for('staff', club_id=club_id))

# ── Смена ────────────────────────────────────────────────────────────────────

@app.route('/clubs/<club_id>/shift/new')
def new_shift(club_id):
    clubs = load_json(clubs_path())
    club  = clubs.get(club_id, {})
    data  = load_json(staff_path(club_id))
    active_staff = {k: v for k, v in data.items() if v.get('active', True)}
    by_role = {}
    for num, emp in active_staff.items():
        role = emp.get('role', '')
        if role not in by_role:
            by_role[role] = []
        by_role[role].append({'number': num, **emp})
    for role in by_role:
        by_role[role].sort(key=lambda x: x['number'])
    return render_template('new_shift.html', club_id=club_id, club=club,
                           by_role=by_role, role_order=ROLE_ORDER, role_names=ROLE_NAMES,
                           today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/clubs/<club_id>/shift/start', methods=['POST'])
def start_shift(club_id):
    date         = request.form['date']
    has_hostess  = request.form.get('has_hostess') == 'on'
    selected     = request.form.getlist('selected_staff')
    artel_km     = request.form.getlist('artel_km')
    artel_bo     = request.form.getlist('artel_bo')

    staff_data = load_json(staff_path(club_id))
    shifts     = load_json(shifts_path(club_id))

    shift_key = f"{club_id}_{date}"
    shifts[shift_key] = {
        'club_id':     club_id,
        'date':        date,
        'has_hostess': has_hostess,
        'staff':       {},
        'artel_km':    artel_km,
        'artel_bo':    artel_bo,
        'status':      'active',
    }

    for number in selected:
        if number in staff_data:
            emp = staff_data[number]
            shifts[shift_key]['staff'][number] = {
                **emp,
                'stavka':       0,
                'guarantee':    emp.get('guarantee', 0),
                'crazy':        0,
                'konsum':       0,
                'chai_zal':     0,
                'chai_vip':     0,
                'netmonet':     0,
                'shtraf':       0,
                'itogo':        0,
                'dolg_bn':      0,
                'dolg_nal':     0,
                'k_vplate':     0,
                'in_artel_km':  number in artel_km,
                'in_artel_bo':  number in artel_bo,
                'items':        [],
            }

    save_json(shifts_path(club_id), shifts)
    return redirect(url_for('shift_detail', club_id=club_id, shift_key=shift_key))

@app.route('/clubs/<club_id>/shift/<shift_key>')
def shift_detail(club_id, shift_key):
    clubs  = load_json(clubs_path())
    club   = clubs.get(club_id, {})
    shifts = load_json(shifts_path(club_id))
    shift  = shifts.get(shift_key, {})
    return render_template('shift.html', club_id=club_id, club=club,
                           shift=shift, shift_key=shift_key,
                           role_order=ROLE_ORDER, role_names=ROLE_NAMES)

# ── API для обновления ячеек ─────────────────────────────────────────────────

@app.route('/api/shift/<club_id>/<shift_key>/update_cell', methods=['POST'])
def update_cell(club_id, shift_key):
    data   = request.json
    shifts = load_json(shifts_path(club_id))
    shift  = shifts.get(shift_key, {})
    number = data.get('number')
    field  = data.get('field')
    value  = data.get('value')
    if number in shift.get('staff', {}):
        shift['staff'][number][field] = value
        # Пересчёт итого
        s = shift['staff'][number]
        earned = sum([
            s.get('stavka', 0), s.get('crazy', 0), s.get('konsum', 0),
            s.get('chai_zal', 0), s.get('chai_vip', 0), s.get('netmonet', 0),
        ]) - s.get('shtraf', 0)
        guarantee = s.get('guarantee', 0)
        itogo = max(earned, guarantee) if guarantee > 0 else earned
        s['itogo'] = itogo
        s['k_vplate'] = itogo - s.get('dolg_bn', 0) - s.get('dolg_nal', 0)
        shifts[shift_key] = shift
        save_json(shifts_path(club_id), shifts)
        return jsonify({'ok': True, 'itogo': itogo, 'k_vplate': s['k_vplate']})
    return jsonify({'ok': False})

if __name__ == '__main__':
    # Создаём Bad Boy по умолчанию
    if not os.path.exists(clubs_path()):
        save_json(clubs_path(), {
            'bad_boy': {'name': 'Bad Boy', 'has_hostess': True},
        })
    app.run(debug=True, port=5001)
