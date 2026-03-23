import os
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get('APP_SECRET_KEY', 'dev-secret-key')

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

PADDLE_API_KEY = os.environ.get('PADDLE_API_KEY', '')
PADDLE_PRICE_ID = os.environ.get('PADDLE_PRICE_ID', '')
PADDLE_SANDBOX = os.environ.get('PADDLE_SANDBOX', 'true').lower() == 'true'
PLAUSIBLE_DOMAIN = os.environ.get('PLAUSIBLE_DOMAIN', '')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT,
            frequency_days INTEGER NOT NULL DEFAULT 3,
            last_watered DATE,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS watering_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            watered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plant_id) REFERENCES plants(id)
        )
    ''')
    conn.commit()
    conn.close()


def get_next_watering(last_watered, frequency_days):
    if not last_watered:
        return date.today()
    if isinstance(last_watered, str):
        last_watered = date.fromisoformat(last_watered)
    return last_watered + timedelta(days=frequency_days)


def get_status(next_watering):
    today = date.today()
    if next_watering <= today:
        return 'overdue'
    elif next_watering == today + timedelta(days=1):
        return 'due_soon'
    return 'ok'


@app.route('/')
def index():
    conn = get_db()
    plants = conn.execute('SELECT * FROM plants ORDER BY name').fetchall()
    conn.close()

    plants_data = []
    for p in plants:
        next_water = get_next_watering(p['last_watered'], p['frequency_days'])
        status = get_status(next_water)
        plants_data.append({
            'id': p['id'],
            'name': p['name'],
            'species': p['species'],
            'frequency_days': p['frequency_days'],
            'last_watered': p['last_watered'],
            'notes': p['notes'],
            'next_watering': next_water.isoformat(),
            'status': status,
        })

    plants_data.sort(key=lambda x: x['next_watering'])

    return render_template('index.html',
                           plants=plants_data,
                           paddle_price_id=PADDLE_PRICE_ID,
                           paddle_sandbox=PADDLE_SANDBOX,
                           plausible_domain=PLAUSIBLE_DOMAIN)


@app.route('/add', methods=['POST'])
def add_plant():
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    try:
        frequency_days = max(1, int(request.form.get('frequency_days', 3)))
    except (ValueError, TypeError):
        frequency_days = 3
    last_watered = request.form.get('last_watered', '') or None
    notes = request.form.get('notes', '').strip()

    if name:
        conn = get_db()
        conn.execute(
            'INSERT INTO plants (name, species, frequency_days, last_watered, notes) VALUES (?, ?, ?, ?, ?)',
            (name, species, frequency_days, last_watered, notes)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('index'))


@app.route('/water/<int:plant_id>', methods=['POST'])
def water_plant(plant_id):
    today = date.today().isoformat()
    conn = get_db()
    conn.execute('UPDATE plants SET last_watered = ? WHERE id = ?', (today, plant_id))
    conn.execute('INSERT INTO watering_log (plant_id) VALUES (?)', (plant_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/delete/<int:plant_id>', methods=['POST'])
def delete_plant(plant_id):
    conn = get_db()
    conn.execute('DELETE FROM watering_log WHERE plant_id = ?', (plant_id,))
    conn.execute('DELETE FROM plants WHERE id = ?', (plant_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/edit/<int:plant_id>', methods=['POST'])
def edit_plant(plant_id):
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    try:
        frequency_days = max(1, int(request.form.get('frequency_days', 3)))
    except (ValueError, TypeError):
        frequency_days = 3
    last_watered = request.form.get('last_watered', '') or None
    notes = request.form.get('notes', '').strip()

    if name:
        conn = get_db()
        conn.execute(
            'UPDATE plants SET name=?, species=?, frequency_days=?, last_watered=?, notes=? WHERE id=?',
            (name, species, frequency_days, last_watered, notes, plant_id)
        )
        conn.commit()
        conn.close()
    return redirect(url_for('index'))


@app.route('/success')
def success():
    return render_template('success.html', plausible_domain=PLAUSIBLE_DOMAIN)


@app.route('/cancel')
def cancel():
    return render_template('cancel.html', plausible_domain=PLAUSIBLE_DOMAIN)


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))


init_db()
