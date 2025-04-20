import os
import re
from typing import List, Optional
from langchain.text_splitter import CharacterTextSplitter
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class GymChatbot:
    def __init__(self):
        """
        Initialize the chatbot without database or embeddings.
        """
        self.setup_gemini_api()
        self.is_initialized = False
        self.chunk_size = 1200
        self.chunk_overlap = 100
        self.knowledge_base = []  # Store text chunks in memory
        self.chat_history = []  # Store recent conversation history

    def setup_gemini_api(self):
        """
        Set up Google Gemini API configuration.
        """
        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = genai.GenerativeModel(model_name="gemini-1.5-pro")
        except Exception as e:
            print(f"Error setting up Gemini API: {e}")
            raise

    def delete_all_data(self):
        """
        Clear all stored knowledge and chat history.
        """
        self.knowledge_base = []
        self.chat_history = []
        self.is_initialized = False

    def process_text(self, text: str) -> bool:
        """
        Process text and store in memory instead of Supabase.
        Works with multilingual text including Arabic.
        """
        try:
            # Start fresh
            self.delete_all_data()
            
            # Use langchain's CharacterTextSplitter which handles Unicode properly
            text_splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size, 
                chunk_overlap=self.chunk_overlap,
                separator="\n"  # Use newlines as separators to respect Arabic text structure
            )
            split_texts = text_splitter.split_text(text)
            
            # Store chunks directly in memory
            self.knowledge_base = split_texts
                    
            self.is_initialized = True
            return True
        except Exception as e:
            print(f"Error processing text: {e}")
            return False

    def process_file(self, file_path: str) -> bool:
        """
        Process a file and store in memory.
        Supports files with Arabic text.
        """
        try:
            # Use utf-8 encoding to properly handle Arabic characters
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()
            return self.process_text(text)
        except UnicodeDecodeError:
            # If utf-8 fails, try with another encoding common for Arabic
            try:
                with open(file_path, "r", encoding="cp1256") as file:  # Windows Arabic encoding
                    text = file.read()
                return self.process_text(text)
            except Exception as e:
                print(f"Error reading file with alternative encoding: {e}")
                return False
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

    def generate_response(self, query: str) -> str:
        """
        Generate a response using Gemini.
        Focuses on uploaded content first, but can also answer general questions.
        Maintains conversation history for context.
        Supports Arabic queries and responses.
        """
        try:
            # Detect if the query is in Arabic to respond in the same language
            is_arabic = any('\u0600' <= c <= '\u06FF' for c in query)
            
            # Keep chat history limited to last 5 exchanges
            if len(self.chat_history) > 10:
                self.chat_history = self.chat_history[-10:]
            
            # Add current query to history
            self.chat_history.append({"role": "user", "content": query})
            
            # Format chat history for context
            history_context = "\n".join(
                [f"{'User' if item['role'] == 'user' else 'Assistant'}: {item['content']}" 
                 for item in self.chat_history[-6:-1]]
            ) if len(self.chat_history) > 1 else ""
            
            if not self.is_initialized or not self.knowledge_base:
                # General knowledge mode (no user-uploaded content)
                if is_arabic:
                    prompt = f"""
                    أنت مساعد ذكي متعدد الاستخدامات قادر على الإجابة على أي سؤال بدقة ووضوح. لديك معرفة شاملة في جميع المجالات بما في ذلك:
                    - العلوم والتكنولوجيا
                    - الصحة واللياقة البدنية
                    - الأدب والفنون
                    - التاريخ والجغرافيا
                    - البرمجة والذكاء الاصطناعي
                    
                    سجل المحادثة السابق:
                    {history_context}
                    
                    استفسار المستخدم: {query}
                    
                    تعليمات الإجابة:
                    1. قدم إجابات شاملة ومفصلة مع أمثلة عملية عند الإمكان.
                    2. رتب المعلومات بطريقة منطقية (النقاط الرئيسية أولاً، ثم التفاصيل).
                    3. إذا كان السؤال يتطلب رأيًا شخصيًا، صرّح بذلك بوضوح.
                    4. استخدم لغة واضحة وسلسة تناسب جميع المستويات.
                    5. عند الاقتضاء، قدم نصائح أو تحذيرات إضافية ذات صلة.
                    """
                else:
                    prompt = f"""
                    You are a versatile AI assistant capable of answering any question accurately and clearly. Your expertise spans all domains including:
                    - Science & Technology  
                    - Health & Fitness  
                    - Literature & Arts  
                    - History & Geography  
                    - Programming & AI  
                    
                    Previous conversation:  
                    {history_context}  
                    
                    User Query: {query}  
                    
                    Answering Guidelines:  
                    1. Provide comprehensive, detailed answers with practical examples where possible.  
                    2. Structure information logically (key points first, then details).  
                    3. For opinion-based questions, explicitly state it's your perspective.  
                    4. Use clear, accessible language for all knowledge levels.  
                    5. When relevant, include additional tips or caveats.  
                    """
            else:
                # User-uploaded content mode
                context = "\n\n".join(self.knowledge_base)
                
                if is_arabic:
                    prompt = f"""
                    أنت مساعد ذكي يركز على الإجابة بناءً على المحتوى المقدم من المستخدم أولاً، مع الاحتفاظ بقدرتك على الإجابة على الأسئلة العامة.
                    
                    المحتوى المقدم من المستخدم (السياق الأساسي للإجابة):
                    {context}
                    
                    سجل المحادثة السابق:
                    {history_context}
                    
                    استفسار المستخدم: {query}
                    
                    تعليمات صارمة:
                    1. الأولوية للمحتوى المقدم: إذا كان السؤال متعلقًا به، أجب مباشرة مع الاستشهاد بأجزاء محددة منه.
                    2. الإجابة العامة: إذا كان السؤال خارج نطاق المحتوى، أجب بناءً على معرفتك العامة مع ذكر ذلك صراحة.
                    3. الربط بين المصادر: عند الاقتضاء، اربط بين معلومات المحتوى المقدم ومعرفتك العامة.
                    4. الشفافية: إذا لم يكن السؤال واضحًا، اطلب توضيحًا بدلاً من تقديم إجابة قد تكون غير دقيقة.
                    5. التنظيم: رتب الإجابات بطريقة سهلة المتابعة (عناوين فرعية، نقاط رئيسية، إلخ).
                    """
                else:
                    prompt = f"""
                    You are an AI assistant that prioritizes answers based on user-uploaded content while retaining general knowledge capabilities.
                    
                    User-Uploaded Content (Primary Context):
                    {context}
                    
                    Previous Conversation:
                    {history_context}
                    
                    User Query: {query}
                    
                    Strict Guidelines:
                    1. Content-First: If the question relates to the uploaded content, answer directly citing specific portions.
                    2. General Knowledge: For unrelated questions, answer based on your general knowledge while stating this explicitly.
                    3. Source Bridging: Where relevant, connect insights from the uploaded content with your general knowledge.
                    4. Transparency: If a query is ambiguous, request clarification instead of guessing.
                    5. Organization: Structure answers for easy reading (subheadings, bullet points, etc.).
                    """
            
            response = self.model.generate_content(prompt)
            answer = response.text.strip()
            
            # Add response to history
            self.chat_history.append({"role": "assistant", "content": answer})
            
            return answer
        
        except Exception as e:
            print(f"Error generating response: {e}")
            if is_arabic:
                return "حدث خطأ أثناء معالجة استفسارك. يرجى المحاولة مرة أخرى."
            else:
                return "An error occurred while processing your query. Please try again."
