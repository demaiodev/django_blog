import json
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.utils import timezone
# Keep this import for the essential CSRF bypass on POST methods
from django.views.decorators.csrf import csrf_exempt 

from .models import Post, Comment

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
    }

# --- API View Classes ---

class PostListCreate(View):
    """
    Handles GET (List Posts) and POST (Create Post) requests at /api/posts/
    CSRF protection is bypassed for this API view.
    """
    # **GUARANTEED CSRF BYPASS:** This method applies the exemption to all requests
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """GET: Retrieve a list of all posts."""
        posts = Post.objects.all().order_by('-published_date')
        
        data = [
            {
                'id': p.id,
                'title': p.title,
                'published_date': p.published_date.isoformat(),
            } 
            for p in posts
        ]
        
        response = JsonResponse(data, safe=False)
        return response # CORS is handled by middleware

    def post(self, request):
        """POST: Create a new post."""
        try:
            data = json.loads(request.body)
            
            if not data.get('title') or not data.get('content'):
                response = JsonResponse({'error': 'Title and content are required.'}, status=400)
                return response

            post = Post.objects.create(
                title=data['title'],
                content=data['content'],
                published_date=timezone.now()
            )
            
            response = JsonResponse(serialize_post(post), status=201)
            return response

        except json.JSONDecodeError:
            response = JsonResponse({'error': 'Invalid JSON format.'}, status=400)
            return response
        except Exception as e:
            response = JsonResponse({'error': str(e)}, status=500)
            return response

    def options(self, request, *args, **kwargs):
        """Handles the preflight OPTIONS request."""
        return JsonResponse({}, status=204)


class PostDetail(View):
    """
    Handles GET (Retrieve single Post with Comments) request at /api/posts/<int:pk>/
    """
    def get(self, request, pk):
        """GET: Retrieve a single post and its comments."""
        try:
            post = get_object_or_404(Post, pk=pk)
            data = serialize_post(post)
            response = JsonResponse(data)
            return response

        except Exception:
            response = JsonResponse({'error': 'Post not found.'}, status=404)
            return response

    def options(self, request, *args, **kwargs):
        """Handles the preflight OPTIONS request."""
        return JsonResponse({}, status=204)


class CommentCreate(View):
    """
    Handles POST (Create Comment) request at /api/comments/
    CSRF protection is bypassed for this API view.
    """
    # **GUARANTEED CSRF BYPASS:** This method applies the exemption to all requests
    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        """POST: Create a new comment."""
        try:
            data = json.loads(request.body)
            
            post_id = data.get('post_id')
            author_name = data.get('author_name')
            text = data.get('text')

            if not all([post_id, author_name, text]):
                response = JsonResponse({'error': 'post_id, author_name, and text are required.'}, status=400)
                return response

            post = get_object_or_404(Post, pk=post_id)

            comment = Comment.objects.create(
                post=post,
                author_name=author_name,
                text=text,
                created_date=timezone.now()
            )
            
            response = JsonResponse(serialize_comment(comment), status=201)
            return response

        except json.JSONDecodeError:
            response = JsonResponse({'error': 'Invalid JSON format.'}, status=400)
            return response
        except Exception:
            response = JsonResponse({'error': 'Post not found or internal error.'}, status=400)
            return response
    
    def options(self, request, *args, **kwargs):
        """Handles the preflight OPTIONS request."""
        return JsonResponse({}, status=204)