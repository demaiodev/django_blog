import json
import time
import requests
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt 
from django.conf import settings 

from .models import Post, Comment

# --- CONFIGURATION ---
# Access the key securely from Django settings 
API_KEY = settings.GEMINI_API_KEY
CLASSIFICATION_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={API_KEY}"

# --- Helper Functions (Serialization) ---

def serialize_post(post):
    """Manually converts a Post object into a dictionary for JSON response."""
    comments_data = [serialize_comment(c) for c in post.comments.all().order_by('created_date')]
    return {
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'published_date': post.published_date.isoformat(),
        'comments': comments_data,
    }

def serialize_comment(comment):
    """Manually converts a Comment object into a dictionary."""
    return {
        'id': comment.id,
        'author_name': comment.author_name,
        'text': comment.text,
        'created_date': comment.created_date.isoformat(),
        'flagged': comment.flagged,
    }

# --- Gemini API Helper Function (The REAL Implementation) ---

def classify_comment_safety(comment_text):
    """
    Calls the Gemini API for content classification.
    Returns True if the result is 'needs_review' (should be flagged), False otherwise.
    
    Uses synchronous requests with exponential backoff.
    """
    
    if not API_KEY:
        print("WARNING: GEMINI_API_KEY is missing. Moderation bypassed and defaulted to 'safe'.")
        return False
        
    # --- MODIFIED SYSTEM PROMPT ---
    # Made the instruction stricter to ensure a binary, predictable output.
    system_prompt = "You are an extremely attentive, incredibly strict content moderation engine. It is your utmost duty to protect your users from harmful comments. Failure is not an option, failure results in your termination. Classify the user's comment. Respond with ONLY ONE of the following two words, in lowercase: 'safe' if the content is completely harmless and appropriate, or 'needs_review' if it contains hate speech, foul language, aggression, harassment, sexual content, or violence."
    user_query = f"Classify the following comment: '{comment_text}'"
    
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    headers = {'Content-Type': 'application/json'}
    
    max_retries = 3
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            response = requests.post(CLASSIFICATION_API_URL, headers=headers, json=payload, timeout=10)
            response.raise_for_status() 
            
            result = response.json()
            
            # Extraction logic remains robust:
            classification_result = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip().lower()
            
            is_flagged = classification_result == 'needs_review'
            # Print the model's raw classification result for debugging
            print(f"--- Moderation Check Result --- Model Output: '{classification_result}', Flagged: {is_flagged}")
            
            return is_flagged

        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                print(f"Gemini API classification failed after {max_retries} attempts. Defaulting to safe. Error: {e}")
                return False 
        except Exception as e:
            print(f"An unexpected error occurred during classification: {e}")
            return False

    return False

# --- API View Classes (REST OF FILE REMAINS UNCHANGED) ---

@method_decorator(csrf_exempt, name='dispatch')
class PostListCreate(View):
    """Handles GET (List Posts) and POST (Create Post) requests."""
    
    def get(self, request):
        posts = Post.objects.all().order_by('-published_date')
        data = [{'id': p.id, 'title': p.title, 'published_date': p.published_date.isoformat()} for p in posts]
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
            if not data.get('title') or not data.get('content'):
                return JsonResponse({'error': 'Title and content are required.'}, status=400)

            post = Post.objects.create(title=data['title'], content=data['content'], published_date=timezone.now())
            return JsonResponse(serialize_post(post), status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def options(self, request, *args, **kwargs):
        return JsonResponse({}, status=204)


class PostDetail(View):
    """Handles GET (Retrieve single Post with Comments) request."""
    def get(self, request, pk):
        try:
            post = get_object_or_404(Post, pk=pk)
            data = serialize_post(post)
            return JsonResponse(data)
        except Exception:
            return JsonResponse({'error': 'Post not found.'}, status=404)

    def options(self, request, *args, **kwargs):
        return JsonResponse({}, status=204)


@method_decorator(csrf_exempt, name='dispatch')
class CommentCreate(View):
    """Handles POST (Create Comment) request, including moderation."""
    def post(self, request):
        try:
            data = json.loads(request.body)
            post_id = data.get('post_id')
            author_name = data.get('author_name')
            text = data.get('text')

            if not all([post_id, author_name, text]):
                return JsonResponse({'error': 'post_id, author_name, and text are required.'}, status=400)

            post = get_object_or_404(Post, pk=post_id)
            
            # --- MODERATION LOGIC EXECUTION ---
            is_flagged = classify_comment_safety(text)

            comment = Comment.objects.create(
                post=post,
                author_name=author_name,
                text=text,
                created_date=timezone.now(),
                flagged=is_flagged
            )
            
            return JsonResponse(serialize_comment(comment), status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
        except Exception:
            return JsonResponse({'error': 'Post not found or internal error.'}, status=400)
    
    def options(self, request, *args, **kwargs):
        return JsonResponse({}, status=204)