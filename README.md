streamlit_content_recognizer

Streamlit app that takes a social post URL, fetches it with Bright Data proxies, and summarizes the content using Gemini.

If a page exposes a video URL (e.g., via `og:video`), the app will download the video and ask Gemini to describe what happens in it.

Quick start:

1) Install deps
   - pip install streamlit requests google-genai

2) Run
   - streamlit run app.py

3) Set secrets (required):

Create `.streamlit/secrets.toml`:

```
BRIGHT_PROXY_HOST = "brd.superproxy.io"
BRIGHT_PROXY_PORT = "33335"
BRIGHT_PROXY_USER = "YOUR_PROXY_USERNAME"
BRIGHT_PROXY_PASS = "YOUR_PROXY_PASSWORD"
GEMINI_API_KEY = "YOUR_KEY"
GEMINI_MODEL = "gemini-3-flash-preview"
```

4) In the app, provide:
   - Social post URL
