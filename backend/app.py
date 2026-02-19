import os
import joblib
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Configuration DB via variable d'environnement
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

def init_db():
    """Initialise la base de données et crée Dr_Moussa si inexistant."""
    print("Initialisation de la base de données...")
    try:
        with engine.connect() as conn:
            # 1. Création des tables si elles n'existent pas
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) DEFAULT 'expert'
                );
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS diagnostics (
                    id SERIAL PRIMARY KEY,
                    patient_id VARCHAR(50) NOT NULL,
                    patient_age FLOAT,
                    bmi FLOAT,
                    hba1c_level FLOAT,
                    blood_glucose_level FLOAT,
                    prediction INTEGER,
                    probability FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()

            # 2. Vérification et création de Dr_Moussa
            check_user = conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": "Dr_Moussa"}).fetchone()
            
            if not check_user:
                print("Création du compte Dr_Moussa...")
                hashed_pw = generate_password_hash('master2_pass')
                conn.execute(
                    text("INSERT INTO users (username, password, role) VALUES (:u, :p, :r)"),
                    {"u": "Dr_Moussa", "p": hashed_pw, "r": "admin"}
                )
                conn.commit()
                print("Dr_Moussa a été créé avec succès.")
            else:
                print("Dr_Moussa existe déjà dans la base.")
                
    except Exception as e:
        print(f"Erreur lors de l'initialisation : {e}")

# Chargement du modèle
try:
    model = joblib.load('diabetes_model.pkl')
    scaler = joblib.load('scaler.pkl')
    metadata = joblib.load('model_metadata.pkl')
    features = metadata['feature_columns']
except Exception as e:
    print(f"Erreur chargement modèle : {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    try:
        with engine.connect() as conn:
            query = text("SELECT username, password, role FROM users WHERE username = :u")
            user = conn.execute(query, {"u": data.get('username')}).fetchone()
        
        if user and check_password_hash(user[1], data.get('password')):
            return jsonify({"status": "success", "username": user[0], "role": user[2]}), 200
        return jsonify({"message": "Identifiants invalides"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    try:
        gender_map = {'Male': 1, 'Female': 0}
        smoking_map = {'never': 0, 'No Info': 0, 'former': 1, 'ever': 1, 'not current': 1, 'current': 2}

        input_data = {
            'gender_encoded': gender_map.get(data.get('gender'), 1),
            'age': float(data.get('age', 40)),
            'hypertension': int(data.get('hypertension', 0)),
            'heart_disease': int(data.get('heart_disease', 0)),
            'smoking_encoded': smoking_map.get(data.get('smoking_history', 'never'), 0),
            'bmi': float(data.get('bmi', 25.0)),
            'HbA1c_level': float(data.get('HbA1c_level', 5.5)),
            'blood_glucose_level': float(data.get('blood_glucose_level', 100))
        }

        df_input = pd.DataFrame([input_data])[features]
        X_scaled = scaler.transform(df_input)
        prediction = int(model.predict(X_scaled)[0])
        probability = float(model.predict_proba(X_scaled)[0][1])

        with engine.connect() as conn:
            conn.execute(
                text("""INSERT INTO diagnostics 
                    (patient_id, patient_age, bmi, hba1c_level, blood_glucose_level, prediction, probability) 
                    VALUES (:pid, :a, :b, :h, :g, :p, :pr)"""),
                {"pid": data.get('patient_id'), "a": input_data['age'], "b": input_data['bmi'],
                 "h": input_data['HbA1c_level'], "g": input_data['blood_glucose_level'],
                 "p": prediction, "pr": probability}
            )
            conn.commit()
        return jsonify({'prediction': prediction, 'probability': probability})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/<patient_id>', methods=['GET'])
def get_history(patient_id):
    try:
        with engine.connect() as conn:
            query = text("""SELECT created_at as date, blood_glucose_level as glucose, 
                            hba1c_level as hba1c, bmi as imc, prediction as result 
                            FROM diagnostics WHERE patient_id = :pid ORDER BY created_at DESC""")
            results = conn.execute(query, {"pid": patient_id}).fetchall()
            return jsonify([dict(row._mapping) for row in results])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_user', methods=['POST'])
def add_user():
    data = request.json
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""INSERT INTO users (username, password, role) 
                    VALUES (:u, :p, :r)"""),
                {"u": data.get('username'), "p": generate_password_hash(data.get('password')), "r": data.get('role')}
            )
            conn.commit()
        return jsonify({"message": "User added successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()  # Lancement auto de l'initialisation
    app.run(host='0.0.0.0', port=5000)
