import os
import re
import uuid
import logging
import tempfile
import mimetypes
import requests
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from langchain.document_loaders import PyPDFLoader
from langchain_unstructured import UnstructuredLoader
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.formatters import TextFormatter
from supabase import create_client, Client
import pytesseract
from PIL import Image
import dotenv
import json
import subprocess
from urllib.parse import urlparse, parse_qs

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

def extract_youtube_id(url):
    """
    Extract YouTube video ID from various URL formats.
    Much more comprehensive approach with multiple methods.
    
    Args:
        url (str): YouTube URL
        
    Returns:
        str: YouTube video ID or None if not found
    """
    # Try parsing URL with urlparse first (most reliable)
    parsed_url = urlparse(url)
    
    # Method 1: youtube.com/watch?v=VIDEO_ID format
    if 'youtube.com' in parsed_url.netloc and '/watch' in parsed_url.path:
        query_params = parse_qs(parsed_url.query)
        if 'v' in query_params:
            return query_params['v'][0]
    
    # Method 2: youtu.be/VIDEO_ID format
    if 'youtu.be' in parsed_url.netloc:
        path = parsed_url.path.strip('/')
        if path and len(path) == 11:
            return path
    
    # Method 3: youtube.com/embed/VIDEO_ID format
    if 'youtube.com' in parsed_url.netloc and '/embed/' in parsed_url.path:
        path_parts = parsed_url.path.split('/')
        if len(path_parts) > 2:
            return path_parts[2]
    
    # Method 4: youtube.com/shorts/VIDEO_ID format
    if 'youtube.com' in parsed_url.netloc and '/shorts/' in parsed_url.path:
        path_parts = parsed_url.path.split('/')
        if len(path_parts) > 2:
            return path_parts[2]
    
    # Method 5: Raw regex patterns as fallback
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:&|\/|$)',  # Standard URLs
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)',  # Shortened URLs
        r'(?:embed\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)',  # Embed URLs
        r'(?:shorts\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)',  # YouTube Shorts
        r'^([0-9A-Za-z_-]{11})$'  # Just the ID itself
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Method 6: Check if the URL itself is just the ID
    if re.match(r'^[0-9A-Za-z_-]{11}$', url):
        return url
    
    return None

def get_youtube_transcript_with_api(video_id):
    """
    Try to extract transcript using the YouTube Transcript API.
    This is the primary method.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: Extracted transcript or None if failed
    """
    logger.info(f"Attempting to extract transcript with YouTube API for video: {video_id}")
    
    try:
        # Languages to try in order of preference
        languages_to_try = ['en', 'en-US', 'en-GB', 'ar', 'es', 'fr', 'de', 'ru', 'zh', 'zh-CN', 'ja', 'ko', 'pt', 'it']
        transcript = None
        
        # First try specific languages
        for lang in languages_to_try:
            try:
                logger.info(f"Trying to get transcript in language: {lang}")
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                logger.info(f"Found transcript in language: {lang}")
                break
            except NoTranscriptFound:
                continue
            except Exception as lang_e:
                logger.warning(f"Error getting transcript in {lang}: {str(lang_e)}")
                continue
        
        # If specific languages failed, try any available transcript
        if not transcript:
            logger.info("Trying to get list of available transcripts")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # First try auto-generated transcript
            for t in transcript_list:
                if t.is_generated:
                    logger.info(f"Found auto-generated transcript in {t.language_code}")
                    transcript = t.fetch()
                    break
            
            # If no auto-generated, get first available
            if not transcript and len(list(transcript_list)) > 0:
                first_transcript = list(transcript_list)[0]
                logger.info(f"Using first available transcript in {first_transcript.language_code}")
                transcript = first_transcript.fetch()
        
        if transcript:
            # Extract text from transcript
            text = " ".join([item["text"] for item in transcript])
            logger.info(f"Successfully extracted transcript with {len(text)} characters")
            return text
        
        return None
        
    except Exception as e:
        logger.warning(f"YouTube transcript API failed: {str(e)}")
        return None

def get_youtube_transcript_with_requests(video_id):
    """
    Try to extract transcript using direct requests to YouTube.
    This is a fallback method.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: Extracted transcript or None if failed
    """
    logger.info(f"Attempting to extract transcript with HTTP requests for video: {video_id}")
    
    try:
        # Try a more direct approach with YouTube's timedtext API
        # First get video info to find available captions
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Request the watch page to get potential caption data
        response = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.warning(f"Failed to get YouTube watch page, status code: {response.status_code}")
            return None
        
        # Look for caption data in various formats
        # Method 1: Try to find captionTracks in the page source
        caption_regex = r'"captionTracks":\s*(\[.*?\])'
        caption_match = re.search(caption_regex, response.text)
        
        if caption_match:
            try:
                caption_data = json.loads(caption_match.group(1))
                
                # Find the English or first available caption
                caption_url = None
                for caption in caption_data:
                    if caption.get('languageCode', '').startswith('en'):
                        caption_url = caption.get('baseUrl')
                        break
                
                # If no English caption found, take the first one
                if not caption_url and caption_data:
                    caption_url = caption_data[0].get('baseUrl')
                
                if caption_url:
                    caption_url = caption_url.replace('\\u0026', '&')
                    logger.info(f"Found caption URL: {caption_url[:50]}...")
                    
                    # Request the caption file
                    caption_response = requests.get(caption_url, headers=headers, timeout=10)
                    
                    if caption_response.status_code == 200:
                        # Extract text from XML
                        text_matches = re.findall(r'<text[^>]*>(.*?)</text>', caption_response.text)
                        if text_matches:
                            # Process and join all text segments
                            import html
                            cleaned_text = [html.unescape(t) for t in text_matches]
                            full_text = " ".join(cleaned_text)
                            logger.info(f"Successfully extracted {len(full_text)} characters from caption XML")
                            return full_text
            except Exception as json_error:
                logger.warning(f"Error parsing caption data: {str(json_error)}")
        
        # Method 2: Try scraping player response JSON
        player_response_regex = r'var ytInitialPlayerResponse = ({.*?});'
        player_match = re.search(player_response_regex, response.text)
        
        if player_match:
            try:
                player_data = json.loads(player_match.group(1))
                caption_tracks = player_data.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
                
                if caption_tracks:
                    # Find the English or first available caption
                    caption_url = None
                    for track in caption_tracks:
                        if track.get('languageCode', '').startswith('en'):
                            caption_url = track.get('baseUrl')
                            break
                    
                    # If no English caption found, take the first one
                    if not caption_url and caption_tracks:
                        caption_url = caption_tracks[0].get('baseUrl')
                    
                    if caption_url:
                        # Request the caption file
                        caption_response = requests.get(caption_url, headers=headers, timeout=10)
                        
                        if caption_response.status_code == 200:
                            # Extract text from XML
                            text_matches = re.findall(r'<text[^>]*>(.*?)</text>', caption_response.text)
                            if text_matches:
                                # Process and join all text segments
                                import html
                                cleaned_text = [html.unescape(t) for t in text_matches]
                                full_text = " ".join(cleaned_text)
                                logger.info(f"Successfully extracted {len(full_text)} characters from caption XML")
                                return full_text
            except Exception as json_error:
                logger.warning(f"Error parsing player response: {str(json_error)}")
        
        return None
        
    except Exception as e:
        logger.warning(f"HTTP request method failed: {str(e)}")
        return None

def get_youtube_transcript_with_external_service(video_id):
    """
    Try to extract transcript using external services as a last resort.
    This is a backup method.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        str: Extracted transcript or None if failed
    """
    logger.info(f"Attempting to extract transcript with external service for video: {video_id}")
    
    try:
        # Try using a third-party service like SaveSubs (this is an example - you may need API access)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://savesubs.com/',
            'Accept': 'application/json'
        }
        
        # This is a placeholder for a potential external API call
        response = requests.post(
            'https://savesubs.com/api/extract',
            json={'url': f'https://www.youtube.com/watch?v={video_id}', 'lang': 'en'},
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('success') and data.get('transcript'):
                    logger.info(f"Successfully extracted transcript from external service")
                    return data['transcript']
            except Exception as json_error:
                logger.warning(f"Error parsing external service response: {str(json_error)}")
        
        # You can add more external services here as additional fallbacks
        
        return None
        
    except Exception as e:
        logger.warning(f"External service method failed: {str(e)}")
        return None

def get_available_transcript_languages(video_id):
    """
    Get a list of available transcript languages for a video.
    
    Args:
        video_id (str): YouTube video ID
        
    Returns:
        list: List of available language codes and whether they're auto-generated
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_languages = []
        
        for transcript in transcript_list:
            available_languages.append({
                "language_code": transcript.language_code,
                "language": transcript.language,
                "is_generated": transcript.is_generated,
                "is_translatable": transcript.is_translatable
            })
        
        return available_languages
    except Exception as e:
        logger.error(f"Error getting available transcript languages: {str(e)}")
        return []

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
        loader = UnstructuredLoader(pptx_path)
        documents = loader.load()
        text = "\n\n".join([doc.page_content for doc in documents])
        logger.info("Successfully extracted text from PPTX using UnstructuredLoader")
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
        loader = UnstructuredLoader(docx_path)
        documents = loader.load()
        text = "\n\n".join([doc.page_content for doc in documents])
        logger.info("Successfully extracted text from DOCX using UnstructuredLoader")
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
        # Use improved video ID extraction
        video_id = extract_youtube_id(url)
        
        if not video_id:
            logger.warning(f"Invalid YouTube URL: {url}")
            return Response({"error": "Invalid YouTube URL or video ID. Please provide a valid YouTube video URL."}, status=400)
        
        logger.info(f"Extracted YouTube video ID: {video_id}")
        
        # Try multiple methods with proper error handling
        extracted_text = None
        error_messages = []
        
        # Method 1: Try using the YouTube Transcript API (most reliable)
        try:
            extracted_text = get_youtube_transcript_with_api(video_id)
            if extracted_text:
                logger.info("Successfully extracted text with YouTube Transcript API")
                return Response({"extracted_text": extracted_text})
        except Exception as e:
            error_msg = f"YouTube Transcript API failed: {str(e)}"
            logger.warning(error_msg)
            error_messages.append(error_msg)
        
        # Method 2: Try using direct HTTP requests
        try:
            extracted_text = get_youtube_transcript_with_requests(video_id)
            if extracted_text:
                logger.info("Successfully extracted text with direct HTTP requests")
                return Response({"extracted_text": extracted_text})
        except Exception as e:
            error_msg = f"Direct HTTP request method failed: {str(e)}"
            logger.warning(error_msg)
            error_messages.append(error_msg)
        
        # Method 3: Try using external service (last resort)
        try:
            extracted_text = get_youtube_transcript_with_external_service(video_id)
            if extracted_text:
                logger.info("Successfully extracted text with external service")
                return Response({"extracted_text": extracted_text})
        except Exception as e:
            error_msg = f"External service method failed: {str(e)}"
            logger.warning(error_msg)
            error_messages.append(error_msg)
        
        # If all methods fail, return error with available languages if possible
        try:
            languages = get_available_transcript_languages(video_id)
            if languages:
                language_options = ", ".join([f"{lang['language_code']} ({lang['language']})" for lang in languages])
                logger.error(f"All transcript methods failed. Available languages: {language_options}")
                return Response({
                    "error": f"YouTube transcript extraction failed. Available languages: {language_options}",
                    "suggestion": "You may need to specify one of these languages in your request."
                }, status=400)
            else:
                # If we can't even get language list
                combined_errors = " | ".join(error_messages) if error_messages else "Unknown error"
                logger.error(f"All transcript methods failed: {combined_errors}")
                return Response({
                    "error": "YouTube transcript extraction failed using all available methods.",
                    "detail": combined_errors,
                    "suggestion": "This video might not have transcripts available or they might be disabled."
                }, status=400)
        except Exception:
            # If we can't even get language list
            combined_errors = " | ".join(error_messages) if error_messages else "Unknown error"
            logger.error(f"All transcript methods failed: {combined_errors}")
            return Response({
                "error": "YouTube transcript extraction failed using all available methods.",
                "detail": combined_errors,
                "suggestion": "This video might not have transcripts available or they might be disabled."
            }, status=400)
    
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
