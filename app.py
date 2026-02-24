from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import sqlite3
import json
from datetime import datetime
import uuid
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kaka-secret-key'
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
                  sid TEXT)''')  # добавили session id
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
    
    emit('registered', {'computer_id': computer_id})

# WebSocket: получение команд от браузера
@socketio.on('send_command')
def handle_send_command(data):
    computer_id = data['computer_id']
    command = data['command']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Получаем session id компьютера
    result = c.execute("SELECT sid FROM computers WHERE id=?", (computer_id,)).fetchone()
    conn.close()
    
    if result and result[0]:
        # Отправляем команду конкретному компьютеру
        socketio.emit('command', {'command': command}, room=result[0])
        emit('command_sent', {'status': 'ok'})
    else:
        emit('command_sent', {'status': 'error', 'message': 'Computer offline'})

# WebSocket: результат от компьютера
@socketio.on('command_result')
def handle_command_result(data):
    computer_id = data['computer_id']
    command = data['command']
    result = data['result']
    
    # Можно сохранить в БД или отправить в браузер
    socketio.emit('command_done', {
        'computer_id': computer_id,
        'command': command,
        'result': result
    })

# WebSocket: отключение компьютера
@socketio.on('disconnect')
def handle_disconnect():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE computers SET status='offline' WHERE sid=?", (request.sid,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)
