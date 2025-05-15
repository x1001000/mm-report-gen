import streamlit as st
from google import genai
from google.genai import types
from Markdown2docx import Markdown2docx

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

st.title("🖨️ MM Report Gen")
user_prompt = st.text_area(
    '[Macro Weekly 250414 華威國際週報範本.pdf](https://drive.google.com/file/d/1g9-8X5WhC_KccUFy525qayxHocLcjjDA/view?usp=sharing) 生成的提示詞如下，可編輯後送出，生成類似的報告',
    """Act as a financial and business news analyst compiling a daily briefing. Create a comprehensive report summarizing key market, economic, political, and tech news for the past week, in Markdown format.

Organize the report into distinct sections using bold headings and numbered bullet points for each news item. Include the following sections:

*   **Macro:** Summarize key economic data releases, consumer sentiment, inflation figures, etc.
*   **Capital Market:** Report on major market indices performance, bond yields, currency movements, notable analyst calls, fund flows.
*   **Cloud, Internet:** Cover significant news related to cloud computing infrastructure, internet service providers, major internet companies (excluding specific ones with their own sections).
*   **Macro-tariffs:** Detail developments in international trade policy, tariffs, and related political statements or actions.
*   **Retail Related:** Summarize retail sales data, company performance (excluding Amazon), industry trends, and relevant consumer news.
*   **China-related:** Focus on economic, business, and trade news specifically pertaining to China, especially its interactions with the US.
*   **Education & Lifestyle:** Report on news in education, entertainment, consumer lifestyle, etc.
*   **Autos & Transportation:** Cover news in the automotive industry, transportation, and related technologies.
*   **Google:** Summarize news specifically about Google/Alphabet.
*   **Social-Meta:** Summarize news specifically about Meta (Facebook, Instagram, etc.) and other social media companies.
*   **Healthcare:** Report on news in the healthcare industry, pharmaceuticals, policy, etc.
*   **AI:** Cover significant developments, research, company actions, and policy related to Artificial Intelligence.
*   **Device, H/W:** Summarize news about consumer electronics, semiconductors, hardware manufacturing, and related supply chains.
*   **Amazon:** Summarize news specifically about Amazon (e-commerce, cloud, logistics, devices, etc.).

Ensure each bullet point is a brief, factual summary. Where possible, include specific numbers, percentages, dates, comparisons (e.g., Y/Y, M/M, vs. expected), and mention the source (e.g., Bloomberg, Freddie Mac, analyst name) or context (e.g., "highest since...", "smallest since..."). Maintain an objective and professional tone.""",
    height=850,
)
if 'response' not in st.session_state:
    st.session_state.response = None
if 'response_text_citation' not in st.session_state:
    st.session_state.response_text_citation = None
if 'response_text_house_view' not in st.session_state:
    st.session_state.response_text_house_view = None
if st.button("生成報告", type="primary"):
    with st.spinner("生成中...", show_time=True):
        try:
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
        for grounding_support in response.model_dump()['candidates'][0]['grounding_metadata']['grounding_supports'][::-1]:
            marker = ''
            for i in grounding_support['grounding_chunk_indices']:
                marker += f'[[{i}]]'
            response_text = response_text.replace(grounding_support['segment']['text'], grounding_support['segment']['text'] + marker)
        response_text += '\n\n\n'
        for i, grounding_chunk in enumerate(response.model_dump()['candidates'][0]['grounding_metadata']['grounding_chunks']):
            response_text += f"[{i}]: {grounding_chunk['web']['uri']}\n"
        st.session_state.response_text_citation = response_text
    '---'
    st.session_state.response_text_citation
    if st.button("加上 MM House View", type="primary"):
        with st.spinner("生成 MM House View...", show_time=True):
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
                system_prompt = "Generate a MacroMicro House View for the report with uploaded MacroMicro content"
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
        md = st.session_state.response_text_citation + st.session_state.response_text_house_view
        with open('mm_report.md', 'w') as f:
            f.write(md)
        project = Markdown2docx('mm_report')
        project.eat_soup()
        project.save()
        with open('mm_report.docx', "rb") as file:
            file_bytes = file.read()
        # Add download button
        st.download_button(
            label="下載 Word 檔案",
            data=file_bytes,
            file_name="mm_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type='primary',
        )