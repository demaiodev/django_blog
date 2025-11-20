import json
import requests
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Post, Comment

# --- Mock Response Helper Classes ---
# These classes simulate the response object returned by the requests library

class MockResponse:
    """Mock class for the requests.post response."""
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Returns the simulated JSON payload."""
        return self.json_data

    def raise_for_status(self):
        """Simulates raise_for_status for HTTP errors."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"Simulated HTTP Error {self.status_code}")

    @property
    def ok(self):
        """Simulates response.ok property."""
        return self.status_code < 400

# --- Standard API Success/Flagged Payloads ---

# 1. Mock payload for a "safe" classification
MOCK_SAFE_RESPONSE = {
    "candidates": [{
        "content": {"parts": [{"text": "safe"}]}
    }]
}
# 2. Mock payload for a "needs_review" classification
MOCK_FLAGGED_RESPONSE = {
    "candidates": [{
        "content": {"parts": [{"text": "needs_review"}]}
    }]
}


class CommentAPITest(TestCase):
    """
    Tests the CommentCreate API endpoint, focusing on moderation logic.
    Mocks the external Gemini API call via requests.post.
    """
    def setUp(self):
        self.client = Client()
        self.post = Post.objects.create(
            title="Test Post", 
            content="Content for testing.", 
            published_date=timezone.now()
        )
        self.url = reverse('comment-create')
        self.base_data = {
            'post_id': self.post.id,
            'author_name': 'Test Author',
            'text': 'A placeholder comment.'
        }

    @mock.patch('blog.views.requests.post')
    def test_comment_creation_safe(self, mock_post):
        """Tests comment creation when the model classifies it as 'safe'."""
        
        # Configure the mock to return a safe response
        mock_post.return_value = MockResponse(MOCK_SAFE_RESPONSE, 201)

        response = self.client.post(self.url, json.dumps(self.base_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        
        # ASSERTIONS
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(data['flagged'], False) 
        self.assertFalse(Comment.objects.first().flagged)

        # Check that the API call was made
        self.assertTrue(mock_post.called)


    @mock.patch('blog.views.requests.post')
    def test_comment_creation_flagged(self, mock_post):
        """Tests comment creation when the model classifies it as 'needs_review' (flagged)."""
        
        # Configure the mock to return a flagged response
        mock_post.return_value = MockResponse(MOCK_FLAGGED_RESPONSE, 201)

        # Use potentially offensive text, though the mock controls the result
        flagged_data = self.base_data.copy()
        flagged_data['text'] = "This is definitely offensive content."
        
        response = self.client.post(self.url, json.dumps(flagged_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        
        # ASSERTIONS
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(data['flagged'], True) 
        self.assertTrue(Comment.objects.first().flagged)
        
        # Check that the API call was made
        self.assertTrue(mock_post.called)


    @mock.patch('blog.views.requests.post')
    def test_comment_creation_api_failure(self, mock_post):
        """Tests comment creation when the external API returns a 500 error."""
        
        # Configure the mock to simulate a server error (which should result in 'safe' default)
        mock_post.side_effect = requests.exceptions.RequestException("API connection error")

        response = self.client.post(self.url, json.dumps(self.base_data), content_type='application/json')
        
        self.assertEqual(response.status_code, 201) # Django still saves, but defaults to safe
        data = response.json()
        
        # ASSERTIONS
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(data['flagged'], False) # Should default to False (safe) on failure
        self.assertFalse(Comment.objects.first().flagged)
        
        # Check that the API call was attempted
        self.assertTrue(mock_post.called)

    def test_comment_creation_missing_data(self):
        """Tests required fields validation."""
        data_missing_text = {'post_id': self.post.id, 'author_name': 'Test'}
        response = self.client.post(self.url, json.dumps(data_missing_text), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

# --- Post List/Detail Tests (No Change Needed, but included for completeness) ---

class PostAPITest(TestCase):
    """Tests the PostListCreate and PostDetail endpoints."""
    def setUp(self):
        self.client = Client()
        self.post1 = Post.objects.create(title="First Post", content="One", published_date=timezone.now())
        self.post2 = Post.objects.create(title="Second Post", content="Two", published_date=timezone.now() - timezone.timedelta(days=1))
        self.list_url = reverse('post-list-create')

    def test_post_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        # Check sorting by published_date descending (post1 is newer)
        self.assertEqual(data[0]['title'], "First Post") 
        self.assertEqual(data[1]['title'], "Second Post")

    def test_post_detail(self):
        detail_url = reverse('post-detail', kwargs={'pk': self.post1.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], "First Post")
        self.assertIn('comments', data)

    def test_post_create(self):
        new_post_data = {'title': 'New Test Post', 'content': 'This is new.'}
        response = self.client.post(self.list_url, json.dumps(new_post_data), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.count(), 3)