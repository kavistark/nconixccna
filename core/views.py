import re
import json
import random
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Avg, Sum
from core.models import Domain, Topic, Question, UserProgress, MockExamResult, AdditionalTopic, WhiteboardStroke
from core.decorators import admin_required

try:
    import pusher as pusher_lib
    PUSHER_AVAILABLE = True
except ImportError:
    pusher_lib = None
    PUSHER_AVAILABLE = False

# --- Helper: Markdown to HTML Parser ---
def parse_markdown(text):
    if not text:
        return ""
    html = text
    
    # Headers
    html = re.sub(r'### (.*)', r'<h3>\1</h3>', html)
    html = re.sub(r'## (.*)', r'<h2>\1</h2>', html)
    html = re.sub(r'# (.*)', r'<h1>\1</h1>', html)
    
    # Code blocks
    html = re.sub(r'```cisco([\s\S]*?)```', r'<pre class="cisco-code">\1</pre>', html)
    html = re.sub(r'```([\s\S]*?)```', r'<pre>\1</pre>', html)
    html = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', html)
    
    # Bold / Italics
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', html)
    
    # Blockquotes / Alerts
    html = re.sub(r'^> (.*)', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    
    # Images (Remap to static directory)
    html = re.sub(r'!\[([^\]]*)\]\(images/([^)]+)\)', r'<img src="/static/core/images/\2" alt="\1" class="lesson-image">', html)
    html = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" class="lesson-image">', html)
    
    # Tables
    lines = html.split('\n')
    in_table = False
    table_lines = []
    new_lines = []
    
    for line in lines:
        if line.strip().startswith('|'):
            in_table = True
            table_lines.append(line)
        else:
            if in_table:
                new_lines.append(process_table(table_lines))
                table_lines = []
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append(process_table(table_lines))
        
    html = '\n'.join(new_lines)
    return html

def process_table(lines):
    if len(lines) < 3:
        return '\n'.join(lines)
    
    headers = [cell.strip() for cell in lines[0].split('|')[1:-1]]
    
    table_html = '<table><thead><tr>'
    for h in headers:
        table_html += f'<th>{h}</th>'
    table_html += '</tr></thead><tbody>'
    
    for line in lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        table_html += '<tr>'
        for cell in cells:
            cell_fmt = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', cell)
            cell_fmt = re.sub(r'`([^`]+)`', r'<code>\1</code>', cell_fmt)
            table_html += f'<td>{cell_fmt}</td>'
        table_html += '</tr>'
        
    table_html += '</tbody></table>'
    return table_html


# --- Authentication Views ---
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


# --- Context Processor helper to get domains and chapters for layout sidebar ---
def get_sidebar_data(user):
    domains = Domain.objects.prefetch_related('topics').all()
    # Map progress
    progress_map = {}
    if user.is_authenticated:
        user_progress = UserProgress.objects.filter(user=user)
        for up in user_progress:
            progress_map[up.topic_id] = {
                'lesson': up.lesson_completed,
                'quiz': up.quiz_completed
            }
            
    sidebar_domains = []
    for d in domains:
        topics_list = []
        for t in d.topics.all():
            prog = progress_map.get(t.id, {'lesson': False, 'quiz': False})
            
            # Check locking
            is_locked = True
            if user.is_authenticated:
                if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
                    is_locked = False
                elif hasattr(user, 'profile'):
                    is_locked = not user.profile.has_access_to_topic(t.id)
                else:
                    is_locked = False
            
            topics_list.append({
                'id': t.id,
                'title': t.title,
                'lesson_completed': prog['lesson'],
                'quiz_completed': prog['quiz'],
                'locked': is_locked
            })
        sidebar_domains.append({
            'name': d.name,
            'topics': topics_list
        })
    return sidebar_domains


# --- Core Views ---
@login_required
def dashboard_view(request):
    user = request.user
    if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        return redirect('admin_dashboard')
    
    # Total Progress calculations (63 lessons + 63 quizzes = 126 total pages/steps)
    total_steps = 126
    
    progress_qs = UserProgress.objects.filter(user=user)
    completed_lessons = progress_qs.filter(lesson_completed=True).count()
    completed_quizzes = progress_qs.filter(quiz_completed=True).count()
    completed_steps = completed_lessons + completed_quizzes
    
    progress_percent = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    
    # Quiz stats
    quizzes_taken = progress_qs.filter(quiz_completed=True).count()
    avg_score = progress_qs.filter(quiz_completed=True).aggregate(Avg('quiz_score'))['quiz_score__avg']
    avg_score = int(round(avg_score)) if avg_score is not None else 0
    
    # Domain Readiness Progression
    domains = Domain.objects.prefetch_related('topics').all()
    domain_readiness = []
    
    for d in domains:
        topic_ids = [t.id for t in d.topics.all()]
        total_domain_steps = len(topic_ids) * 2  # lesson + quiz
        
        domain_progress = progress_qs.filter(topic_id__in=topic_ids)
        completed_in_domain = (
            domain_progress.filter(lesson_completed=True).count() + 
            domain_progress.filter(quiz_completed=True).count()
        )
        
        domain_percentage = int((completed_in_domain / total_domain_steps) * 100) if total_domain_steps > 0 else 0
        
        domain_quizzes = domain_progress.filter(quiz_completed=True)
        domain_quiz_avg = domain_quizzes.aggregate(Avg('quiz_score'))['quiz_score__avg']
        domain_quiz_avg = int(round(domain_quiz_avg)) if domain_quiz_avg is not None else 0
        
        domain_readiness.append({
            'name': d.name,
            'progress_percent': domain_percentage,
            'completed_steps': completed_in_domain,
            'total_steps': total_domain_steps,
            'quiz_avg': domain_quiz_avg
        })

    # Sidebar data
    sidebar_domains = get_sidebar_data(user)

    # Calculate resume_id (first uncompleted unlocked lesson)
    resume_id = 1
    for i in range(1, 64):
        if hasattr(user, 'profile') and not user.profile.has_access_to_topic(i):
            continue
        up_topic = progress_qs.filter(topic_id=i).first()
        if not up_topic or not up_topic.lesson_completed:
            resume_id = i
            break

    context = {
        'progress_percent': progress_percent,
        'completed_steps': completed_steps,
        'total_steps': total_steps,
        'avg_score': avg_score,
        'quizzes_taken': quizzes_taken,
        'completed_lessons': completed_lessons,
        'domain_readiness': domain_readiness,
        'sidebar_domains': sidebar_domains,
        'resume_id': resume_id,
        'active_page': 'dashboard',
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def lesson_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Check access lock
    if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
        sidebar_domains = get_sidebar_data(request.user)
        return render(request, 'core/topic_locked.html', {
            'topic': topic,
            'sidebar_domains': sidebar_domains,
        })
        
    progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
    
    parsed_lesson = parse_markdown(topic.lesson_content)
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'topic': topic,
        'current_topic_id': topic_id,
        'lesson_html': parsed_lesson,
        'progress': progress,
        'sidebar_domains': sidebar_domains,
        'active_page': 'lesson',
        'prev_id': topic_id - 1 if topic_id > 1 else None,
        'next_id': topic_id + 1 if topic_id < 63 else None,
    }
    return render(request, 'core/lesson.html', context)


@login_required
def lesson_complete_view(request, topic_id):
    if request.method == 'POST':
        # Check access lock
        if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
            return JsonResponse({'status': 'error', 'message': 'Access denied: Topic is locked.'}, status=403)
            
        topic = get_object_or_404(Topic, id=topic_id)
        progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
        progress.lesson_completed = True
        progress.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
def quiz_view(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)
    
    # Check access lock
    if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
        sidebar_domains = get_sidebar_data(request.user)
        return render(request, 'core/topic_locked.html', {
            'topic': topic,
            'sidebar_domains': sidebar_domains,
        })
        
    questions = list(topic.questions.all())
    
    # We serialize questions to JSON so the slick client-side interactive card transitions remain identical
    serialized_questions = []
    for q in questions:
        serialized_questions.append({
            'question': q.question_text,
            'options': q.options,
            'correctIndex': q.correct_index,
            'explanation': q.explanation
        })
        
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'topic': topic,
        'current_topic_id': topic_id,
        'questions_json': json.dumps(serialized_questions),
        'sidebar_domains': sidebar_domains,
        'active_page': 'quiz',
    }
    return render(request, 'core/quiz.html', context)


@login_required
def quiz_submit_view(request, topic_id):
    if request.method == 'POST':
        # Check access lock
        if hasattr(request.user, 'profile') and not request.user.profile.has_access_to_topic(topic_id):
            return JsonResponse({'status': 'error', 'message': 'Access denied: Topic is locked.'}, status=403)
            
        data = json.loads(request.body)
        score = int(data.get('score', 0))
        
        topic = get_object_or_404(Topic, id=topic_id)
        progress, _ = UserProgress.objects.get_or_create(user=request.user, topic=topic)
        progress.quiz_completed = True
        # Keep highest score
        if score > progress.quiz_score:
            progress.quiz_score = score
        progress.save()
        
        return JsonResponse({'status': 'success', 'saved_score': progress.quiz_score})
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
def mock_exam_setup_view(request):
    sidebar_domains = get_sidebar_data(request.user)
    return render(request, 'core/mock_exam_setup.html', {
        'sidebar_domains': sidebar_domains,
        'active_page': 'mock_exam',
    })


@login_required
def mock_exam_active_view(request):
    # Determine test size from GET parameter
    size = int(request.GET.get('size', 15))
    if size not in [15, 30, 60]:
        size = 15
        
    # Get questions restricted to allowed topics (unless admin)
    user = request.user
    if user.is_superuser or user.is_staff or (hasattr(user, 'profile') and user.profile.role == 'admin'):
        all_questions = list(Question.objects.select_related('topic').all())
    elif hasattr(user, 'profile'):
        profile = user.profile
        if profile.unlock_all_topics:
            all_questions = list(Question.objects.select_related('topic').all())
        else:
            all_questions = list(Question.objects.filter(topic_id__in=profile.allowed_topics).select_related('topic').all())
            # Fallback if student doesn't have enough unlocked topics
            if len(all_questions) < size:
                all_questions = list(Question.objects.select_related('topic').all())
    else:
        all_questions = list(Question.objects.select_related('topic').all())
        
    if len(all_questions) == 0:
        return redirect('mock_exam_setup')
        
    # Shuffle and select a subset
    random.shuffle(all_questions)
    selected_questions = all_questions[:size]
    
    # Store selected questions in session to validate answers on submit
    session_questions = []
    for q in selected_questions:
        session_questions.append({
            'id': q.id,
            'question': q.question_text,
            'options': q.options,
            'correctIndex': q.correct_index,
            'explanation': q.explanation,
            'topicId': q.topic.id,
            'topicTitle': q.topic.title
        })
    
    request.session['active_mock_exam'] = session_questions
    
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'questions_json': json.dumps(session_questions),
        'seconds_remaining': size * 90,  # 1.5 min per question
        'sidebar_domains': sidebar_domains,
        'active_page': 'mock_exam',
    }
    return render(request, 'core/mock_exam_active.html', context)


@login_required
def mock_exam_submit_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_answers = data.get('answers', [])
        
        session_exam = request.session.get('active_mock_exam')
        if not session_exam:
            return JsonResponse({'status': 'error', 'message': 'No active exam session found'}, status=400)
            
        # Calculate scores
        correct_count = 0
        breakdown = []
        
        for idx, q in enumerate(session_exam):
            user_ans = user_answers[idx] if idx < len(user_answers) else None
            is_correct = (user_ans == q['correctIndex'])
            if is_correct:
                correct_count += 1
                
            breakdown.append({
                'topicId': q['topicId'],
                'topicTitle': q['topicTitle'],
                'question': q['question'],
                'options': q['options'],
                'userAnswer': user_ans,
                'correctIndex': q['correctIndex'],
                'isCorrect': is_correct,
                'explanation': q['explanation']
            })
            
        percent = int(round((correct_count / len(session_exam)) * 100))
        
        # Save to MockExamResult model
        MockExamResult.objects.create(
            user=request.user,
            total_questions=len(session_exam),
            correct_answers=correct_count,
            percentage=percent
        )
        
        # Clear session active exam
        if 'active_mock_exam' in request.session:
            del request.session['active_mock_exam']
            
        return JsonResponse({
            'status': 'success',
            'percentage': percent,
            'correct_count': correct_count,
            'total_questions': len(session_exam),
            'breakdown': breakdown
        })
        
    return JsonResponse({'status': 'invalid method'}, status=400)


@login_required
def additional_topic_detail_view(request, topic_id):
    topic = get_object_or_404(AdditionalTopic, id=topic_id)
    parsed_content = parse_markdown(topic.content)
    sidebar_domains = get_sidebar_data(request.user)
    
    context = {
        'topic': topic,
        'parsed_content': parsed_content,
        'sidebar_domains': sidebar_domains,
        'current_atopic_id': topic.id,
        'active_page': 'additional_topic_detail',
    }
    return render(request, 'core/additional_topic_detail.html', context)


@login_required
def tutor_bot_view(request):
    sidebar_domains = get_sidebar_data(request.user)
    context = {
        'sidebar_domains': sidebar_domains,
        'active_page': 'tutor_bot',
    }
    return render(request, 'core/tutor_bot.html', context)


@login_required
def tutor_chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON request'}, status=400)

        if not user_message:
            return JsonResponse({'error': 'Message is empty'}, status=400)

        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-3.7-flash')

        if not api_key:
            return JsonResponse({'error': 'Gemini API key is not configured.'}, status=500)

        history = data.get('history', [])
        contents = []
        for msg in history:
            role = 'user' if msg.get('role') == 'user' else 'model'
            text = msg.get('text', '').strip()
            if text:
                contents.append({
                    "role": role,
                    "parts": [{"text": text}]
                })
        
        if not contents or contents[-1].get('role') != 'user':
            contents.append({
                "role": "user",
                "parts": [{"text": user_message}]
            })

        headers = {
            "Content-Type": "application/json"
        }
        
        response = None
        used_model = model_name
        fallback_models = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-flash-latest', 'gemini-2.5-flash']

        for model in [model_name] + [m for m in fallback_models if m != model_name]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "contents": contents,
                "systemInstruction": {
                    "parts": [{
                        "text": "You are a professional CCNA and computer networking expert tutor. Answer the student's questions clearly, concisely, and accurately. Provide examples, packet headers, or Cisco commands where relevant to explain networking concepts. Format your responses in clean HTML or Markdown."
                    }]
                }
            }
            try:
                res = requests.post(url, headers=headers, params={"key": api_key}, json=payload, timeout=30)
                if res.status_code == 200:
                    response = res
                    used_model = model
                    break
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Gemini API returned status {res.status_code} for model {model}. Body: {res.text}. Trying next model...")
            except requests.exceptions.RequestException as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error calling Gemini with model {model}: {e}. Trying next model...")

        if response is None:
            return JsonResponse({'error': 'Failed to communicate with Gemini API (all models exhausted/unavailable).'}, status=500)

        try:
            res_data = response.json()
            candidates = res_data.get('candidates', [])
            if candidates:
                content_obj = candidates[0].get('content', {})
                parts = content_obj.get('parts', [])
                if parts:
                    ai_reply = parts[0].get('text', '')
                    ai_reply_html = parse_markdown(ai_reply)
                    return JsonResponse({
                        'reply': ai_reply,
                        'reply_html': ai_reply_html,
                        'model_used': used_model
                    })
            
            return JsonResponse({'error': 'No response candidate returned from Gemini.'}, status=500)
            
        except Exception as e:
            return JsonResponse({'error': f"Failed to parse response: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
@login_required
def board_send_event_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if not PUSHER_AVAILABLE:
            return JsonResponse({'error': 'Pusher library is not installed on this server.'}, status=500)

        app_id = getattr(settings, 'PUSHER_APP_ID', '')
        key = getattr(settings, 'PUSHER_KEY', '')
        secret = getattr(settings, 'PUSHER_SECRET', '')
        cluster = getattr(settings, 'PUSHER_CLUSTER', 'ap2')
        ssl = getattr(settings, 'PUSHER_SSL', True)

        if not (app_id and key and secret):
            return JsonResponse({'error': 'Pusher is not configured.'}, status=500)

        pusher_client = pusher_lib.Pusher(
            app_id=app_id,
            key=key,
            secret=secret,
            cluster=cluster,
            ssl=ssl
        )

        packet_type = data.get('type')

        # Save persistent data in the database
        if packet_type == 'clear':
            WhiteboardStroke.objects.all().delete()
        elif packet_type == 'undo':
            stroke_id = data.get('strokeId')
            if stroke_id:
                WhiteboardStroke.objects.filter(data__strokeId=stroke_id).delete()
        elif packet_type == 'batch':
            segments = data.get('segments', [])
            strokes_to_create = [WhiteboardStroke(data=seg) for seg in segments]
            if strokes_to_create:
                WhiteboardStroke.objects.bulk_create(strokes_to_create)
        elif packet_type == 'pointer':
            pass  # pointer events are not persisted
        else:
            WhiteboardStroke.objects.create(data=data)

        # Broadcast event via Pusher
        try:
            pusher_client.trigger('whiteboard-channel', 'drawing-event', data)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': f"Failed to publish to Pusher: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def board_history_api(request):
    strokes = WhiteboardStroke.objects.all().order_by('created_at')
    history = [s.data for s in strokes]
    return JsonResponse({'history': history})





