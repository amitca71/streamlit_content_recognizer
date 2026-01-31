import json
import re
import tempfile
import textwrap

import requests
import streamlit as st


def extract_meta_tags(html_text: str) -> dict:
    meta = {}
    for key in ["og:title", "og:description", "og:image", "og:video", "twitter:title", "twitter:description"]:
        match = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
            html_text,
            flags=re.IGNORECASE,
        )
        if match:
            meta[key] = match.group(1)
    return meta


class SimpleHTMLStripper:
    def __init__(self) -> None:
        self._text = []

    def feed(self, html_text: str) -> None:
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
        cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        self._text.append(cleaned.strip())

    def get_text(self) -> str:
        return " ".join(self._text).strip()


def html_to_text(html_text: str) -> str:
    stripper = SimpleHTMLStripper()
    stripper.feed(html_text)
    return stripper.get_text()


def fetch_via_bright_proxy(host: str, port: int, user: str, password: str, url: str) -> requests.Response:
    proxies = {
        "http": f"http://{user}:{password}@{host}:{port}",
        "https": f"http://{user}:{password}@{host}:{port}",
    }
    response = requests.get(url, proxies=proxies, timeout=60)
    response.raise_for_status()
    return response


def call_gemini(api_key: str, model: str, prompt: str, media_path: str | None = None) -> str:
    try:
        from google import genai
    except Exception as exc:
        raise RuntimeError("Missing dependency: google-genai. Run `pip install google-genai`.") from exc

    client = genai.Client(api_key=api_key)
    if media_path:
        uploaded = client.files.upload(file=media_path)
        response = client.models.generate_content(model=model, contents=[uploaded, prompt])
    else:
        response = client.models.generate_content(model=model, contents=prompt)
    return getattr(response, "text", "") or ""


st.set_page_config(page_title="Social Post Summarizer", page_icon="🧠", layout="centered")
st.title("🧠 Social Post Summarizer")

bright_host = st.secrets.get("BRIGHT_PROXY_HOST", "brd.superproxy.io")
bright_port = int(st.secrets.get("BRIGHT_PROXY_PORT", 33335))
bright_user = st.secrets.get("BRIGHT_PROXY_USER", "")
bright_pass = st.secrets.get("BRIGHT_PROXY_PASS", "")

llm_key = st.secrets.get("GEMINI_API_KEY", "")
model_name = st.secrets.get("GEMINI_MODEL", "gemini-3-flash-preview")

st.header("Analyze a Social Post")
sample_urls = [
    "https://t.me/abualiexpress/105824",
    "https://t.me/abualiexpress/105838",
    "https://t.me/shikmabressler24/145",
    "https://beactive.co.il/project/84917",
]
selected_sample = st.selectbox("Sample URLs", ["(select a sample)"] + sample_urls)

if selected_sample != "(select a sample)":
    st.session_state["post_url"] = selected_sample

url = st.text_input("Post URL", key="post_url")

if st.button("Summarize"):
    if not url:
        st.error("Please enter a URL.")
        st.stop()
    if not bright_host or not bright_user or not bright_pass:
        st.error("Missing Bright Data proxy settings in secrets.")
        st.stop()
    if not llm_key:
        st.error("Missing GEMINI_API_KEY in secrets.")
        st.stop()

    with st.spinner("Fetching post data via Bright Data proxy..."):
        try:
            response = fetch_via_bright_proxy(bright_host, bright_port, bright_user, bright_pass, url)
        except Exception as exc:
            st.error(f"Bright Data proxy error: {exc}")
            st.stop()

    content_type = response.headers.get("Content-Type", "")
    meta = {}
    video_url = None
    if "text/html" in content_type:
        raw_text = response.text
        meta = extract_meta_tags(raw_text)
        video_url = meta.get("og:video")
        text_content = html_to_text(raw_text)
    elif "application/json" in content_type:
        try:
            parsed = response.json()
            text_content = json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            text_content = response.text
    else:
        text_content = f"Non-text content fetched. Content-Type: {content_type}. Size: {len(response.content)} bytes."

    text_content = textwrap.shorten(text_content, width=6000, placeholder=" ...")

    st.subheader("Bright Data Response (preview)")
    preview = text_content[:1500] if isinstance(text_content, str) else str(text_content)[:1500]
    st.code(preview, language="text")

    prompt = (
        "You are analyzing a social media post. Summarize what it is about and infer the content types present. "
        "Possible types: text, image, video, audio. More than one can apply. Use the extracted content and metadata.\n\n"
        "Respond in Hebrew.\n\n"
        f"URL: {url}\n\n"
        f"Metadata: {json.dumps(meta, ensure_ascii=False)}\n\n"
        f"Content:\n{text_content}\n\n"
        "If a video is provided, also describe what happens in the video.\n\n"
        "In your answer, include: (1) a concise summary, (2) the detected content types, "
        "(3) which content types were successfully analyzed."
    )

    media_path = None
    if video_url:
        with st.spinner("Downloading video for analysis..."):
            try:
                video_resp = fetch_via_bright_proxy(
                    bright_host, bright_port, bright_user, bright_pass, video_url
                )
                suffix = ".mp4"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                    tmp_file.write(video_resp.content)
                    media_path = tmp_file.name
                st.success("Video downloaded for analysis.")
            except Exception as exc:
                st.warning(f"Video download failed: {exc}")

    with st.spinner("Analyzing with Gemini..."):
        try:
            result = call_gemini(llm_key, model_name, prompt, media_path=media_path)
        except Exception as exc:
            st.error(str(exc))
            st.stop()
        finally:
            if media_path:
                try:
                    import os

                    os.remove(media_path)
                except Exception:
                    pass

    if not result:
        st.warning("No response returned from the model.")
    else:
        st.subheader("Summary")
        st.write(result)
