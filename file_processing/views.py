import os
import re
import uuid
import base64
import logging
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from langchain.document_loaders import PyPDFLoader
from langchain_unstructured import UnstructuredLoader
from langchain_community.document_loaders import UnstructuredPowerPointLoader, UnstructuredWordDocumentLoader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter
from supabase import create_client, Client
import tempfile
import mimetypes
import pytesseract
from PIL import Image
import dotenv
import requests
import subprocess

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dotenv.load_dotenv()
# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY") 
supabase_bucket = os.getenv("SUPABASE_BUCKET", "files")
OCR_SPACE_API_KEY = os.getenv("OCR_SPACE_API_KEY", "helloworld")

# Verify environment variables are set
if not supabase_url or not supabase_key:
    logger.error("Supabase credentials not found in environment variables")
    raise ValueError("Supabase credentials not found in environment variables")

logger.info(f"Initializing Supabase client with URL: {supabase_url[:10]}... and bucket: {supabase_bucket}")
supabase: Client = create_client(supabase_url, supabase_key)

def txt_to_text(txt_path):
    """
    Read text from a plain text file.
    
    Args:
        txt_path (str): Path to the text file
        
    Returns:
        str: Content of the text file
    """
    try:
        logger.info(f"Reading text file: {txt_path}")
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        # Try different encodings if UTF-8 fails
        logger.warning(f"UTF-8 decoding failed for {txt_path}, trying latin-1")
        try:
            with open(txt_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            logger.error(f"Failed to read text file with latin-1 encoding: {str(e)}")
            raise Exception(f"Failed to read text file: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to read text file: {str(e)}")
        raise Exception(f"Failed to read text file: {str(e)}")

# Function to extract text from images using OCR
def image_to_text(image_path):
    """
    Extract text from an image using OCR.Space API.
    Args:
        image_path (str): Path to the image file
    Returns:
        str: Extracted text from the image
    """
    try:
        logger.info(f"Processing image with OCR: {image_path}")
        # First try with pytesseract locally
        try:
            image = Image.open(image_path)
            local_text = pytesseract.image_to_string(image)
            if local_text.strip():
                logger.info("Successfully extracted text with pytesseract")
                return local_text
        except Exception as e:
            logger.warning(f"Local OCR failed, falling back to OCR.Space API: {str(e)}")
        
        # Fall back to OCR.Space API
        with open(image_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'filename': f},
                data={
                    'apikey': OCR_SPACE_API_KEY,
                    'language': 'eng',  # or 'ara' for Arabic
                    'isOverlayRequired': False
                },
            )
        result = response.json()
        
        if result.get("IsErroredOnProcessing"):
            raise Exception(result.get("ErrorMessage", "Unknown OCR error"))
        
        parsed_results = result.get("ParsedResults")
        if parsed_results and len(parsed_results) > 0:
            return parsed_results[0].get("ParsedText", "")
        else:
            return ""
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise Exception(f"OCR processing failed: {str(e)}")

def pptx_to_text(pptx_path):
    """
    Extract text from PowerPoint files with fallback methods.
    """
    logger.info(f"Processing PPTX file: {pptx_path}")
    try:
        # Try the primary method
        loader = UnstructuredPowerPointLoader(pptx_path)
        documents = loader.load()
        text = "\n\n".join([doc.page_content for doc in documents])
        logger.info("Successfully extracted text from PPTX using UnstructuredPowerPointLoader")
        return text
    except Exception as e:
        logger.error(f"PPTX primary processing error: {str(e)}")
        # Try alternative method if first method fails
        try:
            logger.info("Attempting PPTX fallback method using LibreOffice")
            # Use LibreOffice to convert PPTX to TXT
            output_dir = os.path.dirname(pptx_path)
            base_name = os.path.basename(pptx_path)
            output_base = os.path.splitext(base_name)[0]
            
            # Run LibreOffice to convert the file
            cmd = ['soffice', '--headless', '--convert-to', 'txt', pptx_path, '--outdir', output_dir]
            logger.info(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            
            # Read the converted text file
            output_path = os.path.join(output_dir, f"{output_base}.txt")
            logger.info(f"Reading converted file: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Clean up the temporary file
            os.unlink(output_path)
            logger.info("Successfully extracted text using LibreOffice fallback")
            return text
        except Exception as fallback_e:
            logger.error(f"PPTX fallback processing error: {str(fallback_e)}")
            raise Exception(f"PPTX processing failed with both methods: {str(e)} | Fallback error: {str(fallback_e)}")

def docx_to_text(docx_path):
    """
    Extract text from Word files with fallback methods.
    """
    logger.info(f"Processing DOCX file: {docx_path}")
    try:
        # Try the primary method
        loader = UnstructuredWordDocumentLoader(docx_path)
        documents = loader.load()
        text = "\n\n".join([doc.page_content for doc in documents])
        logger.info("Successfully extracted text from DOCX using UnstructuredWordDocumentLoader")
        return text
    except Exception as e:
        logger.error(f"DOCX primary processing error: {str(e)}")
        # Try alternative method if first method fails
        try:
            logger.info("Attempting DOCX fallback method using LibreOffice")
            # Use LibreOffice to convert DOCX to TXT
            output_dir = os.path.dirname(docx_path)
            base_name = os.path.basename(docx_path)
            output_base = os.path.splitext(base_name)[0]
            
            # Run LibreOffice to convert the file
            cmd = ['soffice', '--headless', '--convert-to', 'txt', docx_path, '--outdir', output_dir]
            logger.info(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            
            # Read the converted text file
            output_path = os.path.join(output_dir, f"{output_base}.txt")
            logger.info(f"Reading converted file: {output_path}")
            with open(output_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            # Clean up the temporary file
            os.unlink(output_path)
            logger.info("Successfully extracted text using LibreOffice fallback")
            return text
        except Exception as fallback_e:
            logger.error(f"DOCX fallback processing error: {str(fallback_e)}")
            raise Exception(f"DOCX processing failed with both methods: {str(e)} | Fallback error: {str(fallback_e)}")

def sanitize_filename(filename):
    """
    Sanitize filename to be compatible with Supabase storage.
    Removes spaces, brackets, and other special characters.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Replace spaces and brackets with underscores
    sanitized = re.sub(r'[\s\[\]\(\)\{\}]', '_', filename)
    # Remove other special characters
    sanitized = re.sub(r'[^\w\-\.]', '', sanitized)
    return sanitized

@api_view(["POST"])
def upload_and_extract(request):
    """
    Handles either YouTube transcript extraction OR file uploads, not both.
    Returns extracted text based on the input (file or YouTube URL).
    """
    logger.info("Received request for text extraction")
    
    # Get YouTube URL or file from the request
    url = request.data.get("youtube_url", request.data.get("url", "")).strip()
    file = request.FILES.get("file", None)
    
    # Ensure only one input is provided (either file or YouTube URL)
    if url and file:
        logger.warning("Both URL and file provided in request")
        return Response(
            {"error": "Please provide either a YouTube URL or a file, not both."},
            status=400,
        )
    
    # 🎬 Process YouTube URL if provided
    if url:
        logger.info(f"Processing YouTube URL: {url}")
        # Improved regex to extract YouTube video ID from various URL formats
        regex = r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\/|$)"
        video_id_match = re.search(regex, url)
        
        if not video_id_match:
            logger.warning(f"Invalid YouTube URL: {url}")
            return Response({"error": "Invalid YouTube URL"}, status=400)
        
        video_id = video_id_match.group(1)
        logger.info(f"Extracted YouTube video ID: {video_id}")
        
        try:
            # Try multiple language options - including Arabic
            languages_to_try = ['en', 'ar', 'es', 'fr', 'de']
            transcript = None
            
            # First try specific languages
            for lang in languages_to_try:
                try:
                    logger.info(f"Trying to get transcript in language: {lang}")
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                    logger.info(f"Found transcript in language: {lang}")
                    break
                except NoTranscriptFound:
                    logger.info(f"No transcript found in language: {lang}")
                    continue
                except Exception as lang_e:
                    logger.warning(f"Error getting transcript in {lang}: {str(lang_e)}")
                    continue
            
            # If specific languages failed, try to get any available transcript
            if not transcript:
                logger.info("Trying to get list of available transcripts")
                try:
                    # Get list of available transcripts
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    
                    # First try to find an auto-generated transcript
                    for t in transcript_list:
                        if t.is_generated:
                            logger.info(f"Found auto-generated transcript in {t.language_code}")
                            transcript = t.fetch()
                            break
                    
                    # If no auto-generated transcript found, get the first available one
                    if not transcript and len(list(transcript_list)) > 0:
                        first_transcript = list(transcript_list)[0]
                        logger.info(f"Using first available transcript in {first_transcript.language_code}")
                        transcript = first_transcript.fetch()
                except Exception as list_e:
                    logger.error(f"Error getting transcript list: {str(list_e)}")
            
            # If we still don't have a transcript, raise an error
            if not transcript:
                logger.error(f"No transcript found for video ID: {video_id}")
                raise NoTranscriptFound(video_id, languages_to_try)
            
            # Extract the text from the transcript
            text = " ".join([item["text"] for item in transcript])
            logger.info(f"Successfully extracted transcript with {len(text)} characters")
            
            return Response({
                "extracted_text": text
            })
        except TranscriptsDisabled:
            logger.error(f"Transcripts are disabled for video ID: {video_id}")
            return Response({"error": "Transcripts are disabled for this YouTube video"}, status=400)
        except Exception as e:
            # Try to get available languages for better error message
            try:
                logger.info("Trying to get available language options for error message")
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                available_language_codes = []
                
                for t in transcript_list:
                    if t.is_generated:
                        available_language_codes.append(f"{t.language_code} (auto-generated)")
                    else:
                        available_language_codes.append(t.language_code)
                
                language_options = ", ".join(available_language_codes)
                logger.error(f"YouTube transcript extraction failed with available languages: {language_options}")
                return Response({
                    "error": f"YouTube transcript extraction failed. Available languages: {language_options}",
                    "suggestion": "You may need to specify one of these languages in your request."
                }, status=400)
            except Exception as list_e:
                logger.error(f"YouTube transcript extraction failed: {str(e)}, Error getting languages: {str(list_e)}")
                return Response({"error": f"YouTube transcript extraction failed: {str(e)}"}, status=500)
    
    # 📂 Process file if provided
    if file:
        logger.info(f"Processing file: {file.name}")
        try:
            # Get file extension
            file_ext = file.name.split(".")[-1].lower()
            logger.info(f"File extension: {file_ext}")
            
            # Sanitize original filename to be compatible with Supabase
            clean_original_name = sanitize_filename(file.name)
            
            # Generate a unique filename to avoid collisions
            unique_filename = f"{uuid.uuid4()}-{clean_original_name}"
            logger.info(f"Generated unique filename: {unique_filename}")
            
            # Create a temporary file to process locally
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_ext}") as temp_file:
                for chunk in file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            logger.info(f"Created temporary file: {temp_file_path}")
            
            # Get file mimetype
            mime_type, _ = mimetypes.guess_type(temp_file_path)
            logger.info(f"Detected MIME type: {mime_type}")
            
            # Upload file to Supabase
            with open(temp_file_path, 'rb') as f:
                file_content = f.read()
            
            # Simple test upload to debug Supabase connection
            try:
                # Upload to supabase storage
                logger.info(f"Uploading to Supabase storage bucket: {supabase_bucket}")
                supabase_response = supabase.storage.from_(supabase_bucket).upload(
                    unique_filename,
                    file_content,
                    {"content-type": mime_type}
                )
                
                # Get public URL (optional, depending on your bucket settings)
                file_url = supabase.storage.from_(supabase_bucket).get_public_url(unique_filename)
                logger.info(f"File uploaded successfully, URL: {file_url[:50]}...")
                
            except Exception as upload_error:
                # If upload fails, log the error but continue with text extraction
                logger.error(f"Supabase upload error: {str(upload_error)}")
                file_url = None
            
            extracted_text = ""
            
            # Process the file based on its extension
            if file_ext == "pdf":
                logger.info("Processing PDF file")
                loader = PyPDFLoader(temp_file_path)
                docs = loader.load()
                extracted_text = "\n".join([doc.page_content for doc in docs])
            elif file_ext == "docx":
                logger.info("Processing DOCX file")
                extracted_text = docx_to_text(temp_file_path)
            elif file_ext == "pptx":
                logger.info("Processing PPTX file")
                extracted_text = pptx_to_text(temp_file_path)
            elif file_ext in ["jpg", "jpeg", "png", "bmp", "tiff", "gif"]:
                logger.info("Processing image file")
                extracted_text = image_to_text(temp_file_path)
            elif file_ext == "txt":
                logger.info("Processing TXT file")
                extracted_text = txt_to_text(temp_file_path)
            else:
                # Clean up the temporary file
                logger.warning(f"Unsupported file format: .{file_ext}")
                os.unlink(temp_file_path)
                return Response(
                    {
                        "error": f"Unsupported file format: .{file_ext}",
                        "supported_formats": ["pdf", "docx", "pptx", "jpg", "jpeg", "png", "txt"],
                    },
                    status=400,
                )
            
            # Clean up the temporary file
            logger.info("Cleaning up temporary file")
            os.unlink(temp_file_path)
            
            # Check if text extraction was successful
            if not extracted_text.strip():
                logger.error("Text extraction failed. File might be empty or unreadable.")
                return Response(
                    {
                        "error": "Text extraction failed. File might be empty or unreadable."
                    },
                    status=500,
                )
            
            # Return the extracted text
            logger.info(f"Successfully extracted text with {len(extracted_text)} characters")
            return Response({
                "extracted_text": extracted_text,
                "file_url": file_url
            })
            
        except Exception as e:
            logger.error(f"File processing error: {str(e)}")
            return Response({"error": f"File processing error: {str(e)}"}, status=500)
    
    # If neither URL nor file provided
    logger.warning("No URL or file provided in request")
    return Response(
        {"error": "Please provide either a YouTube URL or a file to extract text from."},
        status=400,
    )

@api_view(["GET"])
def health_check(request):
    """
    Simple health check endpoint that returns 200 OK
    """
    return Response({"status": "ok"})
