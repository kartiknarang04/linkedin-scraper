import os
import sys
import time
import random
import re
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
import json
import requests
from uuid import uuid4
from linkedin_scraper import LinkedInScraper  # Import your existing scraper

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_content_with_groq(posts, max_posts=10):
    """Analyze content using Groq API to identify tones and topics."""
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return None
        
        # Limit the number of posts to analyze to avoid long processing times
        if len(posts) > max_posts:
            # Select a representative sample
            sample_posts = posts.sort_values('total_engagement', ascending=False).head(max_posts)
        else:
            sample_posts = posts
        
        # Prepare the prompt
        post_texts = "\n\n---\n\n".join([f"Post {i+1}: {text}" for i, text in enumerate(sample_posts['post_text'].tolist())])
        
        prompt = f"""
        Analyze the following LinkedIn posts to identify:
        1. The dominant tone of each post (professional, inspirational, educational, conversational, promotional, etc.)
        2. The main topics discussed (e.g., leadership, AI, innovation, career development, etc.)

        Posts:
        {post_texts}

        Provide your analysis in the following JSON format:
        {{
            "posts": [
                {{
                    "post_index": 1,
                    "tone": "professional",
                    "topics": ["leadership", "team management"]
                }},
                ...
            ],
            "overall_analysis": {{
                "dominant_tones": ["professional", "inspirational"],
                "main_topics": ["leadership", "innovation", "AI"]
            }}
        }}

        Only respond with the JSON, no additional text.
        """
        
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 2000
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            analysis_text = result["choices"][0]["message"]["content"]
            
            # Extract JSON from the response
            try:
                analysis = json.loads(analysis_text)
                
                # Add the analysis back to the dataframe
                for post_analysis in analysis['posts']:
                    post_idx = post_analysis['post_index'] - 1
                    if post_idx < len(sample_posts):
                        sample_posts.iloc[post_idx, sample_posts.columns.get_loc('tone')] = post_analysis['tone']
                        sample_posts.iloc[post_idx, sample_posts.columns.get_loc('topics')] = ', '.join(post_analysis['topics'])
                
                # Return the overall analysis
                return {
                    'analyzed_posts': sample_posts,
                    'overall_analysis': analysis['overall_analysis']
                }
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from Groq response: {analysis_text}")
                return None
        else:
            logger.error(f"Error from Groq API: {response.status_code} - {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Error analyzing content with Groq: {str(e)}")
        return None

def generate_content_with_groq(topic=None, example_post=None, day_of_week=None, hour_of_day=None, reactions=None, comments=None, hashtags=None, popular_hashtags=None, feedback=None):
    """Generate content using Groq API based on user input or a successful post."""
    try:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return ["GROQ_API_KEY not found in environment variables."]
        
        # If user provided a topic, use that as the primary prompt
        if topic:
            prompt = f"""
            You are a LinkedIn content creator assistant.
            
            Create 3 different variations of a professional LinkedIn post about the following topic:
            "{topic}"
            
            Make each post engaging, insightful, and formatted for LinkedIn.
            Each variation should have a different approach or angle.
            
            Format your response with "Post 1:", "Post 2:", etc. before each variation.
            """
            
            # Add popular hashtags if provided
            if popular_hashtags:
                prompt += f"\n\nInclude some of these popular hashtags where appropriate: {popular_hashtags}"
        
        # Otherwise use the example post as reference
        else:
            prompt = f"""
            You are a LinkedIn content creator assistant.

            Here is a sample post that performed well:
            "{example_post}"

            It was posted on {day_of_week} at {hour_of_day}:00 and received {reactions} reactions and {comments} comments.

            Hashtags used: {hashtags}

            Based on this example, generate 3 different variations of a similar post with a professional and engaging tone.
            Each variation should have a different approach or angle.
            
            Format your response with "Post 1:", "Post 2:", etc. before each variation.
            """
        
        # Add feedback if provided
        if feedback:
            prompt += f"\n\nPlease incorporate this feedback in the new variations: {feedback}"
        
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            
            # Split the content into separate posts
            posts = re.split(r'Post \d+:', generated_content)
            posts = [p.strip() for p in posts if p.strip()]
            
            return posts
        else:
            return [f"Error: {response.status_code} - {response.text}"]
    
    except Exception as e:
        return [f"Error generating content: {str(e)}"]

def analyze_hashtags(df):
    """Extract and analyze hashtags from posts."""
    # Extract all hashtags
    all_hashtags = []
    for tags in df['hashtags'].dropna():
        if tags:
            all_hashtags.extend([tag.strip() for tag in tags.split(',')])
    
    if all_hashtags:
        # Count hashtags
        hashtag_counts = pd.Series(all_hashtags).value_counts()
        
        # Calculate average engagement per hashtag
        hashtag_engagement = []
        for _, row in df.iterrows():
            if pd.notna(row['hashtags']) and row['hashtags']:
                tags = [tag.strip() for tag in row['hashtags'].split(',')]
                for tag in tags:
                    hashtag_engagement.append({
                        'hashtag': tag,
                        'engagement': row['total_engagement']
                    })
        
        if hashtag_engagement:
            hashtag_df = pd.DataFrame(hashtag_engagement)
            hashtag_avg = hashtag_df.groupby('hashtag')['engagement'].agg(['mean', 'count']).reset_index()
            hashtag_avg = hashtag_avg.sort_values('mean', ascending=False)
            
            return {
                'counts': hashtag_counts,
                'engagement': hashtag_avg
            }
    
    return None

def analyze_post_length(df):
    """Analyze the relationship between post length and engagement."""
    if 'post_length' in df.columns and 'total_engagement' in df.columns:
        # Create length categories
        df['length_category'] = pd.cut(
            df['post_length'], 
            bins=[0, 100, 300, 600, 1000, 10000],
            labels=['Very Short', 'Short', 'Medium', 'Long', 'Very Long']
        )
        
        # Calculate average engagement per length category
        length_engagement = df.groupby('length_category')['total_engagement'].mean().reset_index()
        
        # Find optimal length range
        optimal_category = length_engagement.loc[length_engagement['total_engagement'].idxmax(), 'length_category']
        
        return {
            'length_engagement': length_engagement,
            'optimal_category': optimal_category
        }
    
    return None

def analyze_posting_time(df):
    """Analyze the best time to post based on day of week and hour of day."""
    if 'day_of_week' in df.columns and 'hour_of_day' in df.columns and 'total_engagement' in df.columns:
        # Filter out unknown days and hours
        time_df = df[(df['day_of_week'] != 'Unknown') & (df['hour_of_day'] != 'Unknown')].copy()
        
        if not time_df.empty:
            # Convert hour to integer
            time_df['hour_of_day'] = pd.to_numeric(time_df['hour_of_day'], errors='coerce')
            
            # Group by day and hour, calculate average engagement
            day_engagement = time_df.groupby('day_of_week')['total_engagement'].mean().reset_index()
            hour_engagement = time_df.groupby('hour_of_day')['total_engagement'].mean().reset_index()
            
            # Find best day and hour
            best_day = day_engagement.loc[day_engagement['total_engagement'].idxmax(), 'day_of_week']
            best_hour = hour_engagement.loc[hour_engagement['total_engagement'].idxmax(), 'hour_of_day']
            
            # Create day-hour heatmap data
            heatmap_data = time_df.groupby(['day_of_week', 'hour_of_day'])['total_engagement'].mean().reset_index()
            
            return {
                'day_engagement': day_engagement,
                'hour_engagement': hour_engagement,
                'best_day': best_day,
                'best_hour': best_hour,
                'heatmap_data': heatmap_data
            }
    
    return None

def get_top_posts(df, n=5):
    """Get the top performing posts by engagement."""
    if 'total_engagement' in df.columns:
        return df.sort_values('total_engagement', ascending=False).head(n)
    return pd.DataFrame()

# Streamlit UI
def main():
    st.set_page_config(page_title="LinkedIn Content Analyzer", page_icon="📊", layout="wide")
    
    # Initialize session state variables if they don't exist
    if 'feedback_submitted' not in st.session_state:
        st.session_state.feedback_submitted = False
    if 'generated_posts' not in st.session_state:
        st.session_state.generated_posts = []
    if 'refined_posts' not in st.session_state:
        st.session_state.refined_posts = []
    if 'current_topic' not in st.session_state:
        st.session_state.current_topic = None
    if 'current_hashtags' not in st.session_state:
        st.session_state.current_hashtags = None
    if 'current_example_post' not in st.session_state:
        st.session_state.current_example_post = None
    if 'current_day' not in st.session_state:
        st.session_state.current_day = None
    if 'current_hour' not in st.session_state:
        st.session_state.current_hour = None
    if 'current_reactions' not in st.session_state:
        st.session_state.current_reactions = None
    if 'current_comments' not in st.session_state:
        st.session_state.current_comments = None
    if 'current_post_hashtags' not in st.session_state:
        st.session_state.current_post_hashtags = None
    
    st.title("LinkedIn Content Analyzer")
    st.write("Analyze LinkedIn content to optimize your posting strategy")
    
    # Sidebar
    st.sidebar.title("Options")
    
    # Check if data exists
    data_file = 'data/linkedin_original_posts.csv'
    data_exists = os.path.exists(data_file)
    
    # Get list of session files
    session_files = [f for f in os.listdir('data') if f.startswith('linkedin_posts_') and f.endswith('.csv')]
    sessions_exist = len(session_files) > 0
    
    # Create tabs - simplified to 4 tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Scrape Data", 
        "Analyze Content", 
        "Engagement Insights", 
        "Generate Posts"
    ])
    
    with tab1:
        st.header("Scrape LinkedIn Profiles")
        
        # Profile URLs
        st.subheader("LinkedIn Profiles")
        default_profiles = [
            "https://www.linkedin.com/in/archit-anand/",
            "https://www.linkedin.com/in/aarongolbin/",
            "https://www.linkedin.com/in/robertschöne/",
            "https://www.linkedin.com/in/jaspar-carmichael-jack/"
        ]
        
        profile_text = st.text_area(
            "Enter LinkedIn profile URLs (one per line):", 
            value="\n".join(default_profiles),
            height=150
        )
        
        profile_urls = [url.strip() for url in profile_text.split("\n") if url.strip()]
        
        # Scraping options
        col1, col2, col3 = st.columns(3)
        with col1:
            headless = st.checkbox("Run in headless mode", value=False, help="Run browser in background (no visible window)")
        with col2:
            debug_mode = st.checkbox("Debug mode", value=True, help="Save screenshots for debugging")
        with col3:
            max_posts = st.slider("Max posts per profile", min_value=1, max_value=20, value=5, help="Maximum number of posts to scrape per profile")
        
        # Scrape button
        if st.button("Scrape Profiles"):
            if not os.getenv("LINKEDIN_EMAIL") or not os.getenv("LINKEDIN_PASSWORD"):
                st.error("LinkedIn credentials not found. Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.")
            else:
                with st.spinner("Scraping LinkedIn profiles... This may take a few minutes."):
                    try:
                        scraper = LinkedInScraper(headless=headless, debug=debug_mode, max_posts=max_posts)
                        scraper.login()
                        
                        if scraper.logged_in:
                            df_new, df_all = scraper.scrape_multiple_profiles(profile_urls)
                            scraper.close()
                            
                            if not df_new.empty:
                                st.success(f"Successfully scraped {len(df_new)} posts!")
                                st.session_state['last_session_id'] = scraper.session_id
                                st.session_state['last_scraped_data'] = df_new
                                st.dataframe(df_new)
                            else:
                                st.warning("No posts were scraped. Check the debug folder for screenshots.")
                        else:
                            st.error("Login failed. Please check your credentials.")
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
        
        # Display existing data
        if data_exists or sessions_exist:
            st.subheader("Existing Data")
            
            # Option to view all data or specific session
            data_view = st.radio(
                "View data from:",
                ["All scraped data", "Most recent session", "Specific session"],
                index=1 if sessions_exist else 0
            )
            
            if data_view == "All scraped data" and data_exists:
                df = pd.read_csv(data_file)
                st.write(f"Found {len(df)} posts in the database")
                if st.checkbox("Show all data"):
                    st.dataframe(df)
            
            elif data_view == "Most recent session" and sessions_exist:
                # Get the most recent session file
                latest_session = max(session_files, key=lambda x: os.path.getmtime(os.path.join('data', x)))
                df = pd.read_csv(os.path.join('data', latest_session))
                session_id = latest_session.split('_')[-1].split('.')[0]
                st.write(f"Showing {len(df)} posts from session {session_id}")
                st.dataframe(df)
            
            elif data_view == "Specific session" and sessions_exist:
                # Create a dropdown to select a specific session
                session_options = {}
                for file in session_files:
                    session_id = file.split('_')[-1].split('.')[0]
                    file_path = os.path.join('data', file)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        df_temp = pd.read_csv(file_path)
                        num_posts = len(df_temp)
                        profiles = ', '.join(df_temp['profile_name'].unique())
                    except:
                        num_posts = "Unknown"
                        profiles = "Unknown"
                    
                    session_options[session_id] = f"Session {session_id} - {modified_time} - {num_posts} posts - {profiles}"
                
                selected_session = st.selectbox(
                    "Select session:",
                    list(session_options.keys()),
                    format_func=lambda x: session_options[x]
                )
                
                selected_file = f"linkedin_posts_{selected_session}.csv"
                df = pd.read_csv(os.path.join('data', selected_file))
                st.write(f"Showing {len(df)} posts from session {selected_session}")
                st.dataframe(df)
    
    with tab2:
        st.header("Content Analysis")
        
        if not data_exists and not sessions_exist:
            st.warning("No data available. Please scrape LinkedIn profiles first.")
        else:
            # Data selection
            data_source = st.radio(
                "Select data source:",
                ["All data", "Most recent session", "Specific session", "Specific profile"],
                index=1 if sessions_exist else 0
            )
            
            df = None
            
            if data_source == "All data" and data_exists:
                df = pd.read_csv(data_file)
                st.write(f"Analyzing {len(df)} posts from all sessions")
            
            elif data_source == "Most recent session" and sessions_exist:
                # Get the most recent session file
                latest_session = max(session_files, key=lambda x: os.path.getmtime(os.path.join('data', x)))
                df = pd.read_csv(os.path.join('data', latest_session))
                session_id = latest_session.split('_')[-1].split('.')[0]
                st.write(f"Analyzing {len(df)} posts from session {session_id}")
            
            elif data_source == "Specific session" and sessions_exist:
                # Create a dropdown to select a specific session
                session_options = {}
                for file in session_files:
                    session_id = file.split('_')[-1].split('.')[0]
                    file_path = os.path.join('data', file)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        df_temp = pd.read_csv(file_path)
                        num_posts = len(df_temp)
                        profiles = ', '.join(df_temp['profile_name'].unique())
                    except:
                        num_posts = "Unknown"
                        profiles = "Unknown"
                    
                    session_options[session_id] = f"Session {session_id} - {modified_time} - {num_posts} posts - {profiles}"
                
                selected_session = st.selectbox(
                    "Select session:",
                    list(session_options.keys()),
                    format_func=lambda x: session_options[x]
                )
                
                selected_file = f"linkedin_posts_{selected_session}.csv"
                df = pd.read_csv(os.path.join('data', selected_file))
                st.write(f"Analyzing {len(df)} posts from session {selected_session}")
            
            elif data_source == "Specific profile":
                if data_exists:
                    all_df = pd.read_csv(data_file)
                    profiles = sorted(all_df['profile_name'].unique())
                    
                    selected_profile = st.selectbox(
                        "Select profile to analyze:",
                        profiles
                    )
                    
                    df = all_df[all_df['profile_name'] == selected_profile]
                    st.write(f"Analyzing {len(df)} posts from {selected_profile}")
            
            if df is not None and not df.empty:
                # Ensure total_engagement column exists
                if 'total_engagement' not in df.columns:
                    if 'engagement' in df.columns:
                        df['total_engagement'] = df['engagement']
                    else:
                        # Create total_engagement from reactions and comments
                        df['total_engagement'] = df['reactions'] + df['comments']
                        if 'reposts' in df.columns:
                            df['total_engagement'] += df['reposts']
                
                # Add tone and topics columns if they don't exist
                if 'tone' not in df.columns:
                    df['tone'] = None
                if 'topics' not in df.columns:
                    df['topics'] = None
                
                # Basic stats
                st.subheader("Overview")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Posts", len(df))
                with col2:
                    st.metric("Avg. Engagement", f"{df['total_engagement'].mean():.1f}")
                with col3:
                    st.metric("Avg. Reactions", f"{df['reactions'].mean():.1f}")
                with col4:
                    st.metric("Avg. Comments", f"{df['comments'].mean():.1f}")
                
                # Tone and Topic Analysis
                st.subheader("Tone and Topic Analysis")
                
                # Check if we need to analyze content
                analyze_button = st.button("Analyze Content Tones and Topics")
                
                if analyze_button or (df['tone'].notna().sum() > 0 and df['topics'].notna().sum() > 0):
                    if analyze_button or df['tone'].isna().all() or df['topics'].isna().all():
                        with st.spinner("Analyzing content tones and topics..."):
                            # Add tone and topic analysis using Groq
                            content_analysis = analyze_content_with_groq(df)
                            
                            if content_analysis:
                                # Update the dataframe with analysis results
                                analyzed_df = content_analysis['analyzed_posts']
                                overall_analysis = content_analysis['overall_analysis']
                                
                                # Update the original dataframe with tone and topic information
                                for i, row in analyzed_df.iterrows():
                                    if pd.notna(row['tone']):
                                        df.loc[df.index == row.name, 'tone'] = row['tone']
                                    if pd.notna(row['topics']):
                                        df.loc[df.index == row.name, 'topics'] = row['topics']
                                
                                # Display overall analysis
                                st.write("### Content Tone Distribution")
                                
                                # Create tone distribution chart
                                dominant_tones = overall_analysis['dominant_tones']
                                tone_counts = {tone: len(df[df['tone'] == tone]) for tone in dominant_tones if tone in df['tone'].values}
                                
                                if tone_counts:
                                    tone_df = pd.DataFrame({
                                        'Tone': list(tone_counts.keys()),
                                        'Count': list(tone_counts.values())
                                    })
                                    
                                    fig = px.pie(
                                        tone_df,
                                        values='Count',
                                        names='Tone',
                                        title='Content Tone Distribution',
                                        color_discrete_sequence=px.colors.qualitative.Plotly
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                
                                # Display topic distribution
                                st.write("### Main Topics")
                                
                                # Extract all topics
                                all_topics = []
                                for topics_str in df['topics'].dropna():
                                    if topics_str:
                                        all_topics.extend([topic.strip() for topic in topics_str.split(',')])
                                
                                if all_topics:
                                    # Count topics
                                    topic_counts = pd.Series(all_topics).value_counts().head(10)
                                    
                                    fig = px.bar(
                                        x=topic_counts.index,
                                        y=topic_counts.values,
                                        labels={'x': 'Topic', 'y': 'Count'},
                                        title='Top 10 Topics',
                                        color=topic_counts.values,
                                        color_continuous_scale='Viridis'
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                                
                                # Display tone vs engagement
                                if df['tone'].notna().sum() > 0:
                                    st.write("### Tone vs. Engagement")
                                    
                                    tone_engagement = df.groupby('tone')['total_engagement'].mean().reset_index()
                                    tone_engagement = tone_engagement.sort_values('total_engagement', ascending=False)
                                    
                                    fig = px.bar(
                                        tone_engagement,
                                        x='tone',
                                        y='total_engagement',
                                        labels={'tone': 'Tone', 'total_engagement': 'Average Engagement'},
                                        title='Average Engagement by Content Tone',
                                        color='total_engagement',
                                        color_continuous_scale='Viridis'
                                    )
                                    st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.warning("Could not analyze content tones and topics. Please try again or check your Groq API key.")
                    else:
                        # Display existing tone and topic analysis
                        st.write("### Content Tone Distribution")
                        
                        # Create tone distribution chart
                        tone_counts = df['tone'].value_counts()
                        
                        if not tone_counts.empty:
                            fig = px.pie(
                                values=tone_counts.values,
                                names=tone_counts.index,
                                title='Content Tone Distribution',
                                color_discrete_sequence=px.colors.qualitative.Plotly
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Display topic distribution
                        st.write("### Main Topics")
                        
                        # Extract all topics
                        all_topics = []
                        for topics_str in df['topics'].dropna():
                            if topics_str:
                                all_topics.extend([topic.strip() for topic in topics_str.split(',')])
                        
                        if all_topics:
                            # Count topics
                            topic_counts = pd.Series(all_topics).value_counts().head(10)
                            
                            fig = px.bar(
                                x=topic_counts.index,
                                y=topic_counts.values,
                                labels={'x': 'Topic', 'y': 'Count'},
                                title='Top 10 Topics',
                                color=topic_counts.values,
                                color_continuous_scale='Viridis'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Display tone vs engagement
                        if df['tone'].notna().sum() > 0:
                            st.write("### Tone vs. Engagement")
                            
                            tone_engagement = df.groupby('tone')['total_engagement'].mean().reset_index()
                            tone_engagement = tone_engagement.sort_values('total_engagement', ascending=False)
                            
                            fig = px.bar(
                                tone_engagement,
                                x='tone',
                                y='total_engagement',
                                labels={'tone': 'Tone', 'total_engagement': 'Average Engagement'},
                                title='Average Engagement by Content Tone',
                                color='total_engagement',
                                color_continuous_scale='Viridis'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                
                # Content analysis sections
                st.subheader("Content Insights")
                
                # 1. Post Length Analysis
                length_analysis = analyze_post_length(df)
                if length_analysis:
                    st.write("### Post Length Impact")
                    
                    # Create bar chart for length vs engagement
                    fig = px.bar(
                        length_analysis['length_engagement'],
                        x='length_category',
                        y='total_engagement',
                        title='Average Engagement by Post Length',
                        color='length_category'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.info(f"**Optimal post length:** {length_analysis['optimal_category']} posts perform best")
                
                # 2. Hashtag Analysis
                hashtag_analysis = analyze_hashtags(df)
                if hashtag_analysis:
                    st.write("### Hashtag Effectiveness")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Most common hashtags
                        top_hashtags = hashtag_analysis['counts'].head(10)
                        fig = px.bar(
                            x=top_hashtags.index,
                            y=top_hashtags.values,
                            title='Most Common Hashtags',
                            labels={'x': 'Hashtag', 'y': 'Count'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Best performing hashtags
                        top_performing = hashtag_analysis['engagement'].head(10)
                        fig = px.bar(
                            top_performing,
                            x='hashtag',
                            y='mean',
                            title='Top Performing Hashtags',
                            labels={'hashtag': 'Hashtag', 'mean': 'Avg. Engagement'},
                            color='count',
                            color_continuous_scale='Viridis',
                            hover_data=['count']
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # 3. Top Performing Posts
                top_posts = get_top_posts(df)
                if not top_posts.empty:
                    st.write("### Top Performing Posts")
                    
                    for i, (_, post) in enumerate(top_posts.iterrows()):
                        with st.expander(f"#{i+1}: {post['total_engagement']} engagements ({post['post_date']})"):
                            st.write(post['post_text'])
                            engagement_text = f"Reactions: {post['reactions']} | Comments: {post['comments']}"
                            if 'reposts' in post and post['reposts'] > 0:
                                engagement_text += f" | Reposts: {post['reposts']}"
                            
                            # Add tone and topics if available
                            additional_info = ""
                            if pd.notna(post.get('tone')):
                                additional_info += f" | Tone: {post['tone']}"
                            if pd.notna(post.get('topics')):
                                additional_info += f" | Topics: {post['topics']}"
                                
                            st.caption(f"Profile: {post['profile_name']} | {engagement_text}{additional_info}")
                
                # 4. Content Strategy Recommendations
                st.write("### Content Strategy Recommendations")
                
                recommendations = []
                
                # Length recommendations
                if length_analysis:
                    recommendations.append(f"• Aim for **{length_analysis['optimal_category'].lower()}** posts (they get {length_analysis['length_engagement'].loc[length_analysis['length_engagement']['length_category'] == length_analysis['optimal_category'], 'total_engagement'].values[0]:.1f} avg. engagement)")
                
                # Hashtag recommendations
                if hashtag_analysis and not hashtag_analysis['engagement'].empty:
                    top_hashtags = hashtag_analysis['engagement'].head(3)['hashtag'].tolist()
                    recommendations.append(f"• Use high-performing hashtags: **{', '.join(top_hashtags)}**")
                
                # Tone recommendations
                if 'tone' in df.columns and df['tone'].notna().sum() > 0:
                    top_tone = df.groupby('tone')['total_engagement'].mean().sort_values(ascending=False).index[0]
                    recommendations.append(f"• Use a **{top_tone}** tone for higher engagement")
                
                # Topic recommendations
                if 'topics' in df.columns and df['topics'].notna().sum() > 0:
                    # Extract all topics
                    all_topics = []
                    for topics_str in df['topics'].dropna():
                        if topics_str:
                            all_topics.extend([topic.strip() for topic in topics_str.split(',')])
                    
                    if all_topics:
                        # Get top 3 topics
                        top_topics = pd.Series(all_topics).value_counts().head(3).index.tolist()
                        recommendations.append(f"• Focus on these topics: **{', '.join(top_topics)}**")
                
                # Post timing recommendations
                time_analysis = analyze_posting_time(df)
                if time_analysis:
                    recommendations.append(f"• Best day to post: **{time_analysis['best_day']}**")
                    recommendations.append(f"• Best time to post: **{int(time_analysis['best_hour']):02d}:00**")
                
                # Display recommendations
                for rec in recommendations:
                    st.markdown(rec)
                
                # Additional insights from top posts
                if not top_posts.empty:
                    st.info("**Key insight:** Your top-performing posts tend to be about specific topics and use an engaging tone. Consider using similar approaches for future content.")
    
    with tab3:
        st.header("Engagement Insights")
        
        if not data_exists and not sessions_exist:
            st.warning("No data available. Please scrape LinkedIn profiles first.")
        else:
            # Data selection
            data_source = st.radio(
                "Select data source for insights:",
                ["All data", "Most recent session", "Specific session", "Specific profile"],
                index=1 if sessions_exist else 0,
                key="insights_data_source"
            )
            
            df = None
            
            if data_source == "All data" and data_exists:
                df = pd.read_csv(data_file)
                st.write(f"Analyzing {len(df)} posts from all sessions")
            
            elif data_source == "Most recent session" and sessions_exist:
                # Get the most recent session file
                latest_session = max(session_files, key=lambda x: os.path.getmtime(os.path.join('data', x)))
                df = pd.read_csv(os.path.join('data', latest_session))
                session_id = latest_session.split('_')[-1].split('.')[0]
                st.write(f"Analyzing {len(df)} posts from session {session_id}")
            
            elif data_source == "Specific session" and sessions_exist:
                # Create a dropdown to select a specific session
                session_options = {}
                for file in session_files:
                    session_id = file.split('_')[-1].split('.')[0]
                    file_path = os.path.join('data', file)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        df_temp = pd.read_csv(file_path)
                        num_posts = len(df_temp)
                        profiles = ', '.join(df_temp['profile_name'].unique())
                    except:
                        num_posts = "Unknown"
                        profiles = "Unknown"
                    
                    session_options[session_id] = f"Session {session_id} - {modified_time} - {num_posts} posts - {profiles}"
                
                selected_session = st.selectbox(
                    "Select session for insights:",
                    list(session_options.keys()),
                    format_func=lambda x: session_options[x],
                    key="insights_session_select"
                )
                
                selected_file = f"linkedin_posts_{selected_session}.csv"
                df = pd.read_csv(os.path.join('data', selected_file))
                st.write(f"Analyzing {len(df)} posts from session {selected_session}")
            
            elif data_source == "Specific profile":
                if data_exists:
                    all_df = pd.read_csv(data_file)
                    profiles = sorted(all_df['profile_name'].unique())
                    
                    selected_profile = st.selectbox(
                        "Select profile for insights:",
                        profiles,
                        key="insights_profile_select"
                    )
                    
                    df = all_df[all_df['profile_name'] == selected_profile]
                    st.write(f"Analyzing {len(df)} posts from {selected_profile}")
            
            if df is not None and not df.empty:
                # Ensure total_engagement column exists
                if 'total_engagement' not in df.columns:
                    df['total_engagement'] = df['reactions'] + df['comments']
                    if 'reposts' in df.columns:
                        df['total_engagement'] += df['reposts']
                
                # 1. Best Time to Post - Heatmap
                time_analysis = analyze_posting_time(df)
                if time_analysis:
                    st.subheader("Best Time to Post")
                    
                    # Create pivot table for heatmap
                    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    pivot_data = time_analysis['heatmap_data'].pivot(index='day_of_week', columns='hour_of_day', values='total_engagement')
                    
                    # Reindex to ensure days are in correct order
                    pivot_data = pivot_data.reindex(days_order)
                    
                    # Create heatmap
                    fig = px.imshow(
                        pivot_data,
                        labels=dict(x="Hour of Day", y="Day of Week", color="Avg. Engagement"),
                        x=pivot_data.columns,
                        y=pivot_data.index,
                        color_continuous_scale='Viridis',
                        title='Average Engagement by Day and Hour'
                    )
                    
                    # Add peak times annotation
                    peak_times = time_analysis['heatmap_data'].sort_values('total_engagement', ascending=False).head(3)
                    peak_text = "Peak posting times:<br>"
                    for _, row in peak_times.iterrows():
                        peak_text += f"- {row['day_of_week']} at {int(row['hour_of_day']):02d}:00 ({row['total_engagement']:.1f} engagement)<br>"
                    
                    fig.add_annotation(
                        x=0.5,
                        y=-0.15,
                        xref="paper",
                        yref="paper",
                        text=peak_text,
                        showarrow=False,
                        font=dict(size=12),
                        align="left"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Day of week bar chart
                    st.subheader("Engagement by Day of Week")
                    
                    # Order days of week correctly
                    day_engagement = time_analysis['day_engagement']
                    day_engagement['day_of_week'] = pd.Categorical(day_engagement['day_of_week'], categories=days_order, ordered=True)
                    day_engagement = day_engagement.sort_values('day_of_week')
                    
                    fig = px.bar(
                        day_engagement,
                        x='day_of_week',
                        y='total_engagement',
                        title='Average Engagement by Day of Week',
                        labels={'day_of_week': 'Day of Week', 'total_engagement': 'Average Engagement'},
                        color='total_engagement',
                        color_continuous_scale='Viridis'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # 2. Engagement Breakdown
                st.subheader("Engagement Breakdown")
                
                if 'reactions' in df.columns and 'comments' in df.columns:
                    # Create a dataframe for the breakdown
                    engagement_types = ['Reactions', 'Comments']
                    engagement_values = [df['reactions'].mean(), df['comments'].mean()]
                    
                    if 'reposts' in df.columns:
                        engagement_types.append('Reposts')
                        engagement_values.append(df['reposts'].mean())
                    
                    engagement_breakdown = pd.DataFrame({
                        'Metric': engagement_types,
                        'Average': engagement_values
                    })
                    
                    # Create pie chart
                    fig = px.pie(
                        engagement_breakdown,
                        values='Average',
                        names='Metric',
                        title='Average Engagement Breakdown',
                        color_discrete_sequence=px.colors.sequential.Viridis
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # 3. Engagement Trend Over Time
                if 'post_date' in df.columns:
                    st.subheader("Engagement Trend Over Time")
                    
                    # Convert post_date to datetime
                    df['post_date'] = pd.to_datetime(df['post_date'], errors='coerce')
                    
                    # Filter out invalid dates
                    time_trend_df = df[pd.notna(df['post_date'])].copy()
                    
                    if not time_trend_df.empty:
                        # Sort by date
                        time_trend_df = time_trend_df.sort_values('post_date')
                        
                        # Create time series plot
                        fig = px.scatter(
                            time_trend_df,
                            x='post_date',
                            y='total_engagement',
                            color='profile_name',
                            labels={'post_date': 'Post Date', 'total_engagement': 'Total Engagement'},
                            title='Engagement Trend Over Time'
                        )
                        
                        # Add trendline
                        fig.add_traces(
                            px.scatter(
                                time_trend_df, 
                                x='post_date', 
                                y='total_engagement',
                                trendline='lowess'
                            ).data[1]
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Not enough date data available for trend analysis")
                else:
                    st.info("Post date data not available for trend analysis")
                
                # 4. Post Length vs. Engagement
                st.subheader("Post Length vs. Engagement")
                
                fig = px.scatter(
                    df, 
                    x='post_length', 
                    y='total_engagement',
                    color='profile_name',
                    hover_data=['post_date_text'] if 'post_date_text' in df.columns else ['post_date'],
                    trendline="ols",
                    labels={'post_length': 'Post Length (characters)', 'total_engagement': 'Total Engagement'},
                    title='Post Length vs. Engagement'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 5. Audience Insights
                st.subheader("Audience Insights")
                
                # Create a summary of what content works best
                st.write("### What Content Works Best")
                
                # Get top 3 posts
                top_3_posts = get_top_posts(df, 3)
                
                if not top_3_posts.empty:
                    # Extract common themes
                    common_themes = "Based on your top-performing posts, your audience engages most with:"
                    
                    # Check if posts have hashtags
                    has_hashtags = False
                    for _, post in top_3_posts.iterrows():
                        if 'hashtags' in post and post['hashtags']:
                            has_hashtags = True
                            break
                    
                    # Add insights based on data
                    insights = [
                        "• **Content type:** Original posts with clear value propositions",
                        f"• **Post length:** {analyze_post_length(df)['optimal_category'] if analyze_post_length(df) else 'Medium'} posts perform best",
                        "• **Hashtags:** " + ("Posts with relevant hashtags get more engagement" if has_hashtags else "Consider testing more hashtags in your posts"),
                        "• **Timing:** " + (f"Posts on {time_analysis['best_day']} at {int(time_analysis['best_hour']):02d}:00" if time_analysis else "Consider testing different posting times")
                    ]
                    
                    for insight in insights:
                        st.markdown(insight)
                    
                    st.info("**Pro tip:** Analyze the tone, structure, and topics of your top-performing posts to identify patterns you can replicate.")
    
    with tab4:
        st.header("Generate Content")
        
        if not data_exists and not sessions_exist:
            st.warning("No data available. Please scrape LinkedIn profiles first.")
        else:
            # Check if GROQ API key is available
            groq_api_key = os.getenv("GROQ_API_KEY")
            if not groq_api_key:
                st.warning("GROQ API key not found in environment variables. Content generation will not work.")
            
            # Content generation method selection
            generation_method = st.radio(
                "How would you like to generate content?",
                ["Based on a topic", "Based on top performing post"],
                key="generation_method"
            )
            
            if generation_method == "Based on a topic":
                st.subheader("Generate Content Based on Topic")
                
                # Topic input
                topic = st.text_area(
                    "Enter the topic or idea for your LinkedIn post:",
                    placeholder="E.g., AI in healthcare, Remote work best practices, Leadership skills",
                    height=100
                )
                
                # Option to include popular hashtags
                include_popular_hashtags = st.checkbox("Include popular hashtags from your data")
                popular_hashtags = None
                
                if include_popular_hashtags:
                    # Get popular hashtags from data
                    if data_exists:
                        try:
                            if 'all_df' not in locals():
                                all_df = pd.read_csv(data_file)
                            
                            # Extract all hashtags
                            all_hashtags = []
                            for tags in all_df['hashtags'].dropna():
                                if tags:
                                    all_hashtags.extend([tag.strip() for tag in tags.split(',')])
                            
                            if all_hashtags:
                                # Count hashtags and get top 10
                                hashtag_counts = pd.Series(all_hashtags).value_counts().head(10)
                                popular_hashtags = ", ".join(hashtag_counts.index)
                                st.info(f"Popular hashtags: {popular_hashtags}")
                            else:
                                st.info("No hashtags found in your data")
                        except Exception as e:
                            st.error(f"Error getting popular hashtags: {str(e)}")
                
                # Generate button
                if st.button("Generate Content from Topic"):
                    if not topic:
                        st.error("Please enter a topic for your post")
                    else:
                        with st.spinner("Generating content with Groq AI..."):
                            # Store current parameters in session state
                            st.session_state.current_topic = topic
                            st.session_state.current_hashtags = popular_hashtags
                            st.session_state.current_example_post = None
                            st.session_state.current_day = None
                            st.session_state.current_hour = None
                            st.session_state.current_reactions = None
                            st.session_state.current_comments = None
                            st.session_state.current_post_hashtags = None
                            
                            # Generate posts
                            generated_posts = generate_content_with_groq(
                                topic=topic,
                                popular_hashtags=popular_hashtags
                            )
                            
                            # Store generated posts in session state
                            st.session_state.generated_posts = generated_posts
                            st.session_state.refined_posts = []
                            st.session_state.feedback_submitted = False
                
                # Display generated posts if available
                if 'generated_posts' in st.session_state and st.session_state.generated_posts:
                    generated_posts = st.session_state.generated_posts
                    
                    if generated_posts and not isinstance(generated_posts, str) and len(generated_posts) > 0:
                        st.subheader("Generated Content")
                        
                        # Display each post variation
                        for i, post in enumerate(generated_posts[:3]):  # Limit to 3 posts
                            st.write(f"**Post Variation {i+1}:**")
                            st.info(post)
                        
                        # Add a single feedback box at the end
                        st.write("### Provide Feedback")
                        feedback = st.text_area(
                            "What would you like to change or improve in these posts?",
                            placeholder="E.g., Make them shorter, Add more examples, Change the tone, Add more hashtags",
                            height=100,
                            key="feedback_all"
                        )
                        
                        # Regenerate button
                        if st.button("Regenerate with Feedback", key="regenerate_topic"):
                            if feedback:
                                with st.spinner("Regenerating posts with your feedback..."):
                                    # Generate refined posts
                                    refined_posts = generate_content_with_groq(
                                        topic=st.session_state.current_topic,
                                        popular_hashtags=st.session_state.current_hashtags,
                                        feedback=feedback
                                    )
                                    
                                    # Store refined posts in session state
                                    st.session_state.refined_posts = refined_posts
                                    st.session_state.feedback_submitted = True
                        
                        # Display refined posts if available
                        if st.session_state.feedback_submitted and st.session_state.refined_posts:
                            refined_posts = st.session_state.refined_posts
                            
                            if refined_posts and not isinstance(refined_posts, str) and len(refined_posts) > 0:
                                st.subheader("Refined Content")
                                
                                # Display each refined post
                                for i, post in enumerate(refined_posts[:3]):  # Limit to 3 posts
                                    st.write(f"**Refined Post {i+1}:**")
                                    st.info(post)
                                
                                # Copy button for the first post
                                st.text_area("Copy this content:", value=refined_posts[0], height=300)
                            else:
                                st.error("Failed to regenerate content. Please try again.")
                        
                        # Copy button for the first post if no refined posts
                        if not st.session_state.feedback_submitted or not st.session_state.refined_posts:
                            st.text_area("Copy this content:", value=generated_posts[0], height=300)
            
            else:  # Based on top performing post
                # Data selection
                data_source = st.radio(
                    "Select data source for content generation:",
                    ["All data", "Most recent session", "Specific session", "Specific profile"],
                    index=1 if sessions_exist else 0,
                    key="generate_data_source"
                )
                
                df = None
                
                if data_source == "All data" and data_exists:
                    df = pd.read_csv(data_file)
                    st.write(f"Using {len(df)} posts from all sessions")
                
                elif data_source == "Most recent session" and sessions_exist:
                    # Get the most recent session file
                    latest_session = max(session_files, key=lambda x: os.path.getmtime(os.path.join('data', x)))
                    df = pd.read_csv(os.path.join('data', latest_session))
                    session_id = latest_session.split('_')[-1].split('.')[0]
                    st.write(f"Using {len(df)} posts from session {session_id}")
                
                elif data_source == "Specific session" and sessions_exist:
                    # Create a dropdown to select a specific session
                    session_options = {}
                    for file in session_files:
                        session_id = file.split('_')[-1].split('.')[0]
                        file_path = os.path.join('data', file)
                        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M:%S')
                        try:
                            df_temp = pd.read_csv(file_path)
                            num_posts = len(df_temp)
                            profiles = ', '.join(df_temp['profile_name'].unique())
                        except:
                            num_posts = "Unknown"
                            profiles = "Unknown"
                        
                        session_options[session_id] = f"Session {session_id} - {modified_time} - {num_posts} posts - {profiles}"
                    
                    selected_session = st.selectbox(
                        "Select session for content generation:",
                        list(session_options.keys()),
                        format_func=lambda x: session_options[x],
                        key="generate_session_select"
                    )
                    
                    selected_file = f"linkedin_posts_{selected_session}.csv"
                    df = pd.read_csv(os.path.join('data', selected_file))
                    st.write(f"Using {len(df)} posts from session {selected_session}")
                
                elif data_source == "Specific profile":
                    if data_exists:
                        all_df = pd.read_csv(data_file)
                        profiles = sorted(all_df['profile_name'].unique())
                        
                        selected_profile = st.selectbox(
                            "Select profile for content generation:",
                            profiles,
                            key="generate_profile_select"
                        )
                        
                        df = all_df[all_df['profile_name'] == selected_profile]
                        st.write(f"Using {len(df)} posts from {selected_profile}")
                
                if df is not None and not df.empty and groq_api_key:
                    # Ensure total_engagement column exists
                    if 'total_engagement' not in df.columns:
                        df['total_engagement'] = df['reactions'] + df['comments']
                        if 'reposts' in df.columns:
                            df['total_engagement'] += df['reposts']
                    
                    # Get top performing post as example
                    top_post = df.sort_values('total_engagement', ascending=False).iloc[0]
                    
                    st.subheader("Generate Content Based on Top Performing Post")
                    
                    # Display top post
                    st.write("**Top performing post:**")
                    st.info(top_post['post_text'])
                    engagement_text = f"Engagement: {top_post['total_engagement']} | Reactions: {top_post['reactions']} | Comments: {top_post['comments']}"
                    if 'reposts' in top_post and top_post['reposts'] > 0:
                        engagement_text += f" | Reposts: {top_post['reposts']}"
                    st.caption(f"{engagement_text} | Posted on: {top_post['day_of_week']} at {top_post['hour_of_day']}:00")
                    
                    # Content generation options
                    st.subheader("Content Generation Options")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        target_day = st.selectbox(
                            "Target day of week:",
                            days_order,
                            index=days_order.index(top_post['day_of_week']) if 'day_of_week' in top_post and top_post['day_of_week'] in days_order else 0
                        )
                    
                    with col2:
                        target_hour = st.slider(
                            "Target hour of day:",
                            0, 23, 
                            int(top_post['hour_of_day']) if 'hour_of_day' in top_post and top_post['hour_of_day'] != 'Unknown' else 9
                        )
                    
                    # Generate button
                    if st.button("Generate Content from Top Post"):
                        with st.spinner("Generating content with Groq AI..."):
                            # Store current parameters in session state
                            st.session_state.current_topic = None
                            st.session_state.current_hashtags = None
                            st.session_state.current_example_post = top_post['post_text']
                            st.session_state.current_day = target_day
                            st.session_state.current_hour = target_hour
                            st.session_state.current_reactions = top_post['reactions']
                            st.session_state.current_comments = top_post['comments']
                            st.session_state.current_post_hashtags = top_post['hashtags'] if 'hashtags' in top_post else None
                            
                            # Generate posts
                            generated_posts = generate_content_with_groq(
                                example_post=top_post['post_text'],
                                day_of_week=target_day,
                                hour_of_day=target_hour,
                                reactions=top_post['reactions'],
                                comments=top_post['comments'],
                                hashtags=top_post['hashtags'] if 'hashtags' in top_post else None
                            )
                            
                            # Store generated posts in session state
                            st.session_state.generated_posts = generated_posts
                            st.session_state.refined_posts = []
                            st.session_state.feedback_submitted = False
                    
                    # Display generated posts if available
                    if 'generated_posts' in st.session_state and st.session_state.generated_posts:
                        generated_posts = st.session_state.generated_posts
                        
                        if generated_posts and not isinstance(generated_posts, str) and len(generated_posts) > 0:
                            st.subheader("Generated Content")
                            
                            # Display each post variation
                            for i, post in enumerate(generated_posts[:3]):  # Limit to 3 posts
                                st.write(f"**Post Variation {i+1}:**")
                                st.info(post)
                            
                            # Add a single feedback box at the end
                            st.write("### Provide Feedback")
                            feedback = st.text_area(
                                "What would you like to change or improve in these posts?",
                                placeholder="E.g., Make them shorter, Add more examples, Change the tone, Add more hashtags",
                                height=100,
                                key="feedback_top_all"
                            )
                            
                            # Regenerate button
                            if st.button("Regenerate with Feedback", key="regenerate_top_post"):
                                if feedback:
                                    with st.spinner("Regenerating posts with your feedback..."):
                                        # Generate refined posts
                                        refined_posts = generate_content_with_groq(
                                            example_post=st.session_state.current_example_post,
                                            day_of_week=st.session_state.current_day,
                                            hour_of_day=st.session_state.current_hour,
                                            reactions=st.session_state.current_reactions,
                                            comments=st.session_state.current_comments,
                                            hashtags=st.session_state.current_post_hashtags,
                                            feedback=feedback
                                        )
                                        
                                        # Store refined posts in session state
                                        st.session_state.refined_posts = refined_posts
                                        st.session_state.feedback_submitted = True
                            
                            # Display refined posts if available
                            if st.session_state.feedback_submitted and st.session_state.refined_posts:
                                refined_posts = st.session_state.refined_posts
                                
                                if refined_posts and not isinstance(refined_posts, str) and len(refined_posts) > 0:
                                    st.subheader("Refined Content")
                                    
                                    # Display each refined post
                                    for i, post in enumerate(refined_posts[:3]):  # Limit to 3 posts
                                        st.write(f"**Refined Post {i+1}:**")
                                        st.info(post)
                                    
                                    # Copy button for the first post
                                    st.text_area("Copy this content:", value=refined_posts[0], height=300)
                                else:
                                    st.error("Failed to regenerate content. Please try again.")
                            
                            # Copy button for the first post if no refined posts
                            if not st.session_state.feedback_submitted or not st.session_state.refined_posts:
                                st.text_area("Copy this content:", value=generated_posts[0], height=300)

if __name__ == "__main__":
    main()