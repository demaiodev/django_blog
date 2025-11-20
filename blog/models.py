from django.db import models

class Post(models.Model):
    """
    Represents a blog post with a title, content, and publication date.
    """
    title = models.CharField(max_length=200)
    content = models.TextField()
    published_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class Comment(models.Model):
    """
    Represents a comment made on a Post, linked by a ForeignKey.
    """
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    author_name = models.CharField(max_length=100)
    text = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post.title[:30]}..."