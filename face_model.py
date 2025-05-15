import cv2
import numpy as np
from tensorflow.keras.models import load_model
import os

# Load model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "ai_model/facereg2.keras")
model = load_model(MODEL_PATH)

# # Hàm detect và crop face
# face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
# def detect_and_crop_face(img):
#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     faces = face_cascade.detectMultiScale(gray, 1.3, 5)
#     if len(faces) == 0:
#         raise ValueError('No face detected')
#     x, y, w, h = faces[0]
#     return img[y:y+h, x:x+w]

# Preprocess và predict
def analyze_face(image):
        face, (x, y, w, h) = preprocess_image(image)
        predictions = model.predict(face)
    
        # Giả sử model trả về 3 outputs: age, gender, race
        age = predictions[0][0] * 100  # Giả sử tuổi được chuẩn hóa về [0,1]
        gender_prob = predictions[1][0]
        race_prob = predictions[2][0]
        
        # Xác định giới tính
        gender = "Nữ" if gender_prob[0] > 0.5 else "Nam"
        gender_confidence = max(gender_prob[0], 1 - gender_prob[0])
        
        # Xác định sắc tộc
        race_classes = ['White', 'Black', 'Asian', 'Indian', 'Others']
        race_idx = np.argmax(race_prob)
        race = race_classes[race_idx]
        race_confidence = race_prob[race_idx]
        
        return {
            'age': int(age),
            'gender': gender,
            'gender_confidence': float(gender_confidence),
            'race': race,
            'race_confidence': float(race_confidence),
            'face_coordinates': (int(x), int(y), int(w), int(h))
        }

def preprocess_image(img):
    # Chuyển sang grayscale để phát hiện khuôn mặt
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Sử dụng Haar cascade để phát hiện khuôn mặt
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    
    if len(faces) == 0:
        # Thử cascade khác nếu không phát hiện được
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
    
    if len(faces) == 0:
        print("Cảnh báo: Không phát hiện khuôn mặt rõ ràng, sẽ xử lý toàn bộ ảnh")
        face = cv2.resize(img, (128, 128))  # Thay đổi từ 224x224 thành 128x128
        face = face.astype('float32') / 255.0
        return np.expand_dims(face, axis=0), (0, 0, img.shape[1], img.shape[0])
    
    # Lấy khuôn mặt đầu tiên
    (x, y, w, h) = faces[0]
    face = img[y:y+h, x:x+w]
    
    # Resize về 128x128
    face = cv2.resize(face, (128, 128))
    
    # Chuẩn hóa pixel values
    face = face.astype('float32') / 255.0
    
    # Thêm batch dimension
    face = np.expand_dims(face, axis=0)
    
    return face, (x, y, w, h)