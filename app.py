import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room, emit
from pymongo import MongoClient
from dotenv import load_dotenv
from face_model import analyze_face
import cv2
import numpy as np
import datetime
from datetime import timedelta
from bson import ObjectId
import time
from threading import Thread

# Load biến môi trường
load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

# Kết nối MongoDB
db = MongoClient(os.getenv('MONGO_URI')).friendapp
users = db.users
sessions = db.sessions

# Index cho matching
users.create_index([('age',1), ('gender',1), ('race',1), ('status',1)])

# Trang chính
@app.route('/')
def index():
    return render_template('index.html')

# Trang video
@app.route('/video')
def video():
    return render_template('video.html')

# API: Phân tích ảnh khuôn mặt
@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    image = request.files.get('image')
    if not image:
        return jsonify({'error': 'No image'}), 400
    attrs = analyze_face(read_image_from_request(image))
    return jsonify(attrs)

def read_image_from_request(image_file):
    image_bytes = image_file.read()
    np_arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

# API: Đăng ký user và xếp hàng chờ
@app.route('/api/register', methods=['POST'])
def register():
    name = request.form.get('name')
    image = request.files.get('image')
    attrs = analyze_face(read_image_from_request(image))
    user = {
        'name': name,
        'age': attrs['age'],
        'gender': attrs['gender'],
        'race': attrs['race'],
        'status': 'waiting',
        'created_at': datetime.datetime.now(datetime.timezone.utc)
    }
    result = users.insert_one(user)
    user_id = str(result.inserted_id)
    return jsonify({'user_id': user_id, 'attrs': attrs})

connected_users = {}

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

# SocketIO: Xử lý signaling và matching
@socketio.on('join_queue')
def handle_join(data):
    user_id = data['user_id']
    user = users.find_one({'_id': ObjectId(user_id)})
    if user:
        connected_users[request.sid] = {
            'user_id': user_id,
            'name': user.get('name', 'Ẩn danh')
        }
    users.update_one({'_id': ObjectId(user_id)}, {'$set': {'status': 'waiting'}})
    emit('queue_joined')
    try_match()

def try_match():
    waiting = list(users.find({'status': 'waiting'}).sort([
        ('age', 1),
        ('gender', 1),
        ('race', 1)
    ]))
    if len(waiting) < 2:
        return

    u1 = waiting[0]
    u1_data = users.find_one({'_id': u1['_id']})
    matched_before = set(u1_data.get('matched_ids', []))

    best_match_index = -1
    min_diff = float('inf')

    for i in range(1, len(waiting)):
        u2 = waiting[i]

        # ❌ Bỏ qua nếu đã từng match nhau
        if str(u2['_id']) in matched_before:
            continue

        u2_data = users.find_one({'_id': u2['_id']})
        if u2_data and str(u1['_id']) in set(u2_data.get('matched_ids', [])):
            continue

        # ✅ Ưu tiên theo khoảng cách tuổi + giới tính + sắc tộc
        age_diff = abs(u1['age'] - u2['age'])
        score = age_diff * 0.5
        if u1['gender'] == u2['gender']:
            score -= 0.25
        if u1['race'] == u2['race']:
            score -= 0.25

        if score < min_diff:
            min_diff = score
            best_match_index = i

    if best_match_index != -1:
        u2 = waiting.pop(best_match_index)
        u1 = waiting.pop(0)
        room = str(ObjectId())

        users.update_many(
            {'_id': {'$in': [u1['_id'], u2['_id']]}},
            {'$set': {'status': 'in_call'}}
        )

        sessions.insert_one({
            'room': room,
            'users': [u1['_id'], u2['_id']],
            'start_time': datetime.datetime.now(datetime.timezone.utc)
        })

    
        users.update_one(
            {'_id': u1['_id']},
            {'$addToSet': {'matched_ids': str(u2['_id'])}}
        )
        users.update_one(
            {'_id': u2['_id']},
            {'$addToSet': {'matched_ids': str(u1['_id'])}}
        )

        socketio.emit('matched', {
            'room': room,
            'users': [str(u1['_id']), str(u2['_id'])]
        })


# Signaling: relay offer/answer and ICE
@socketio.on('signal')
def handle_signal(data):
    room = data['room']
    emit('signal', data, room=room, include_self=False)

@socketio.on('join_room')
def on_join(data):
    join_room(data['room'])

@socketio.on('leave_room')
def handle_leave(data):
    room = data.get('room')
    sid = request.sid
    leave_room(room)
    session = sessions.find_one({'room': room})
    if session:
        other_user_id = next((uid for uid in session['users'] if str(uid) != data.get('user_id')), None)
        if other_user_id:
            users.update_one({'_id': ObjectId(other_user_id)}, {'$set': {'status': 'waiting'}})
        sessions.delete_one({'_id': session['_id']})

    users.update_one({'_id': ObjectId(data.get('user_id'))}, {'$set': {'status': 'waiting'}})

    emit('partner_left', room=room, include_self=False)
    try_match()


@socketio.on('chat_message')
def handle_chat(data):
    sender = connected_users.get(request.sid, {}).get('name', 'Ẩn danh')
    emit('chat_message', {
        'sender': sender,
        'message': data['message']
    }, room=data['room'])

@socketio.on('disconnect')
def handle_disconnect():
    connected_users.pop(request.sid, None)
    emit('partner_left', room=request.sid)

def clean_inactive_users(db):
    while True:
        timeout = datetime.datetime.now(datetime.timezone.utc) - timedelta(seconds=1800)
        db.queue.delete_many({'last_active': {'$lt': timeout}})
        time.sleep(30)

if __name__ == '__main__':
    t = Thread(target=clean_inactive_users, args=(db,))
    t.daemon = True
    t.start()
    socketio.run(app, host='0.0.0.0', port=5000)