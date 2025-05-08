import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
import re
import logging
import langdetect
import random
import urllib.parse
import requests
from bs4 import BeautifulSoup

# Set up logging to help with debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Define base URL for knowledge linking
BASE_KNOWLEDGE_URL = "https://knowledge.example.com"

def detect_language(text):
    """Detect if text is Arabic or English."""
    try:
        language = langdetect.detect(text)
        if language == 'ar':
            return 'arabic'
        else:
            return 'english'
    except:
        # Default to English if detection fails
        return 'english'

def get_color_palette():
    """Return a visually clear and consistent color palette."""
    return {
        "feature": "#4CAF50",   # Green (for features, growth, success)
        "benefit": "#FF9800",   # Orange (for benefits, attraction)
        "technology": "#2196F3", # Blue (for tech, innovation)
    }

def search_related_url(text, language='english'):
    """
    Search for a URL related to the text content using Google Search.
    Returns a relevant URL or falls back to a generated URL if search fails.
    """
    try:
        # Remove quotes and other special characters
        clean_text = re.sub(r'["\'<>\[\]()]', '', text).strip()
        
        # Use the gemini model to generate a relevant URL
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        if language == 'arabic':
            prompt = f"""
            أنا بحاجة إلى عنوان URL حقيقي وموثوق به متعلق بـ "{clean_text}".
            يجب أن يكون عنوان URL حقيقيًا (مثل موقع ويكيبيديا أو موقع رسمي أو منظمة معروفة).
            أعطني فقط عنوان URL واحدًا كاملًا بدون أي توضيحات أو تعليقات إضافية.
            مثال على الإخراج: https://ar.wikipedia.org/wiki/مثال
            """
        else:
            prompt = f"""
            I need a real, authoritative URL related to "{clean_text}".
            The URL should be real (like a Wikipedia page, official website, or well-known organization).
            Give me just a single complete URL with no additional explanations or comments.
            Example output: https://en.wikipedia.org/wiki/Example
            """
        
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 20,
            "max_output_tokens": 256
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Extract URL from response
        url_match = re.search(r'(https?://[^\s"\'<>]+)', response.text)
        if url_match:
            url = url_match.group(1)
            
            # Validate the URL with a HEAD request
            try:
                # Use a timeout to avoid hanging
                head_response = requests.head(url, timeout=3)
                if head_response.status_code < 400:  # URL exists
                    logger.info(f"Found valid URL for '{clean_text}': {url}")
                    return url
            except requests.RequestException:
                logger.warning(f"URL validation failed for '{url}'")
        
        # Fallback: Create a path using the base knowledge URL
        slug = re.sub(r'[^\w\s-]', '', clean_text.lower()).strip()
        slug = re.sub(r'[\s-]+', '-', slug)
        safe_slug = urllib.parse.quote(slug)
        fallback_url = f"{BASE_KNOWLEDGE_URL}/{safe_slug}"
        
        logger.info(f"Using fallback URL for '{clean_text}': {fallback_url}")
        return fallback_url
        
    except Exception as e:
        logger.error(f"Error in search_related_url: {str(e)}")
        # Fallback: Create a path using the base knowledge URL
        slug = re.sub(r'[^\w\s-]', '', text.lower()).strip()
        slug = re.sub(r'[\s-]+', '-', slug)
        safe_slug = urllib.parse.quote(slug)
        return f"{BASE_KNOWLEDGE_URL}/{safe_slug}"

# Improved diagram tool function with working links and language support
def diagram_tool(input_text, include_colors=True, include_clicks=True, base_url=BASE_KNOWLEDGE_URL):
    try:
        # Detect language of the input text
        language = detect_language(input_text)
        logger.info(f"Diagram tool detected language: {language}")
        
        model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Generate a color palette
        color_palette = get_color_palette()
        
        # Create specific Mermaid diagram structure that works
        if language == 'arabic':
            styling_instructions = f"""
            يجب أن تستخدم هذا البناء الدقيق للمخطط:
             ```mermaid
            graph RL
            classDef feature fill:{color_palette['feature']},stroke:#333
            classDef benefit fill:{color_palette['benefit']},stroke:#333
            classDef technology fill:{color_palette['technology']},stroke:#333

            subgraph "العنوان الرئيسي"
            A["العنصر الأول"]:::feature
            
            subgraph "المجموعة الفرعية 1"
                B["العنصر الفرعي"]:::technology
            end
            subgraph "المجموعة الفرعية 2"
                D["العنصر الفرعي"]:::technology
            end
            A --> B
            A --> D
            D --> B
            D --> A
            end
            
            click A "https://ar.wikipedia.org/wiki/مثال" _blank
            click B "https://ar.wikipedia.org/wiki/مثال_آخر" _blank
            click D "https://ar.wikipedia.org/wiki/مثال_ثالث" _blank
            
            ✅ **ملاحظات هامة:**
           - يجب أن تستخدم جميع الروابط **عناوين URL حقيقية** وتنتهي بـ `_blank`.
           - تأكد من أن العقد والروابط في المخطط تعكس محتوى النص المعطى.
            """
        else:
            styling_instructions = f"""
            You must use exactly this diagram structure that works reliably:
            ```mermaid
            graph LR
            classDef feature fill:{color_palette['feature']},stroke:#69c,stroke-width:1px
            classDef benefit fill:{color_palette['benefit']},stroke:#6a6,stroke-width:1px
            classDef technology fill:{color_palette['technology']},stroke:#6c9,stroke-width:1px
            
            subgraph "Main Title"
            A["First Item"]:::feature
            
            subgraph "Subgroup 1"
                B["Subitem"]:::technology
            end
            subgraph "Subgroup 2"
                D["Subitem"]:::technology
            end
            A --> B
            A --> D
            D --> B
            D --> A
            end
            
            click A "https://en.wikipedia.org/wiki/Example" _blank
            click B "https://en.wikipedia.org/wiki/Another_example" _blank
            click D "https://en.wikipedia.org/wiki/Third_example" _blank
            
            ```
            
            ✅ **Important Notes:**
            - All links should use **real, content-relevant URLs** and end with `_blank`.
            - Make sure the nodes and connections in the diagram reflect the given text content.
            """

        # Generate instructions based on language
        if language == 'arabic':
            prompt = f"""
            أنشئ مخططًا دقيقًا لـ Mermaid استنادًا إلى وصف النص التالي:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **ملاحظات:** 
            - تأكد من أن المخطط يتبع **بالضبط** البنية الموضحة في التعليمات.
            - استخرج العناصر الرئيسية والعلاقات من النص المعطى.
            - **لا تضف أي تفسيرات، تعليقات، أو تعديلات إضافية** - فقط **كود Mermaid النقي**.
            """
        else:
            prompt = f"""
            Create a precise Mermaid diagram based on the following text description:
            
            {input_text}
            
            {styling_instructions}
            
            🔹 **Notes:** 
            - Make sure the diagram follows **exactly** the structure shown in the instructions.
            - Extract key entities and relationships from the given text.
            - **Do not include any prefixes, suffixes, or explanations** - just **pure Mermaid code**.
            """

        # Set generation configuration based on language
        generation_config = {
            "temperature": 0.1,  # Lower temperature for more deterministic output
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048  # Ensure we get complete output
        }
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        # Log the raw response for debugging
        logger.info(f"Raw Gemini response: {response.text}")
        
        # Process the response and clean up
        diagram_code = response.text.strip()
        
        # Remove markdown code blocks if present
        diagram_code = re.sub(r'```mermaid|```', '', diagram_code).strip()
        
        # Ensure diagram begins with 'graph' if missing
        if not any(diagram_code.startswith(prefix) for prefix in ['graph ', 'flowchart ']):
            diagram_code = "graph LR\n" + diagram_code
        
        # Ensure the diagram has styling if requested and not already present
        if include_colors and not any(["classDef" in diagram_code, "style" in diagram_code]):
            diagram_code = f"classDef feature fill:{color_palette['feature']},stroke:#69c,stroke-width:1px\n" + \
                           f"classDef benefit fill:{color_palette['benefit']},stroke:#6a6,stroke-width:1px\n" + \
                           f"classDef technology fill:{color_palette['technology']},stroke:#6c9,stroke-width:1px\n" + \
                           diagram_code
        
        # Add or fix click functionality if requested
        if include_clicks:
            # Extract all node IDs from the diagram
            nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)([^\]}\)]+)(?:\]|\)|\})', diagram_code)
            
            # Remove any existing click lines to replace them with correct ones
            diagram_code = re.sub(r'click\s+[A-Za-z0-9_]+\s+"[^"]+"\s+_blank', '', diagram_code)
            
            # Add click lines for all nodes
            click_lines = []
            for node_id, node_text in nodes:
                # Clean text for search
                clean_text = re.sub(r'["<>]', '', node_text).strip()
                
                # Find a related URL for this content
                url = search_related_url(clean_text, language)
                
                # Add click line with appropriate URL
                click_lines.append(f'click {node_id} "{url}" _blank')
            
            # Add the new click lines
            if click_lines:
                diagram_code += "\n\n" + "\n".join(click_lines)
        
        # Add RTL direction for Arabic if needed
        if language == 'arabic' and not any(["direction: RTL" in diagram_code, "direction:RTL" in diagram_code]):
            if any([diagram_code.startswith("graph "), diagram_code.startswith("flowchart ")]):
                first_line_end = diagram_code.find("\n")
                if first_line_end != -1:
                    diagram_code = diagram_code[:first_line_end] + " direction:RTL" + diagram_code[first_line_end:]
                else:
                    diagram_code += " direction:RTL"
        
        return diagram_code
    except Exception as e:
        logger.error(f"Error in diagram tool: {str(e)}")
        return f"Error generating diagram: {str(e)}"

# Tool for generating diagrams using LangChain
diagram_tool_obj = Tool(
    name="Mermaid Diagram Generator",
    func=diagram_tool,
    description="Generates Mermaid diagrams from text descriptions using Gemini in the appropriate language (Arabic or English)."
)

# Initialize LangChain Agent
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.2)

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

diagram_agent = initialize_agent(
    tools=[diagram_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory
)

# Extract function with fixes for links and language support
def extract_diagram_from_output(output_text):
    logger.info(f"Agent output to extract from: {output_text}")
    
    # Detect language from the output
    language = detect_language(output_text)
    
    # Find diagram in output
    observation_match = re.search(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
    
    if observation_match:
        diagram_code = observation_match.group(1).strip()
        diagram_code = re.sub(r'```mermaid|```', '', diagram_code).strip()
        
        # Ensure diagram begins with 'graph' if missing
        if not any(diagram_code.startswith(prefix) for prefix in ['graph ', 'flowchart ']):
            diagram_code = "graph LR\n" + diagram_code
        
        # Ensure class definitions are at the top
        class_defs = re.findall(r'(classDef [^\n]+)', diagram_code)
        if class_defs:
            for class_def in class_defs:
                diagram_code = diagram_code.replace(class_def, '')
            diagram_code = '\n'.join(class_defs) + '\n' + diagram_code.strip()
        
        # Remove any existing click lines
        click_lines = re.findall(r'(click [^\n]+)', diagram_code)
        for line in click_lines:
            diagram_code = diagram_code.replace(line, '')
        
        # Add proper click lines at the end with content-related URLs
        node_lines = []
        nodes = re.findall(r'([A-Za-z0-9_]+)(?:\[|\(|\{)([^\]}\)]+)(?:\]|\)|\})', diagram_code)
        for node_id, node_text in nodes:
            # Clean text and search for related URL
            clean_text = re.sub(r'["<>]', '', node_text).strip()
            url = search_related_url(clean_text, language)
            node_lines.append(f'click {node_id} "{url}" _blank')
        
        if node_lines:
            diagram_code += '\n\n' + '\n'.join(node_lines)
        
        return diagram_code
    
    # Fallback patterns
    mermaid_patterns = [
        r'(graph [TBLR][DRLUD][\s\S]*?)(?=\n\n|$)',
        r'(sequenceDiagram[\s\S]*?)(?=\n\n|$)',
        r'(classDiagram[\s\S]*?)(?=\n\n|$)',
        r'(stateDiagram(?:-v2)?[\s\S]*?)(?=\n\n|$)',
        r'(gantt[\s\S]*?)(?=\n\n|$)',
        r'(pie[\s\S]*?)(?=\n\n|$)',
        r'(erDiagram[\s\S]*?)(?=\n\n|$)'
    ]
    
    for pattern in mermaid_patterns:
        match = re.search(pattern, output_text)
        if match:
            return match.group(1).strip()
    
    # Last resort
    code_blocks = re.findall(r'```(?:mermaid)?\s*([\s\S]*?)```', output_text)
    if code_blocks:
        return code_blocks[0].strip()
    
    logger.error("Failed to extract any diagram code")
    return None
