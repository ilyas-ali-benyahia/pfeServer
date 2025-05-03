import os
import re
from typing import List, Optional, Dict, Any
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
        self.max_history_entries = 10

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
            # Try multiple encodings to properly handle Arabic and other character sets
            encodings = ["utf-8", "cp1256", "utf-16", "iso-8859-6"]
            
            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as file:
                        text = file.read()
                    return self.process_text(text)
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, try binary mode and detect encoding
            with open(file_path, "rb") as file:
                raw_bytes = file.read()
                
            # Try to detect encoding from byte order mark
            if raw_bytes.startswith(b'\xef\xbb\xbf'):  # UTF-8 BOM
                text = raw_bytes[3:].decode('utf-8')
            elif raw_bytes.startswith(b'\xff\xfe'):  # UTF-16 LE BOM
                text = raw_bytes[2:].decode('utf-16-le')
            elif raw_bytes.startswith(b'\xfe\xff'):  # UTF-16 BE BOM
                text = raw_bytes[2:].decode('utf-16-be')
            else:
                # Last resort: try with errors='replace'
                text = raw_bytes.decode('utf-8', errors='replace')
                
            return self.process_text(text)
                
        except Exception as e:
            print(f"Error reading file: {e}")
            return False

    def preprocess_query(self, query: str) -> str:
        """
        Clean and improve the query before sending to Gemini.
        Corrects common spelling mistakes and improves query structure.
        """
        # Clean up extra whitespace
        query = re.sub(r'\s+', ' ', query).strip()
        
        # Common spelling corrections (can be expanded)
        spelling_corrections = {
            r'\bwirat\b': 'write',
            r'\bwrit\b': 'write',
            r'\bqition\b': 'question',
            r'\banser\b': 'answer',
            r'\benhansed\b': 'enhanced',
            r'\bbeater\b': 'better',
            r'\blake\b': 'like',
            r'\bwont\b': 'want',
            r'\bbecose\b': 'because',
            r'\bunderestendable\b': 'understandable',
        }
        
        for misspelling, correction in spelling_corrections.items():
            query = re.sub(misspelling, correction, query, flags=re.IGNORECASE)
        
        # Add question mark if query appears to be a question but lacks one
        question_words = ['what', 'how', 'why', 'when', 'where', 'who', 'which', 'can', 'could', 'would', 'should', 'is', 'are', 'do', 'does']
        if any(query.lower().startswith(word) for word in question_words) and not query.endswith('?'):
            query += '?'
            
        return query

    def detect_language(self, text: str) -> str:
        """
        Detect if text is primarily Arabic or English.
        Returns 'ar' for Arabic, 'en' for English or other languages.
        """
        # Count Arabic characters
        arabic_count = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        
        # Determine if text is primarily Arabic (at least 30% Arabic characters)
        return 'ar' if arabic_count > len(text) * 0.3 else 'en'

    def build_prompt(self, query: str, lang: str, history_context: str) -> str:
        """
        Build an optimized prompt based on language and available context.
        """
        if not self.is_initialized or not self.knowledge_base:
            # General knowledge mode (no user-uploaded content)
            if lang == 'ar':
                return f"""
                أنت مساعد ذكي متخصص ومدرب على تقديم إجابات دقيقة وواضحة ومفيدة. 

                سجل المحادثة السابق:
                {history_context}

                استفسار المستخدم: {query}

                تعليمات الإجابة:
                1. افهم جوهر السؤال حتى لو كانت الصياغة غير مثالية.
                2. قدم إجابات مباشرة ومنظمة بدون مقدمات طويلة.
                3. استخدم أمثلة عملية لتوضيح النقاط المعقدة.
                4. قسّم المعلومات إلى فقرات قصيرة وسهلة القراءة.
                5. تجنب المصطلحات المعقدة إلا عند الضرورة، وقم بشرحها عند استخدامها.
                6. اختتم بملخص سريع للنقاط الرئيسية إذا كانت الإجابة طويلة.
                """
            else:
                return f"""
                You are an intelligent assistant trained to provide accurate, clear, and helpful answers. You excel at understanding queries even when they have grammatical or spelling errors.

                Previous conversation:
                {history_context}

                User query: {query}

                Response guidelines:
                1. Understand the core of the question even if the phrasing is imperfect.
                2. Provide direct, structured answers without lengthy introductions.
                3. Use practical examples to illustrate complex points.
                4. Break information into short, readable paragraphs.
                5. Avoid complex terminology unless necessary, and explain it when used.
                6. End with a quick summary of key points if the answer is lengthy.
                """
        else:
            # User-uploaded content mode
            # Join the knowledge base chunks, but limit total context size
            max_context_length = 10000
            context = ""
            for chunk in self.knowledge_base:
                if len(context) + len(chunk) + 4 <= max_context_length:
                    context += chunk + "\n\n"
                else:
                    # Add final partial chunk if space allows
                    remaining_space = max_context_length - len(context)
                    if remaining_space > 100:  # Only add if significant space remains
                        context += chunk[:remaining_space-4] + " ..."
                    break
            
            if lang == 'ar':
                return f"""
                أنت مساعد خبير متخصص في تحليل وفهم المحتوى المقدم من المستخدم، وقادر على تقديم إجابات دقيقة حتى مع الأسئلة ذات الصياغة غير المثالية.

                المحتوى المقدم (المصدر الرئيسي للمعلومات):
                {context}

                سجل المحادثة السابق:
                {history_context}

                استفسار المستخدم: {query}

                إرشادات للإجابة:
                1. أولوية المحتوى: ركز على المعلومات الموجودة في المحتوى المقدم عند الإجابة.
                2. اقتبس أجزاء محددة: عند الإشارة إلى معلومات من المحتوى، حدد موقعها بدقة.
                3. افهم السؤال بعمق: حتى لو كان السؤال غير مصاغ بشكل مثالي، اسعَ لفهم المقصود.
                4. دمج المعرفة: إذا كان مناسبًا، اربط بين المحتوى المقدم ومعرفتك العامة لتقديم سياق أفضل.
                5. وضوح الإجابة: قدم إجابات منظمة ومباشرة، مع تقسيم المعلومات إلى نقاط أو فقرات قصيرة للقراءة السهلة.
                """
            else:
                return f"""
                You are an expert assistant specialized in analyzing and understanding user-provided content, capable of delivering precise answers even with imperfectly phrased questions.

                Provided content (primary information source):
                {context}

                Previous conversation:
                {history_context}

                User query: {query}

                Response guidelines:
                1. Content priority: Focus on information from the provided content when answering.
                2. Cite specific portions: When referencing information from the content, precisely identify its location.
                3. Deep question understanding: Even if the question is not perfectly phrased, seek to understand the intent.
                4. Knowledge integration: Where appropriate, connect the provided content with your general knowledge for better context.
                5. Answer clarity: Provide organized, direct answers, breaking information into bullet points or short paragraphs for easy reading.
                """

    def generate_response(self, query: str) -> str:
        """
        Generate a response using Gemini with enhanced query preprocessing
        and optimized prompts based on detected language.
        """
        try:
            # Preprocess the query to correct common errors and improve structure
            processed_query = self.preprocess_query(query)
            
            # Detect language to provide culturally appropriate responses
            lang = self.detect_language(query)
            
            # Add current query to history
            self.chat_history.append({"role": "user", "content": query})
            
            # Keep chat history limited
            if len(self.chat_history) > self.max_history_entries:
                self.chat_history = self.chat_history[-self.max_history_entries:]
            
            # Format chat history for context
            history_context = "\n".join(
                [f"{'User' if item['role'] == 'user' else 'Assistant'}: {item['content']}" 
                 for item in self.chat_history[-6:-1]]
            ) if len(self.chat_history) > 1 else ""
            
            # Build optimized prompt based on language and available context
            prompt = self.build_prompt(processed_query, lang, history_context)
            
            # Generate response with enhanced parameters
            generation_config = {
                "temperature": 0.2,  # Lower temperature for more focused answers
                "top_p": 0.95,       # Slightly narrowed sampling for more reliable outputs
                "top_k": 40,         # Moderate top_k for balance between creativity and precision
                "max_output_tokens": 1024,  # Ensure sufficient space for comprehensive answers
            }
            
            # Add safety settings to ensure appropriate responses
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                }
            ]
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            answer = response.text.strip()
            
            # Add response to history
            self.chat_history.append({"role": "assistant", "content": answer})
            
            return answer
        
        except Exception as e:
            print(f"Error generating response: {e}")
            if lang == 'ar':
                return "حدث خطأ أثناء معالجة استفسارك. يرجى المحاولة مرة أخرى."
            else:
                return "An error occurred while processing your query. Please try again."
