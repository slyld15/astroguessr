from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from models.user_model import User, UserRole, Base
from config.db_config import SessionLocal, engine
from utils.security import hash_password, verify_password, create_access_token

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/auth")

Base.metadata.create_all(bind=engine)

@auth_bp.route("/register", methods=["POST"])

def register():
    data= request.get_json()
    first_name= data.get("first_name")
    last_name= data.get("last_name")
    username= data.get("username")
    email= data.get("email")
    password = data.get("password")
    role = data.get("role")

    if not first_name or not last_name or not username or not email or not password or not role:
        return jsonify({"error": "All fields including role are required"}), 400
    
    if role not in [r.value for r in UserRole]:
        return jsonify({"error": "Invalid role"}), 400
    
    db: Session = SessionLocal()

    if db.query(User).filter((User.username == username) | (User.email == email)).first():
        db.close()
        return jsonify({"error": "User already registered"}), 400
    
    new_user=User(first_name=first_name, last_name=last_name, username=username, email=email, 
                  hashed_password=hash_password(password), role=UserRole(role))
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()

    token = create_access_token({"sub": new_user.username, "role": new_user.role.value})
    return jsonify({"access_token": token, "role": new_user.role.value})

@auth_bp.route("/login", methods=["POST"])

def login():
    data=request.get_json()
    username=data.get("username")
    password=data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    db: Session = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if not user or not verify_password(password, user.hashed_password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return jsonify({"access_token": token, "role": user.role.value})