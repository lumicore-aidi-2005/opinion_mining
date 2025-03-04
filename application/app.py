from flask import Flask, render_template, request, flash
from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from scrapper.comment_fetcher import reddit, store_comments_for_url
from scrapper.keyword_extract import extract_keywords
from scrapper.sentiment_analysis import SentimentAnalyzer
from scrapper.ls_psql import query_db, connect_to_db
from dotenv import load_dotenv
import praw.exceptions
import sys
from pathlib import Path
# from transformers import pipeline
from urllib.parse import urlparse
import re



#
def is_valid_reddit_url(url):
    """Validate if URL is a legitimate Reddit URL"""
    parsed = urlparse(url)
    return parsed.netloc in [
        "reddit.com",
        "www.reddit.com",
        "old.reddit.com",
    ] and re.match(r"^/r/[^/]+/comments/[^/]+(/[^/]+)?/?$", parsed.path)



# Add this function at the top with other imports
def generate_summary(comments_df, keywords, sentiment_stats):
    # Get top 2-3 most representative comments
    summary_comments = []
    
    # Get dominant sentiment
    max_sentiment = max(sentiment_stats.items(), key=lambda x: x[1])[0]
    
    # Find comments that contain keywords and match dominant sentiment
    for _, row in comments_df.iterrows():
        comment = row['comment']
        # Check if comment contains any keywords
        if any(keyword.lower() in comment.lower() for keyword in keywords):
            summary_comments.append(comment)
            if len(summary_comments) >= 3:
                break
    
    # Create summary
    summary = f"Discussion shows {max_sentiment.lower()} sentiment ({sentiment_stats[max_sentiment]:.1f}%). "
    summary += f"Key points discussed: {', '.join(keywords[:3])}. "
    
    if summary_comments:
        summary += "\nKey insights: " + " ... ".join(summary_comments)
    
    return summary

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-secret-key')
csrf = CSRFProtect(app)
talisman = Talisman(
    app,
    content_security_policy={
        "default-src": "'self'",
        "script-src": "'self' 'unsafe-inline'",
        "style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    },force_https=True
)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "10 per hour"],
    storage_uri="memory://",
)




@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']

        # Validate Reddit URL
        if not is_valid_reddit_url(url):
            flash('Invalid Reddit URL provided. Please check the URL and try again.', 'error')
            return render_template('index.html')
        
        try:
            # First store comments in database
            store_comments_for_url(url)
            
            # Connect to database
            conn = connect_to_db(
                os.getenv("HOST"),
                os.getenv("PORT"),
                os.getenv("DATABASE"),
                os.getenv("USER"),
                os.getenv("PASSWORD")
            )
            
            # Fetch comments from database
            query = "SELECT comment, comment_level FROM Comments WHERE specific_url = %s LIMIT 10"
            comments_df = query_db(conn, query, (url,))
            
            # Process comments from database
            comments = []
            all_text = ""
            for _, row in comments_df.iterrows():
                comments.append({
                    'text': row['comment'],
                    'level': row['comment_level']
                })
                all_text += row['comment'] + " "
            
            # Extract keywords
            keywords = extract_keywords(all_text, top_n=10)
            
            # Analyze sentiment
            analyzer = SentimentAnalyzer()
            sentiments = []
            for comment in comments:
                sentiment = analyzer.analyze_sentiment(comment['text'])
                sentiments.append(sentiment)
            
            # Calculate sentiment percentages
            total = len(sentiments)
            sentiment_stats = {
                'Positive': sentiments.count('Positive') / total * 100,
                'Neutral': sentiments.count('Neutral') / total * 100,
                'Negative': sentiments.count('Negative') / total * 100
            }
            
            # Generate summary using our custom function instead of transformer
            summary = generate_summary(comments_df, keywords, sentiment_stats)

            return render_template('results.html',
                                comments=comments,
                                keywords=keywords,
                                sentiment_stats=sentiment_stats,
                                summary=summary)
            
        except praw.exceptions.InvalidURL:
            flash('Invalid Reddit URL provided. Please check the URL and try again.', 'error')
            return render_template('index.html')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
            return render_template('index.html')
    
    return render_template('index.html')

if __name__ == '__main__':

    debug_mode = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", debug=debug_mode)

