from django.urls import path
from . import views

urlpatterns = [
    # GET /api/posts/ - List all posts
    # POST /api/posts/ - Create a new post
    path('posts/', views.PostListCreate.as_view(), name='post-list-create'),

    # GET /api/posts/1/ - Retrieve a single post and its comments
    path('posts/<int:pk>/', views.PostDetail.as_view(), name='post-detail'),

    # POST /api/comments/ - Create a new comment
    path('comments/', views.CommentCreate.as_view(), name='comment-create'),

    # GET /api/comments/flagged/ - List all flagged comments for moderation
    path('comments/flagged/', views.FlaggedCommentList.as_view(), name='flagged-comment-list'),
]