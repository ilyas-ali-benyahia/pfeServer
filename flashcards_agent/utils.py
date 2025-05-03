import os
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory
import langdetect

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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

def flashcard_tool(input_text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # Detect language
    language = detect_language(input_text)
    
    if language == 'arabic':
        prompt = """
        قم بإنشاء بطاقات تعليمية من النص التالي:
        
        {input_text}
        
        أعد فقط البطاقات التعليمية بهذا التنسيق:
        س: سؤال
        ج: جواب
        
        قم بإنشاء بطاقات تعليمية  . 
        لا تقم بتضمين أي نص أو أفكار أو شروحات إضافية.
        """
    else:  # Default to English
        prompt = """
        Generate flashcards from the following text:
        
        {input_text}
        
        Return ONLY the flashcards in this format:
        Q: question
        A: answer
        
        Generate  flashcards. Do not include any additional text
          thoughts, or explanations.
        """
    
    response = model.generate_content(prompt.format(input_text=input_text))
    return response.text

# Define tool for LangChain agent
flashcard_tool_obj = Tool(
    name="Flashcard Generator",
    func=flashcard_tool,
    description="Generates flashcards from input text using Gemini in the appropriate language (Arabic or English)."
)

# Initialize LangChain agent with Gemini
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(
    tools=[flashcard_tool_obj],
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,  # You can set this to False later
    memory=memory
)

# Create a function to extract flashcards from agent output
def extract_flashcards_from_output(output_text):
    """
    Extract flashcards from agent output with improved reliability.
    Works with both English and Arabic outputs.
    """
    import re
    
    all_flashcards = []
    
    # First try to extract from observation sections
    if 'Observation:' in output_text:
        observation_sections = re.findall(r'Observation: (.*?)(?=Thought:|$)', output_text, re.DOTALL)
        
        for section in observation_sections:
            # Try Arabic format
            ar_qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', section, re.DOTALL)
            for question, answer in ar_qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
            
            # Try English format
            en_qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', section, re.DOTALL)
            for question, answer in en_qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
    
    # If no flashcards found in observation sections, try the full text
    if not all_flashcards:
        # Try Arabic format
        ar_qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', output_text, re.DOTALL)
        for question, answer in ar_qa_pairs:
            all_flashcards.append({
                "question": question.strip(),
                "answer": answer.strip()
            })
        
        # Try English format
        en_qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', output_text, re.DOTALL)
        for question, answer in en_qa_pairs:
            all_flashcards.append({
                "question": question.strip(),
                "answer": answer.strip()
            })
    
    # Additional capture for output formats with indentation or different patterns
    if not all_flashcards:
        # Try capturing with potential spaces/indentation
        en_qa_pairs = re.findall(r'[Qq](?:uestion)?:?\s*(.*?)\s*\n[Aa](?:nswer)?:?\s*(.*?)(?=\s*\n\s*[Qq](?:uestion)?:?|\s*$)', 
                               output_text, re.DOTALL)
        for question, answer in en_qa_pairs:
            all_flashcards.append({
                "question": question.strip(),
                "answer": answer.strip()
            })
        
        # Try capturing with potential spaces/indentation for Arabic
        ar_qa_pairs = re.findall(r'[سؤال](?:ؤال)?:?\s*(.*?)\s*\n[جواب](?:واب)?:?\s*(.*?)(?=\s*\n\s*[سؤال](?:ؤال)?:?|\s*$)', 
                                output_text, re.DOTALL)
        for question, answer in ar_qa_pairs:
            all_flashcards.append({
                "question": question.strip(),
                "answer": answer.strip()
            })
    
    return all_flashcards


def create_direct_flashcards(text):
    """
    Function to directly create flashcards by calling the flashcard_tool
    without going through the agent. This provides a reliable fallback.
    """
    try:
        # Import needed at function level to avoid circular imports
        from .utils import flashcard_tool, detect_language
        
        # Get language
        language = detect_language(text)
        
        # Call the tool directly
        tool_output = flashcard_tool(text)
        
        # Extract flashcards
        all_flashcards = []
        import re
        
        if language == 'arabic':
            qa_pairs = re.findall(r'س: (.*?)\nج: (.*?)(?=\s*س:|$)', tool_output, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
        else:
            qa_pairs = re.findall(r'Q: (.*?)\nA: (.*?)(?=\s*Q:|$)', tool_output, re.DOTALL)
            for question, answer in qa_pairs:
                all_flashcards.append({
                    "question": question.strip(),
                    "answer": answer.strip()
                })
                
        return all_flashcards
    except Exception as e:
        print(f"Direct flashcard creation error: {str(e)}")
        return []
