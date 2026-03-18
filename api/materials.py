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
                explanation=q_data.get('explanation', ''),
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


@material_bp.route('/parse-pdf', methods=['POST'])
@login_required
def parse_pdf():
    """Parse grammar questions from uploaded PDF (e.g. exam papers from PPT exports)."""
    auth_check = require_teacher()
    if auth_check:
        return auth_check

    if 'file' not in request.files:
        return jsonify({"ok": False, "error": "no_file"}), 400

    file = request.files['file']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"ok": False, "error": "must_be_pdf"}), 400

    import pdfplumber
    import tempfile
    import os

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    file.save(tmp.name)
    tmp.close()

    try:
        with pdfplumber.open(tmp.name) as pdf:
            all_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
            full_text = '\n'.join(all_text)
    finally:
        os.unlink(tmp.name)

    # Parse questions from the extracted text
    questions = _parse_pdf_questions(full_text)

    return jsonify({"ok": True, "questions": questions, "raw_text_length": len(full_text)})


def _parse_pdf_questions(text):
    """Parse grammar questions from PDF text.

    Expected format per question:
      N.(source info)Question stem with ______ blank.
      A.option1  B.option2
      C.option3  D.option4
      答案 X  explanation text...
      [Optional: 思路分析 / 方法技巧 sections]
    """
    # Clean up duplicated header artifacts like 栏栏目目引索引
    text = re.sub(r'栏+目+引?索?引?', '', text)

    # Split into question blocks using the numbered pattern
    # Pattern: digit(s) followed by .( which indicates start of a question
    q_starts = list(re.finditer(r'(?:^|\n)\s*(\d+)\s*\.\s*\(', text))

    questions = []
    for i, match in enumerate(q_starts):
        start = match.start()
        end = q_starts[i + 1].start() if i + 1 < len(q_starts) else len(text)
        block = text[start:end].strip()

        q = _parse_single_question(block, i + 1)
        if q:
            questions.append(q)

    # If no questions found with source pattern, try simpler numbering
    if not questions:
        q_starts = list(re.finditer(r'(?:^|\n)\s*(\d+)\s*[.、]\s*', text))
        for i, match in enumerate(q_starts):
            start = match.start()
            end = q_starts[i + 1].start() if i + 1 < len(q_starts) else len(text)
            block = text[start:end].strip()
            q = _parse_single_question_simple(block, int(match.group(1)))
            if q:
                questions.append(q)

    return questions


def _parse_single_question(block, fallback_seq):
    """Parse a single question block with source info pattern like N.(2019江西,30)."""
    # Extract question number and source
    header = re.match(r'(\d+)\s*\.\s*\(([^)]+)\)\s*', block)
    if not header:
        return None

    seq = int(header.group(1))
    source = header.group(2).strip()
    rest = block[header.end():]

    # Find answer section
    ans_match = re.search(r'答案\s+([A-D])\s+', rest)
    if not ans_match:
        # Try without space after letter
        ans_match = re.search(r'答案\s+([A-D])', rest)

    answer = ans_match.group(1) if ans_match else ''
    explanation = ''

    if ans_match:
        # Everything after "答案 X" up to 思路分析/方法技巧 is explanation
        exp_text = rest[ans_match.end():]
        # Remove 思路分析 and 方法技巧 sections
        exp_text = re.split(r'思路分析|方法技巧', exp_text)[0]
        explanation = exp_text.strip()
        # The question+options part is before the answer
        q_part = rest[:ans_match.start()].strip()
    else:
        q_part = rest.strip()

    # Parse options from q_part
    # Options can be on same line: "A.xxx B.xxx" or separate lines: "A.xxx\nB.xxx"
    # Find all options
    opt_pattern = r'([A-D])\.\s*([^\n]+?)(?=\s+[B-D]\.|$|\n)'
    options = []

    # Try to find the options area (last lines of q_part that contain A. B. C. D.)
    lines = q_part.split('\n')
    stem_lines = []
    option_lines = []
    found_options = False

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Check if line starts with or contains A. pattern
        if re.match(r'^[A-D]\.', line) or (not found_options and re.search(r'\bA\.', line)):
            option_lines.append(line)
            found_options = True
        elif found_options and re.match(r'^[A-D]\.', line):
            option_lines.append(line)
        else:
            if not found_options:
                stem_lines.append(line)
            else:
                # Could be continuation of options on new line
                if re.search(r'^[A-D]\.', line):
                    option_lines.append(line)
                else:
                    stem_lines.append(line)

    stem = ' '.join(stem_lines).strip()
    # Clean up stem - remove multiple spaces
    stem = re.sub(r'\s{2,}', ' ', stem)

    # Parse individual options from option_lines
    opt_text = ' '.join(option_lines)
    # Split by option letter pattern
    opt_matches = re.findall(r'([A-D])\.\s*(\S+(?:\s+\S+)*?)(?=\s+[B-D]\.\s*\S|$)', opt_text)

    for key, text in opt_matches:
        options.append({'key': key, 'text': text.strip()})

    # If we didn't get options, try a different approach
    if len(options) < 2:
        options = []
        for line in option_lines:
            single_opts = re.findall(r'([A-D])\.\s*(.+?)(?=\s{2,}[A-D]\.|$)', line)
            if single_opts:
                for key, text in single_opts:
                    options.append({'key': key, 'text': text.strip()})
            else:
                m = re.match(r'([A-D])\.\s*(.+)', line)
                if m:
                    options.append({'key': m.group(1), 'text': m.group(2).strip()})

    # Add source to hint
    hint = f"来源: {source}"

    return {
        'sequence': seq,
        'content': stem,
        'question_type': 'choice',
        'reference_answer': answer,
        'explanation': explanation,
        'hint': hint,
        'points': 1,
        'options': options
    }


def _parse_single_question_simple(block, seq):
    """Parse a simple question block without source info."""
    # Find answer section
    ans_match = re.search(r'答案\s+([A-D])', block)
    answer = ans_match.group(1) if ans_match else ''
    explanation = ''

    if ans_match:
        exp_text = block[ans_match.end():]
        exp_text = re.split(r'思路分析|方法技巧', exp_text)[0]
        explanation = exp_text.strip()
        q_part = block[:ans_match.start()].strip()
    else:
        q_part = block.strip()

    # Remove leading number
    q_part = re.sub(r'^\d+\s*[.、]\s*', '', q_part)

    lines = q_part.split('\n')
    stem_lines = []
    option_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^[A-D]\.', line) or re.search(r'\bA\.', line):
            option_lines.append(line)
        elif option_lines and re.match(r'^[C-D]\.', line):
            option_lines.append(line)
        else:
            if not option_lines:
                stem_lines.append(line)

    stem = ' '.join(stem_lines).strip()
    stem = re.sub(r'\s{2,}', ' ', stem)

    opt_text = ' '.join(option_lines)
    options = []
    opt_matches = re.findall(r'([A-D])\.\s*(\S+(?:\s+\S+)*?)(?=\s+[B-D]\.\s*\S|$)', opt_text)
    for key, text in opt_matches:
        options.append({'key': key, 'text': text.strip()})

    if len(options) < 2:
        options = []
        for line in option_lines:
            m = re.match(r'([A-D])\.\s*(.+)', line)
            if m:
                options.append({'key': m.group(1), 'text': m.group(2).strip()})

    return {
        'sequence': seq,
        'content': stem,
        'question_type': 'choice',
        'reference_answer': answer,
        'explanation': explanation,
        'hint': '',
        'points': 1,
        'options': options
    } if stem else None
