"""Material Bank API for structured learning materials."""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from models import db, MaterialBank, Question, QuestionOption, StudentAnswer, Task
from datetime import datetime
import re

material_bp = Blueprint('material', __name__, url_prefix='/api/materials')


def require_teacher():
    """Decorator to ensure user isadvertis teacher/admin."""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if current_user.role not in ['teacher', 'admin', 'assistant']:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return None


# ============================================================================
# Material CRUD
# ============================================================================

@material_bp.route('', methods=['GET'])
@login_required
def list_materials():
    """Get list of materials with optional filtering."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    material_type = request.args.get('type')
    search = request.args.get('search', '').strip()
    
    query = MaterialBank.query.filter_by(is_deleted=False, is_active=True)
    
    if material_type:
        query = query.filter_by(type=material_type)
    
    if search:
        query = query.filter(MaterialBank.title.contains(search))
    
    query = query.order_by(MaterialBank.created_at.desc())
    materials = query.all()
    
    result = []
    for m in materials:
        question_count = Question.query.filter_by(material_id=m.id).count()
        result.append({
            "id": m.id,
            "title": m.title,
            "type": m.type,
            "description": m.description,
            "question_count": question_count,
            "created_at": m.created_at.strftime("%Y-%m-%d")
        })
    
    return jsonify({"ok": True, "materials": result})


@material_bp.route('/<int:material_id>', methods=['GET'])
@login_required
def get_material(material_id):
    """Get single material with questions."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    material = MaterialBank.query.filter_by(id=material_id, is_deleted=False).first()
    if not material:
        return jsonify({"ok": False, "error": "material_not_found"}), 404
    
    questions = Question.query.filter_by(material_id=material_id).order_by(Question.sequence).all()
    
    questions_data = []
    for q in questions:
        options = QuestionOption.query.filter_by(question_id=q.id).order_by(QuestionOption.option_key).all()
        questions_data.append({
            "id": q.id,
            "sequence": q.sequence,
            "question_type": q.question_type,
            "content": q.content,
            "reference_answer": q.reference_answer,
            "hint": q.hint,
            "points": q.points,
            "options": [{"key": opt.option_key, "text": opt.option_text} for opt in options]
        })
    
    return jsonify({
        "ok": True,
        "material": {
            "id": material.id,
            "title": material.title,
            "type": material.type,
            "description": material.description,
            "questions": questions_data
        }
    })


@material_bp.route('', methods=['POST'])
@login_required
def create_material():
    """Create new material with questions."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    data = request.get_json()
    
    # Create material
    material = MaterialBank(
        title=data.get('title'),
        type=data.get('type'),
        description=data.get('description', ''),
        created_by=current_user.id
    )
    db.session.add(material)
    db.session.flush()  # Get material.id
    
    # Create questions
    questions_data = data.get('questions', [])
    for q_data in questions_data:
        question = Question(
            material_id=material.id,
            sequence=q_data.get('sequence'),
            question_type=q_data.get('question_type', 'choice'),
            content=q_data.get('content'),
            reference_answer=q_data.get('reference_answer'),
            hint=q_data.get('hint'),
            points=q_data.get('points', 1)
        )
        db.session.add(question)
        db.session.flush()
        
        # Create options for choice questions
        if q_data.get('options'):
            for opt in q_data['options']:
                option = QuestionOption(
                    question_id=question.id,
                    option_key=opt['key'],
                    option_text=opt['text']
                )
                db.session.add(option)
    
    db.session.commit()
    
    return jsonify({"ok": True, "material_id": material.id})


@material_bp.route('/<int:material_id>', methods=['PUT'])
@login_required
def update_material(material_id):
    """Update material."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    material = MaterialBank.query.filter_by(id=material_id, is_deleted=False).first()
    if not material:
        return jsonify({"ok": False, "error": "material_not_found"}), 404
    
    data = request.get_json()
    
    # Update basic info
    if 'title' in data:
        material.title = data['title']
    if 'type' in data:
        material.type = data['type']
    if 'description' in data:
        material.description = data['description']
    
    # If questions are provided, replace all questions
    if 'questions' in data:
        # Delete existing questions (cascade will delete options)
        Question.query.filter_by(material_id=material_id).delete()
        
        # Create new questions
        questions_data = data.get('questions', [])
        for q_data in questions_data:
            question = Question(
                material_id=material.id,
                sequence=q_data.get('sequence'),
                question_type=q_data.get('question_type', 'choice'),
                content=q_data.get('content'),
                reference_answer=q_data.get('reference_answer'),
                hint=q_data.get('hint'),
                points=q_data.get('points', 1)
            )
            db.session.add(question)
            db.session.flush()
            
            # Create options for choice questions
            if q_data.get('options'):
                for opt in q_data['options']:
                    option = QuestionOption(
                        question_id=question.id,
                        option_key=opt['key'],
                        option_text=opt['text']
                    )
                    db.session.add(option)
    
    material.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"ok": True})


@material_bp.route('/<int:material_id>', methods=['DELETE'])
@login_required
def delete_material(material_id):
    """Soft delete material."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    material = MaterialBank.query.filter_by(id=material_id, is_deleted=False).first()
    if not material:
        return jsonify({"ok": False, "error": "material_not_found"}), 404
    
    material.is_deleted = True
    material.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"ok": True})


# ============================================================================
# Question Parsing Utilities
# ============================================================================

@material_bp.route('/parse', methods=['POST'])
@login_required
def parse_questions():
    """Parse questions from pasted text (Word content)."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    data = request.get_json()
    text = data.get('text', '')
    
    questions = []
    lines = text.split('\n')
    
    current_question = None
    current_options = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Match question number: "1. " or "1、"
        question_match = re.match(r'^(\d+)[.、]\s*(.+)$', line)
        if question_match:
            # Save previous question
            if current_question:
                current_question['options'] = current_options
                questions.append(current_question)
            
            # Start new question
            sequence = int(question_match.group(1))
            content = question_match.group(2)
            current_question = {
                'sequence': sequence,
                'content': content,
                'question_type': 'choice',
                'reference_answer': '',
                'points': 1
            }
            current_options = []
            continue
        
        # Match options: "A. " or "A、"
        option_match = re.match(r'^([A-D])[.、]\s*(.+)$', line)
        if option_match and current_question:
            option_key = option_match.group(1)
            option_text = option_match.group(2)
            current_options.append({'key': option_key, 'text': option_text})
            continue
        
        # Otherwise, append to current question content
        if current_question and not option_match:
            current_question['content'] += ' ' + line
    
    # Don't forget last question
    if current_question:
        current_question['options'] = current_options
        questions.append(current_question)
    
    return jsonify({"ok": True, "questions": questions})


@material_bp.route('/parse-answers', methods=['POST'])
@login_required
def parse_answers():
    """Parse answers from pasted text."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check
    
    data = request.get_json()
    text = data.get('text', '')
    
    answers = {}
    answers = {}
    
    # Normalize text: replace Chinese punctuation with English
    text = text.replace('：', ':').replace('、', '.')
    
    # Regex to find all "1. A" or "1. Answer: A" patterns
    # Handles multiple answers on one line
    matches = re.findall(r'(\d+)\s*[.]\s*(?:Answer:)?\s*([A-D])', text, re.IGNORECASE)
    
    for num_str, ans_str in matches:
        question_num = int(num_str)
        answers[question_num] = ans_str.upper()
    
    return jsonify({"ok": True, "answers": answers})
