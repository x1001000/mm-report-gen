import streamlit as st
from google import genai
from google.genai import types

import markdown
from htmldocx import HtmlToDocx
from docx import Document
import io

client = genai.Client(api_key=st.secrets['GEMINI_API_KEY'])
model = 'gemini-2.5-flash-preview-04-17'
price = {
    'gemini-2.0-flash': {'input': 0.1, 'output': 0.4},
    'gemini-2.5-flash-preview-04-17': {'input': 0.15, 'output': 0.6, 'thinking': 3.5},
}

prompt_token_count = 0
candidates_token_count = 0
cached_content_token_count = 0
thoughts_token_count = 0
tool_use_prompt_token_count = 0
total_token_count = 0
def accumulate_token_count(usage_metadata):
    global prompt_token_count, candidates_token_count, cached_content_token_count, thoughts_token_count, tool_use_prompt_token_count, total_token_count
    prompt_token_count += usage_metadata.prompt_token_count
    candidates_token_count += usage_metadata.candidates_token_count
    cached_content_token_count += usage_metadata.cached_content_token_count if usage_metadata.cached_content_token_count else 0
    thoughts_token_count += usage_metadata.thoughts_token_count if usage_metadata.thoughts_token_count else 0
    tool_use_prompt_token_count += usage_metadata.tool_use_prompt_token_count if usage_metadata.tool_use_prompt_token_count else 0
    total_token_count += usage_metadata.total_token_count
def cost():
    return round((prompt_token_count * price[model]['input'] + candidates_token_count * price[model]['output'] + thoughts_token_count * price[model]['thinking'])/1e6, 2)

def generate_content(user_prompt, system_prompt, response_type, response_schema, tools):
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type=response_type,
            response_schema=response_schema,
            tools=tools,
        )
    )
    accumulate_token_count(response.usage_metadata)
    return response

if 'ai_generated_prompt' not in st.session_state:
    st.session_state.ai_generated_prompt = None
if 'response' not in st.session_state:
    st.session_state.response = None
if 'response_text_citation' not in st.session_state:
    st.session_state.response_text_citation = None
if 'response_text_house_view' not in st.session_state:
    st.session_state.response_text_house_view = None

with st.sidebar:
    uploaded_file = st.file_uploader("Upload Report to generate Prompt", type=['pdf', 'docx', 'md'])
    if uploaded_file and not st.session_state.ai_generated_prompt:
        import os
        saved_path = os.path.join('uploads', uploaded_file.name)
        with open(saved_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        with st.spinner("Generating Prompt...", show_time=True):
            try:
                myfile = client.files.upload(file=saved_path)
                user_prompt = ['to generate a weekly brief report like this file, for the past week, show me the prompt:', myfile]
                system_prompt = None
                response_type = 'text/plain'
                response_schema = None
                tools = None
                response_text = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
                st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens + {thoughts_token_count} thinking tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")
            except Exception as e:
                st.code(f"Errrr: {e}")
                st.stop()
        st.session_state.ai_generated_prompt = st.text_area('Edit the AI generated Prompt. REMOVE UNWANTED part.', response_text, height=850)
    elif st.session_state.ai_generated_prompt:
        st.text_area('Edit the AI generated Prompt. REMOVE UNWANTED part.', st.session_state.ai_generated_prompt, height=850)

st.title("🖨️ MM Report Gen")
if uploaded_file and st.button("Generate Report", type="primary"):
    with st.spinner("Generating Report...", show_time=True):
        try:
            user_prompt = st.session_state.ai_generated_prompt
            system_prompt = None
            response_type = 'text/plain'
            response_schema = None
            tools = [types.Tool(google_search=types.GoogleSearch())]
            st.session_state.response = generate_content(user_prompt, system_prompt, response_type, response_schema, tools)
            st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens + {thoughts_token_count} thinking tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")
        except Exception as e:
            st.code(f"Errrr: {e}")
            st.stop()
if st.session_state.response:
    if not st.session_state.response_text_citation:
        response = st.session_state.response
        response_text = response.text
        if grounding_supports := response.model_dump()['candidates'][0]['grounding_metadata']['grounding_supports']:
            for grounding_support in grounding_supports:
                marker = ''
                for i in grounding_support['grounding_chunk_indices']:
                    marker += f'[[{i+1}]]'
                response_text = response_text.replace(grounding_support['segment']['text'], grounding_support['segment']['text'] + marker)
            # response_text += '\n\n\n'
            for i, grounding_chunk in enumerate(response.model_dump()['candidates'][0]['grounding_metadata']['grounding_chunks']):
                # Reference-style Links cannot be converted to HTML
                # response_text += f"[{i}]: {grounding_chunk['web']['uri']}\n"
                response_text = response_text.replace(f"[{i+1}]", f"[{i+1}]({grounding_chunk['web']['uri']})")
        st.session_state.response_text_citation = response_text
    '---'
    st.session_state.response_text_citation
    if st.button("Generate Analysis", type="primary"):
        with st.spinner("Generating Analysis...", show_time=True):
            try:
                import glob
                files = []
                for file in glob.glob('knowledge/*.pdf'):
                    files.append(client.files.upload(file=file))
                user_prompt = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_uri(
                                file_uri=file.uri,
                                mime_type=file.mime_type,
                            ) for file in files
                        ] + [
                            types.Part.from_text(text=st.session_state.response.text),
                        ],
                    ),
                ]
                system_prompt = "Use data and content of MacroMicro, generate MM Analyst section which offers valuable insights into the Macro section in the report"
                response_type = 'text/plain'
                response_schema = None
                tools = None
                st.session_state.response_text_house_view = generate_content(user_prompt, system_prompt, response_type, response_schema, tools).text
                st.badge(f'{prompt_token_count} input tokens + {candidates_token_count} output tokens + {thoughts_token_count} thinking tokens ≒ {cost()} USD ( when Google Search < 1500 Requests/Day )', icon="💰", color="green")
            except Exception as e:
                st.code(f"Errrr: {e}")
                st.stop()
    if st.session_state.response_text_house_view:
        '---'
        st.session_state.response_text_house_view
        markdown_text = st.session_state.response_text_citation + st.session_state.response_text_house_view

        # 將Markdown轉換為HTML
        html = markdown.markdown(markdown_text)
        # 創建一個Word文檔
        doc = Document()
        
        # 使用htmldocx將HTML轉換為Word
        parser = HtmlToDocx()
        parser.add_html_to_document(html, doc)
        
        # 保存為BytesIO對象以便在Streamlit中下載
        docx_io = io.BytesIO()
        doc.save(docx_io)
        docx_io.seek(0)

        # Add download buttons
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Word file",
                data=docx_io,
                file_name="MacroMicro_AI_Generated_Report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type='primary',
            )
        with col2:
            st.download_button(
                label="Download Markdown file",
                data=markdown_text,
                file_name="MacroMicro_AI_Generated_Report.md",
                mime="text/markdown",
                type='primary',
            )