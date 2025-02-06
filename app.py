from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
import openai
import os
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)

# Configurazione: ricordati di sostituire i valori con quelli reali
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin@localhost:5432/recipes'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'ax019321kmamldafldraklerj012i3al,smkamsa!'  # Cambiare in produzione
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Modelli
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    recipes = db.relationship('Recipe', backref='user', lazy=True)

class Recipe(db.Model):
    __tablename__ = 'recipes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_public = db.Column(db.Boolean, default=False)  # Flag per rendere la ricetta pubblica
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# Endpoint per la registrazione utente
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username già in uso"}), 400
    hashed_password = generate_password_hash(password)
    new_user = User(username=username, password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Utente registrato con successo"}), 201

# Endpoint per il login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"message": "Credenziali non valide"}), 401
    access_token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": access_token}), 200

# Recupera le ricette dell'utente loggato (include lo stato "is_public")
@app.route('/user/recipes', methods=['GET'])
@jwt_required()
def get_user_recipes():
    user_id = get_jwt_identity()
    recipes = Recipe.query.filter_by(user_id=user_id).all()
    recipes_data = [{
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "is_public": r.is_public
    } for r in recipes]
    return jsonify(recipes_data), 200

# Aggiungi una nuova ricetta (l'utente può decidere se renderla pubblica)
@app.route('/user/recipes', methods=['POST'])
@jwt_required()
def add_recipe():
    user_id = get_jwt_identity()
    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    is_public = data.get('is_public', False)
    new_recipe = Recipe(title=title, description=description, is_public=is_public, user_id=user_id)
    db.session.add(new_recipe)
    db.session.commit()
    return jsonify({"message": "Ricetta aggiunta con successo"}), 201

# Rimuove una ricetta (solo se l'utente è proprietario)
@app.route('/user/recipes/<int:recipe_id>', methods=['DELETE'])
@jwt_required()
def delete_recipe(recipe_id):
    user_id = get_jwt_identity()
    recipe = Recipe.query.get(recipe_id)

    if recipe is None or recipe.user_id != int(user_id):
        return jsonify({"message": "Ricetta non trovata o non autorizzata"}), 404
    db.session.delete(recipe)
    db.session.commit()
    return jsonify({"message": "Ricetta rimossa con successo"}), 200

# Endpoint per togglare lo stato pubblico di una ricetta
@app.route('/user/recipes/<int:recipe_id>/toggle_public', methods=['PUT'])
@jwt_required()
def toggle_public(recipe_id):
    user_id = get_jwt_identity()
    recipe = Recipe.query.get(recipe_id)
    if recipe is None or recipe.user_id != int(user_id):
        return jsonify({"message": "Ricetta non trovata o non autorizzata"}), 404
    data = request.get_json()
    if "is_public" not in data:
        return jsonify({"message": "Parametro is_public mancante"}), 400
    recipe.is_public = data["is_public"]
    db.session.commit()
    return jsonify({"message": "Stato pubblico aggiornato", "is_public": recipe.is_public}), 200

# Recupera solo le ricette pubbliche
@app.route('/recipes/public', methods=['GET'])
def get_public_recipes():
    recipes = Recipe.query.filter_by(is_public=True).all()
    recipes_data = []
    for r in recipes:
        recipes_data.append({
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "username": r.user.username
        })
    return jsonify(recipes_data), 200

# Pagina “Mix It Up”: utilizza solo ricette pubbliche per il mix
@app.route('/recepies/mix', methods=['GET'])
def mix_it_up():
    # Recupera tutte le ricette pubbliche dal database
    recipes = Recipe.query.filter_by(is_public=True).all()
    if not recipes:
        return jsonify({"message": "Nessuna ricetta pubblica disponibile per il mix"}), 404

    # Costruisce il prompt includendo le ricette pubbliche
    prompt = "Combina in modo creativo le seguenti ricette e proponi una nuova ricetta innovativa:\n\n"
    for recipe in recipes:
        prompt += f"- {recipe.title}: {recipe.description}\n"
    prompt += "\nRispondi con un titolo e una descrizione per la nuova ricetta."

    # Imposta la tua API key da una variabile d'ambiente caricata con dotenv
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        return jsonify({"message": "API Key non configurata. Imposta la variabile OPENAI_API_KEY nel file .env."}), 500

    try:
        # Chiamata all'API di OpenAI con il modello GPT-3.5-turbo
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Sei un esperto chef creativo."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200,
        )
    except Exception as e:
        return jsonify({"message": "Errore durante la generazione della ricetta", "error": str(e)}), 500

    # Estrae il testo generato dalla risposta
    creative_recipe_text = response["choices"][0]["message"]["content"].strip()
    
    return jsonify({"creative_recipe": creative_recipe_text}), 200

if __name__ == '__main__':
    app.run(debug=True)
