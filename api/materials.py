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
    material_type = data.get('type')
    
    # Create material
    material = MaterialBank(
        title=data.get('title'),
        type=material_type,
        description=data.get('description', ''),
        created_by=current_user.id
    )
    db.session.add(material)
    db.session.flush()  # Get material.id
    
    # Handle different material types
    if material_type == 'grammar':
        # Grammar: traditional questions with options
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
    
    elif material_type == 'writing_logic':
        # Writing logic chain: single question with essay data
        question = Question(
            material_id=material.id,
            sequence=1,
            question_type='writing_logic',
            content=data.get('essay_full'),  # Full essay
            hint=data.get('essay_blank'),  # Blank version with labels
            reference_answer=data.get('essay_answers')  # Answer list
        )
        db.session.add(question)
    
    elif material_type == 'speaking_reading':
        # Speaking reading: single question with vocabulary, patterns, and paragraph
        question = Question(
            material_id=material.id,
            sequence=1,
            question_type='speaking_reading',
            content=data.get('vocabulary', ''),  # Vocabulary expressions
            hint=data.get('sentence_patterns', ''),  # Sentence patterns
            reference_answer=data.get('sample_paragraph', '')  # Sample paragraph
        )
        db.session.add(question)
    
    elif material_type == 'speaking_part1':
        # Speaking Part 1: multiple questions, each as a separate record
        questions_text = data.get('part1_questions', '')
        questions_list = _parse_speaking_part1(questions_text)
        if not questions_list:
            questions_list = [q.strip() for q in questions_text.strip().split('\n') if q.strip()]
        
        for i, question_text in enumerate(questions_list, 1):
            question = Question(
                material_id=material.id,
                sequence=i,
                question_type='speaking_part1',
                content=question_text
            )
            db.session.add(question)
    
    elif material_type == 'speaking_part2':
        # Speaking Part 2: single question with topic card
        question = Question(
            material_id=material.id,
            sequence=1,
            question_type='speaking_part2',
            content=data.get('part2_topic')  # Topic card text
        )
        db.session.add(question)

    elif material_type == 'speaking_part2_3':
        # Speaking Part 2+3: multiple topic cards, each stored as one question
        cards_text = data.get('part23_topics', '')
        cards = _parse_speaking_part23(cards_text)
        for i, card in enumerate(cards, 1):
            question = Question(
                material_id=material.id,
                sequence=i,
                question_type='speaking_part2_3',
                content=card,
            )
            db.session.add(question)
    
    elif material_type == 'translation':
        # Translation exercise: single question with sentence, skeleton, grammar, and reference
        question = Question(
            material_id=material.id,
            sequence=1,
            question_type='translation',
            content=data.get('sentence', ''),  # Original English sentence
            hint=data.get('skeleton', ''),  # Sentence skeleton structure
            explanation=data.get('grammar', ''),  # Grammar points
            reference_answer=data.get('reference', '')  # Reference translation
        )
        db.session.add(question)
    
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
    elif material.type == 'speaking_part1' and data.get('part1_questions'):
        Question.query.filter_by(material_id=material_id).delete()
        questions_list = _parse_speaking_part1(data.get('part1_questions', ''))
        if not questions_list:
            questions_list = [q.strip() for q in data.get('part1_questions', '').split('\n') if q.strip()]
        for i, question_text in enumerate(questions_list, 1):
            question = Question(
                material_id=material.id,
                sequence=i,
                question_type='speaking_part1',
                content=question_text
            )
            db.session.add(question)
    elif material.type == 'speaking_part2' and data.get('part2_topic'):
        Question.query.filter_by(material_id=material_id).delete()
        question = Question(
            material_id=material.id,
            sequence=1,
            question_type='speaking_part2',
            content=data.get('part2_topic')
        )
        db.session.add(question)
    elif material.type == 'speaking_part2_3' and data.get('part23_topics'):
        Question.query.filter_by(material_id=material_id).delete()
        cards = _parse_speaking_part23(data.get('part23_topics', ''))
        for i, card in enumerate(cards, 1):
            question = Question(
                material_id=material.id,
                sequence=i,
                question_type='speaking_part2_3',
                content=card,
            )
            db.session.add(question)
    
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

def _parse_speaking_part1(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or '').split('\n')]
    questions: list[str] = []
    current_topic = ''
    has_topic = False

    for line in lines:
        if not line:
            continue

        header_match = re.match(r'^(\d+)[.、)]\s*(.+)$', line)
        if header_match:
            current_topic = header_match.group(2).strip()
            has_topic = True
            continue

        bullet_match = re.match(r'^[*•\-]\s*(.+)$', line)
        if bullet_match:
            question_text = bullet_match.group(1).strip()
        else:
            question_text = line

        if not question_text:
            continue

        if has_topic and current_topic:
            question_text = f"{current_topic} - {question_text}"
        questions.append(question_text)

    return questions


def _looks_like_part23_title(line: str) -> bool:
    text = (line or "").strip()
    if not text:
        return False
    lower = text.lower()

    # Not a card title
    if text.startswith(('*', '•', '-', '·')):
        return False
    if re.match(r"^part\s*3\b", lower):
        return False
    if re.match(r"^you should say[:：]?$", lower):
        return False
    if re.match(r"^describe\b", lower):
        return False
    if re.search(r"[?？!！。]$", text):
        return False

    # Typical title patterns
    if re.match(r"^\d+[.)、]\s*", text):
        return True
    if re.search(r"[（(].+[)）]", text):
        return True
    if re.search(r"[\u4e00-\u9fff]", text) and len(text) <= 40:
        return True
    if re.match(r"^[A-Z][A-Za-z0-9/&,'\-\s]{2,40}$", text):
        return True
    return False


def _parse_speaking_part23(text: str) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []

    lines = raw.split("\n")
    cards: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current and current[-1] != "":
                current.append("")
            continue

        if _looks_like_part23_title(stripped) and current:
            block = "\n".join(current).strip()
            if block:
                cards.append(block)
            current = []

        current.append(stripped)

    if current:
        block = "\n".join(current).strip()
        if block:
            cards.append(block)

    if cards:
        return cards

    blocks = re.split(r"\n\s*\n+", raw)
    return [block.strip() for block in blocks if block.strip()]

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
    
    # Normalize text: replace Chinese punctuation with English
    text = text.replace('：', ':').replace('、', '.')
    
    # Strategy 1: Look for multiple choice patterns (multiple on one line)
    # e.g. "1. A 2. B" or "7. B/C"
    # Regex explanation:
    # (\d+)       : Capture Group 1 - Question number
    # \s*[.]\s*   : Dot separator with optional whitespace
    # (?:Answer:)? : Optional "Answer:" prefix
    # \s*         : Optional whitespace
    # ([A-E]+(?:/[A-E]+)*) : Capture Group 2 - Answer (e.g. "A", "AB", "B/C")
    choice_matches = re.findall(r'(\d+)\s*[.]\s*(?:Answer:)?\s*([A-E]+(?:/[A-E]+)*)', text, re.IGNORECASE)
    
    for num_str, ans_str in choice_matches:
        answers[int(num_str)] = ans_str.upper()
    
    # Strategy 2: Look for text answers (one per line)
    # This handles "1. The government built..."
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line looks like it contains multiple choice answers (handled by Strategy 1)
        # e.g. "1. A 2. B" - we skip these lines to avoid overwriting with partial text
        if re.search(r'\d+\s*[.]\s*[A-E]\s+\d+', line):
            continue
            
        # Match "Number. Content"
        match = re.match(r'^(\d+)\s*[.]\s*(.+)$', line)
        if match:
            seq = int(match.group(1))
            content = match.group(2).strip()
            
            # Only use this if we haven't found a choice answer for this sequence
            # OR if the content is clearly longer than a choice answer (e.g. > 5 chars)
            # This prevents "1. A" (text match) from overwriting "1. A" (choice match), which is fine,
            # but helps if Strategy 1 missed something.
            if seq not in answers or len(content) > 5:
                # Special case: if content is just "A" or "B", treat as choice
                if re.match(r'^[A-E]$', content, re.IGNORECASE):
                    answers[seq] = content.upper()
                else:
                    answers[seq] = content
    
    return jsonify({"ok": True, "answers": answers})
