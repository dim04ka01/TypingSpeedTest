import socket
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
import time
import random
import os
import glob
import uuid
import html

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24).hex()
socketio = SocketIO(app, cors_allowed_origins="*")

# Глобальное хранилище текстов по ID сессии
text_samples = {}

def load_text_categories():
    base_path = 'texts'
    categories = {}
    
    for text_type in os.listdir(base_path):
        type_path = os.path.join(base_path, text_type)
        if not os.path.isdir(type_path):
            continue
            
        for language in os.listdir(type_path):
            lang_path = os.path.join(type_path, language)
            if not os.path.isdir(lang_path):
                continue
                
            for difficulty_file in os.listdir(lang_path):
                if difficulty_file.endswith('.txt'):
                    difficulty = difficulty_file.split('.')[0]
                    file_path = os.path.join(lang_path, difficulty_file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            if text_type == "words":
                                # Для слов: все слова из файла в один список
                                content = f.read().strip()
                                words = [word.strip() for word in content.split() if word.strip()]
                                key = f"{text_type}/{language}/{difficulty}"
                                categories[key] = words
                            else:
                                # Для текстов: разделение по строкам
                                content = f.read().strip()
                                texts = [t.strip() for t in content.split('\n') if t.strip()]
                                key = f"{text_type}/{language}/{difficulty}"
                                categories[key] = texts
                    except Exception as e:
                        print(f"Error loading {file_path}: {str(e)}")
    
    return categories

# Коллекция текстов для тестирования
TEXT_CATEGORIES = load_text_categories()

# Хранилище результатов
results_store = {}

# Функция для получения случайного текста по настройкам
def get_text_sample(text_type, language, difficulty, word_count=25):
    key = f"{text_type}/{language}/{difficulty}"
    samples = TEXT_CATEGORIES.get(key)
    
    if not samples:
        return "Текст не найден"
    
    if text_type == "words":
        # Выбираем случайные слова и объединяем в строку
        selected_words = random.sample(samples, min(word_count, len(samples)))
        return ' '.join(selected_words)
    else:
        return random.choice(samples)

def get_session_key():
    # Генерирует уникальный ключ сессии для текущего пользователя
    if 'session_key' not in session:
        session['session_key'] = str(uuid.uuid4())
    return session['session_key']

@app.route('/')
def index():
    session['test_id'] = str(uuid.uuid4())
    
    # Получаем текущие настройки
    text_type = session.get('text_type', 'text')
    language = session.get('language', 'russian')
    difficulty = session.get('difficulty', 'easy')
    
    # Генерируем текст
    word_count = 25 if text_type == "words" else 1
    text_sample = get_text_sample(text_type, language, difficulty, word_count)
    session_key = get_session_key()
    text_samples[session_key] = text_sample
    
    # Передаем настройки в шаблон
    return render_template('index.html', 
                           text_sample=text_sample,
                           settings={
                               'text_type': text_type,
                               'language': language,
                               'difficulty': difficulty
                           })

@app.route('/update_settings', methods=['POST'])
def update_settings():
    data = request.json
    session['text_type'] = data['text_type']
    session['language'] = data['language']
    session['difficulty'] = data['difficulty']
    
    # Генерируем новый текст
    word_count = 25 if data['text_type'] == "words" else 1
    new_text = get_text_sample(
        data['text_type'],
        data['language'],
        data['difficulty'],
        word_count
    )
    
    # Обновляем текст в хранилище
    session_key = get_session_key()
    text_samples[session_key] = new_text
    
    return jsonify({'new_text': new_text})

@app.route('/results')
def results():
    test_id = request.args.get('test_id')
    result = results_store.get(test_id)
    
    if not result:
        return redirect(url_for('index'))
    
    return render_template('results.html', result=result)

@socketio.on('connect')
def handle_connect():
    # При подключении создаем ключ сессии, если его нет
    if 'session_key' not in session:
        session['session_key'] = str(uuid.uuid4())

@socketio.on('disconnect')
def handle_disconnect(sid=None):
    """Обработчик отключения клиента"""
    try:
        # Получаем ключ сессии из HTTP-сессии
        session_key = session.get('session_key')
        
        # Очищаем хранилище
        if session_key and session_key in text_samples:
            del text_samples[session_key]
            print(f"Cleaned up resources for session: {session_key}")
    except Exception as e:
        print(f"Error during disconnect cleanup: {str(e)}")

@socketio.on('start_test')
def handle_start_test():
    # Получаем актуальный текст из хранилища
    session_key = session.get('session_key')
    current_text = text_samples.get(session_key, '')
    
    if not current_text:
        # Если текста нет - генерируем новый
        text_type = session.get('text_type', 'text')
        language = session.get('language', 'russian')
        difficulty = session.get('difficulty', 'easy')
        word_count = 25 if text_type == "words" else 1
        current_text = get_text_sample(text_type, language, difficulty, word_count)
        text_samples[session_key] = current_text
    
    # Сохраняем текст в сессии
    session['text_sample'] = current_text
    session['start_time'] = time.time()
    emit('test_started', {'status': 'success'})

@socketio.on('submit_results')
def handle_submit_results(data):
    end_time = time.time()
    elapsed_time = end_time - session.get('start_time', end_time)
    
    # Используем текст из сессии
    original_text = session.get('text_sample', '')
    typed_text = data.get('typed_text', '')
    
    # Расчет статистики
    stats = calculate_typing_stats(original_text, typed_text, elapsed_time)
    
    # Сохраняем результаты в хранилище
    test_id = session.get('test_id')
    if test_id:
        results_store[test_id] = stats
    
    # Отправляем результаты клиенту
    emit('test_results', {'test_id': test_id})

@socketio.on_error_default
def default_error_handler(e):
    print(f"Socket.IO error: {str(e)}")

def calculate_typing_stats(original, typed, elapsed):
    correct_chars = 0
    mistakes = []
    highlighted_text = []
    current_word = []
    in_word = False
    
    # Обрабатываем каждый символ оригинального текста
    for i, orig_char in enumerate(original):
        typed_char = typed[i] if i < len(typed) else None
        
        # Определяем статус символа
        if typed_char == orig_char:
            status = "correct"
            correct_chars += 1
        else:
            status = "mistake"
            actual = typed_char if typed_char is not None else "∅"
            mistakes.append({
                'position': i,
                'expected': orig_char,
                'actual': actual
            })
        
        # Формируем HTML для символа
        char_class = f"char {status}"
        tooltip = ""
        
        if status == "mistake":
            expected_escaped = html.escape(orig_char)
            actual_escaped = html.escape(typed_char) if typed_char is not None else "∅"
            tooltip = (f'<span class="tooltip">Ожидалось: "{expected_escaped}"<br>'
                       f'Введено: "{actual_escaped}"</span>')
        
        char_html = (f'<span class="{char_class}">'
                     f'{html.escape(orig_char)}{tooltip}'
                     f'</span>')
        
        # Определяем, находимся ли мы внутри слова
        is_space = orig_char.isspace()
        
        if not is_space:
            # Начало или продолжение слова
            current_word.append(char_html)
            in_word = True
        elif in_word:
            # Конец слова и начало пробела
            # Добавляем собранное слово
            highlighted_text.append(f'<span class="word">{"".join(current_word)}</span>')
            current_word = []
            in_word = False
            # Добавляем пробел
            highlighted_text.append(char_html)
        else:
            # Последовательные пробелы
            highlighted_text.append(char_html)
    
    # Добавляем последнее слово, если оно есть
    if current_word:
        highlighted_text.append(f'<span class="word">{"".join(current_word)}</span>')
    
    # Добавляем оставшуюся часть оригинального текста
    if len(typed) < len(original):
        for i in range(len(typed), len(original)):
            orig_char = original[i]
            char_class = "char missed"
            char_html = f'<span class="{char_class}">{html.escape(orig_char)}</span>'
            
            if orig_char.isspace():
                highlighted_text.append(char_html)
            else:
                if not current_word and i > 0 and not original[i-1].isspace():
                    # Начало нового слова после пропущенного пробела
                    current_word = []
                current_word.append(char_html)
        
        if current_word:
            highlighted_text.append(f'<span class="word">{"".join(current_word)}</span>')
    
    highlighted_text = ''.join(highlighted_text)
    
    # Рассчет статистики
    total_chars = len(original)
    words_typed = len(typed.split()) if typed else 0
    accuracy = (correct_chars / max(len(original), len(typed))) * 100 if total_chars > 0 else 0
    wpm = (len(typed) / 5) / elapsed * 60 if elapsed > 0 else 0
    cpm = (len(typed) / elapsed) * 60 if elapsed > 0 else 0
    
    return {
        'wpm': round(wpm, 2),
        'cpm': round(cpm, 2),
        'accuracy': round(accuracy, 2),
        'time_elapsed': round(elapsed, 2),
        'total_chars': len(typed),
        'mistakes': mistakes,
        'mistake_count': len(mistakes),
        'highlighted_text': highlighted_text
    }

if __name__ == '__main__':
    socketio.run(app, debug=True)