LinkedIn Content Analyzer
A powerful tool to analyze and generate LinkedIn content tailored to individual profiles.

This application helps you uncover what content performs best for a specific LinkedIn user, determine the optimal posting times, and even generate posts in their unique tone and voice. Whether you're growing your own personal brand or optimizing a client’s content strategy, this tool delivers data-driven insights and personalized recommendations.

📎 [**Demo Video**](https://drive.google.com/file/d/10iJ4H6wCFZ_-wyjJBS37e1QpMxN8zaIk/view?usp=sharing)

---

## 🔍 What Makes It Unique?

Unlike generic LinkedIn tools, **this analyzer focuses on specific LinkedIn profiles**.

You can scrape all posts from a targeted profile, analyze engagement patterns, extract top-performing topics, tone, and CTA styles — and generate new content that matches their style and success metrics.

Perfect for creators, consultants, or brand managers working with individuals.

---

## 🚀 Features

### 1. Scrape Data from Specific Profiles
- Scrape **all available posts** from any **public or authorized LinkedIn profile**
- Configure scraping options: `headless`, `debug`, `max post count`
- Export data as CSV
- Robust login and session error handling

### 2. Analyze Content Performance
- Identify what types of content work best for a **specific profile**
- Extract top-performing **topics**, **keywords**, and **post tone**
- Evaluate **call-to-action effectiveness**
- View top posts with engagement breakdown

### 3. Engagement Insights
- Discover **best posting times** for maximum reach
- Analyze **hashtag effectiveness** and usage frequency
- Understand how **post length** affects engagement
- Visualize reactions, comments, and repost patterns

### 4. AI-Powered Content Generation
- Generate new posts inspired by your **top-performing content**
- Adjust tone, CTA style, hashtags, and length
- Recommend optimal post timing
- Create **multiple variations** and refine based on feedback
- Copy content directly to clipboard

---

## ⚙️ Technical Overview

### Architecture

- **Streamlit App** with four interactive tabs:
  - Scraping
  - Analysis
  - Insights
  - Content Generation
- **Modular backend** for LinkedIn scraping, content analysis, and generation
- Smooth and responsive interface for minimal load time

### Key Components

- `app.py`: Streamlit app logic and routing
- `linkedin_scraper.py`: Scrapes posts and engagement data from specific profiles
- Content Analyzer: Keyword extraction, sentiment and tone analysis, CTA evaluation
- Content Generator: AI-powered (Groq API), template-based fallback

# 🛠️ Installation and Setup

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git (optional, for cloning the repo)

---

## 📦 Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/kartiknarang04/linkedin-scraper.git
   cd linkedin-scraper
   pip install -r requirements.txt
2. **Create a .env file in the root directory and add the following**
   ```bash
   LINKEDIN_EMAIL=your_email@example.com
   LINKEDIN_PASSWORD=your_password
   GROQ_API_KEY=your_groq_api_key
3. **Run the app**
   ```bash
   streamlit run app.py

