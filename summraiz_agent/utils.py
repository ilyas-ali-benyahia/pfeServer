import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
import langdetect
import re

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def detect_language(text):
    """
    Enhanced language detection with better handling for mixed texts.
    Supports Arabic, English, and many other languages.
    """
    try:
        language = langdetect.detect(text)
        language_map = {
            'ar': 'arabic',
            'en': 'english',
            'fr': 'french',
            'es': 'spanish',
            'de': 'german',
            'zh': 'chinese',
            'ru': 'russian',
            'ja': 'japanese',
            'hi': 'hindi',
            'ur': 'urdu',
            'fa': 'farsi',
            'tr': 'turkish'
        }
        return language_map.get(language, 'english')
    except:
        return 'english'  # Default to English if detection fails

def summary_tool(input_text, detailed=True):
    """
    Enhanced summary tool that extracts more comprehensive information from texts.
    
    Args:
        input_text (str): The text to analyze
        detailed (bool): Whether to include additional analysis sections
    """
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Detect language
    language = detect_language(input_text)
    
    # Calculate appropriate number of key points based on text length
    min_points = 3
    max_points = 7
    if len(input_text) > 3000:
        max_points = 10
    elif len(input_text) < 500:
        max_points = 5
    
    if language == 'arabic':
        prompt = f"""
        استخرج تحليلاً شاملاً من النص التالي:
        
        {input_text}
        
        أعد النتائج بالتنسيق التالي بدقة:
        ملخص: [ملخص دقيق للنص بأكمله، فقرة واحدة مكثفة]
        
        نقطة رئيسية 1: [النقطة الأولى مع شرح موجز]
        نقطة رئيسية 2: [النقطة الثانية مع شرح موجز]
        نقطة رئيسية 3: [النقطة الثالثة مع شرح موجز]
        [وهكذا...]
        
        {"المواضيع الرئيسية: [حدد 3-5 مواضيع أو مجالات رئيسية يغطيها النص]" if detailed else ""}
        
        {"تحليل النبرة: [حدد نبرة النص (موضوعية، مقنعة، تعليمية، إلخ) وكيف يتم توصيلها]" if detailed else ""}
        
        {"تحليل المشاعر: [إيجابي، سلبي، محايد، أو مختلط، مع تفسير موجز]" if detailed else ""}
        
        {"اقتباسات مهمة: [3-5 اقتباسات أو جمل مهمة من النص الأصلي]" if detailed else ""}
        
        {"استنتاجات ورؤى: [استنتاجات مهمة أو رؤى يمكن استخلاصها من النص]" if detailed else ""}
        
        {"الجمهور المستهدف: [الجمهور المحتمل المستهدف لهذا النص]" if detailed else ""}
        
        {"مصطلحات رئيسية: [قائمة بالمصطلحات أو المفاهيم التقنية الرئيسية الموجودة في النص مع تعريفات موجزة]" if detailed else ""}
        
        التزم بهذا التنسيق بالضبط. قم بتضمين {min_points}-{max_points} نقاط رئيسية حسب طول النص.
        """
    else:  # Default to English
        prompt = f"""
        Extract a comprehensive analysis from the following text:
        
        {input_text}
        
        Return the analysis in this precise format:
        Summary: [accurate summary of the entire text in one concise paragraph]
        
        Key Point 1: [first key point with brief explanation]
        Key Point 2: [second key point with brief explanation]
        Key Point 3: [third key point with brief explanation]
        [and so on...]
        
        {"Main Topics: [identify 3-5 main topics or areas covered in the text]" if detailed else ""}
        
        {"Tone Analysis: [identify the tone of the text (objective, persuasive, educational, etc.) and how it's conveyed]" if detailed else ""}
        
        {"Sentiment Analysis: [positive, negative, neutral, or mixed, with brief explanation]" if detailed else ""}
        
        {"Important Quotes: [3-5 important quotes or sentences from the original text]" if detailed else ""}
        
        {"Conclusions & Insights: [important conclusions or insights that can be drawn from the text]" if detailed else ""}
        
        {"Target Audience: [likely intended audience for this text]" if detailed else ""}
        
        {"Key Terms: [list of key technical terms or concepts in the text with brief definitions]" if detailed else ""}
        
        Strictly follow this format. Include {min_points}-{max_points} key points depending on the length of the text.
        """
    
    response = model.generate_content(prompt)
    return response.text

# Define tool for LangChain agent
summary_tool_obj = Tool(
    name="Enhanced Text Analyzer",
    func=summary_tool,
    description="""
    Generates a comprehensive analysis from input text in the appropriate language.
    Extracts summary, key points, topics, tone, sentiment, important quotes, insights, target audience, and key terms.
    Automatically detects language (Arabic, English, French, Spanish, and others).
    """
)

# Initialize LangChain agent with Gemini
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(
    tools=[summary_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    memory=memory
)

# Enhanced function to extract structured information from agent output
def extract_summary_from_output(output_text):
    """
    Extract structured analysis information from the agent's output text.
    Handles both Arabic and English formats with improved pattern matching.
    """
    # Initialize result dictionary with all possible fields
    result = {
        "summary": "",
        "key_points": [],
        "main_topics": [],
        "tone_analysis": "",
        "sentiment_analysis": "",
        "important_quotes": [],
        "conclusions": "",
        "target_audience": "",
        "key_terms": {}
    }
    
    # Check if output contains Arabic format
    is_arabic = 'ملخص:' in output_text or 'ملخص :' in output_text
    
    if is_arabic:
        # Arabic extraction patterns
        patterns = {
            "summary": [r'ملخص: (.*?)(?=نقطة رئيسية|\n\n|$)', r'ملخص : (.*?)(?=نقطة رئيسية|\n\n|$)'],
            "key_points": [r'نقطة رئيسية (\d+): (.*?)(?=نقطة رئيسية|\n\n|$)', r'نقطة رئيسية (\d+) : (.*?)(?=نقطة رئيسية|\n\n|$)'],
            "main_topics": [r'المواضيع الرئيسية: (.*?)(?=تحليل النبرة|\n\n|$)', r'المواضيع الرئيسية : (.*?)(?=تحليل النبرة|\n\n|$)'],
            "tone_analysis": [r'تحليل النبرة: (.*?)(?=تحليل المشاعر|\n\n|$)', r'تحليل النبرة : (.*?)(?=تحليل المشاعر|\n\n|$)'],
            "sentiment_analysis": [r'تحليل المشاعر: (.*?)(?=اقتباسات مهمة|\n\n|$)', r'تحليل المشاعر : (.*?)(?=اقتباسات مهمة|\n\n|$)'],
            "important_quotes": [r'اقتباسات مهمة: (.*?)(?=استنتاجات ورؤى|\n\n|$)', r'اقتباسات مهمة : (.*?)(?=استنتاجات ورؤى|\n\n|$)'],
            "conclusions": [r'استنتاجات ورؤى: (.*?)(?=الجمهور المستهدف|\n\n|$)', r'استنتاجات ورؤى : (.*?)(?=الجمهور المستهدف|\n\n|$)'],
            "target_audience": [r'الجمهور المستهدف: (.*?)(?=مصطلحات رئيسية|\n\n|$)', r'الجمهور المستهدف : (.*?)(?=مصطلحات رئيسية|\n\n|$)'],
            "key_terms": [r'مصطلحات رئيسية: (.*?)(?=\n\n|$)', r'مصطلحات رئيسية : (.*?)(?=\n\n|$)']
        }
    else:
        # English extraction patterns
        patterns = {
            "summary": [r'Summary: (.*?)(?=Key Point|\n\n|$)'],
            "key_points": [r'Key Point (\d+): (.*?)(?=Key Point|\n\n|Main Topics:|$)'],
            "main_topics": [r'Main Topics: (.*?)(?=Tone Analysis|\n\n|$)'],
            "tone_analysis": [r'Tone Analysis: (.*?)(?=Sentiment Analysis|\n\n|$)'],
            "sentiment_analysis": [r'Sentiment Analysis: (.*?)(?=Important Quotes|\n\n|$)'],
            "important_quotes": [r'Important Quotes: (.*?)(?=Conclusions & Insights|\n\n|$)'],
            "conclusions": [r'Conclusions & Insights: (.*?)(?=Target Audience|\n\n|$)'],
            "target_audience": [r'Target Audience: (.*?)(?=Key Terms|\n\n|$)'],
            "key_terms": [r'Key Terms: (.*?)(?=\n\n|$)']
        }
    
    # Extract data using patterns
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            if field == "key_points":
                matches = re.findall(pattern, output_text, re.DOTALL)
                if matches:
                    for idx, point in matches:
                        result["key_points"].append(point.strip())
                    break
            else:
                match = re.search(pattern, output_text, re.DOTALL)
                if match:
                    if field in ["main_topics", "important_quotes"]:
                        # Split list items
                        items = re.split(r'\d+\.\s*|\-\s*|\•\s*', match.group(1).strip())
                        result[field] = [item.strip() for item in items if item.strip()]
                    elif field == "key_terms":
                        # Process key terms to create a dictionary
                        terms_text = match.group(1).strip()
                        term_matches = re.findall(r'([^:]+):\s*([^•]+)(?=\n|$)', terms_text)
                        result[field] = {term.strip(): desc.strip() for term, desc in term_matches}
                    else:
                        result[field] = match.group(1).strip()
                    break
    
    return result