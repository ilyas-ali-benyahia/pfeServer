import os
import cohere
from dotenv import load_dotenv
from typing import List, Optional
from langchain.text_splitter import CharacterTextSplitter
from langchain.docstore.document import Document
from supabase import create_client, Client
import google.generativeai as genai

load_dotenv()

class GymChatbot:
    def __init__(self):
        """
        Initialize the chatbot without immediately processing content.
        """
        self.setup_gemini_api()
        self.supabase = self.initialize_supabase()
        self.setup_cohere_api()
        self.is_initialized = False
        self.chunk_size = 1200
        self.chunk_overlap = 100

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

    def initialize_supabase(self) -> Client:
        """
        Initialize the Supabase client.
        """
        try:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_KEY")
            if not supabase_url or not supabase_key:
                raise ValueError("Missing Supabase credentials")
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"Error initializing Supabase: {e}")
            raise

    def setup_cohere_api(self):
        """
        Set up Cohere API for embeddings.
        """
        try:
            self.cohere_api_key = os.getenv("COHERE_API_KEY")
            if not self.cohere_api_key:
                raise ValueError("Missing Cohere API key")
            self.client = cohere.Client(self.cohere_api_key)
        except Exception as e:
            print(f"Error setting up Cohere API: {e}")
            raise

    def embed_text(self, text: str, input_type: str = "search_query") -> Optional[List[float]]:
        """
        Generate embeddings using Cohere's multilingual model.
        The embed-multilingual-light-v3.0 model supports 100+ languages including Arabic.
        """
        try:
            response = self.client.embed(
                texts=[text], 
                model="embed-multilingual-light-v3.0",  # This model supports Arabic
                input_type=input_type
            )
            return response.embeddings[0]
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            return None

    def delete_all_data(self):
        """
        Delete all records from Supabase.
        """
        try:
            self.supabase.table("chatbotcontent").delete().neq("id", 0).execute()
            self.is_initialized = False
        except Exception as e:
            print(f"Error deleting data: {e}")

    def process_text(self, text: str) -> bool:
        """
        Process text and create a vector store in Supabase.
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
            
            # Process each chunk
            for chunk in split_texts:
                # Ensure the text is properly encoded
                embedding = self.embed_text(chunk, input_type="search_document")
                if embedding:
                    self.supabase.table("chatbotcontent").insert({
                        "content": chunk,
                        "embedding": embedding
                    }).execute()
                    
            self.is_initialized = True
            return True
        except Exception as e:
            print(f"Error processing text: {e}")
            return False

    def process_file(self, file_path: str) -> bool:
        """
        Process a file and create a vector store in Supabase.
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

    def retrieve_relevant_context(self, query: str, top_k: int = 6) -> List[str]:
        """
        Retrieve relevant context from Supabase.
        Works with Arabic queries.
        """
        try:
            if not self.is_initialized:
                return []
                
            query_embedding = self.embed_text(query)
            if not query_embedding:
                return []

            response = self.supabase.rpc(
                'match_documents', 
                {'query_embedding': query_embedding, 'match_threshold': 0.1, 'match_count': top_k}
            ).execute()

            return [row["content"] for row in response.data]
        except Exception as e:
            print(f"Error retrieving context: {e}")
            return []

    def generate_response(self, query: str) -> str:
        """
        Generate a response using Gemini.
        Supports Arabic queries and responses.
        """
        try:
            if not self.is_initialized:
                return "لم يتم تهيئة الروبوت المحادث بقاعدة معرفية بعد. يرجى تحميل النص أولاً."
                
            context = self.retrieve_relevant_context(query)
            if not context:
                return "لم أتمكن من العثور على معلومات محددة. هل يمكنك إعادة صياغة سؤالك؟"
            
            # Detect if the query is in Arabic to respond in the same language
            is_arabic = any('\u0600' <= c <= '\u06FF' for c in query)
            
            if is_arabic:
                prompt = f"""
                أنت مساعد خبير في صالة الألعاب الرياضية. استخدم السياق التالي للإجابة على الاستفسار:

                السياق:
                {chr(10).join([f"- {chunk}" for chunk in context])}

                استفسار المستخدم: {query}
                
                أجب فقط بناءً على السياق المقدم. إذا لم يكن لديك معلومات كافية، فأخبر بذلك.
                """
            else:
                prompt = f"""
                You are an expert gym assistant. Use the following context to answer the query:

                Context:
                {chr(10).join([f"- {chunk}" for chunk in context])}

                User Query: {query}
                
                Answer based only on the provided context. If you don't have enough information, say so.
                """
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
        
        except Exception as e:
            print(f"Error generating response: {e}")
            if any('\u0600' <= c <= '\u06FF' for c in query):  # Check if query is in Arabic
                return "حدث خطأ أثناء معالجة استفسارك."
            else:
                return "An error occurred while processing your query."